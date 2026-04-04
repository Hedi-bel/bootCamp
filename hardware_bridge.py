"""
Hardware bridge — mock-friendly replacement for ros_bridge.py.

Provides the same public interface as the original ROSBridge class so that
tools/robot.py and the rest of the codebase work with zero changes.

Two operating modes controlled by `mock_mode` in settings (or MOCK_MODE env var):

  mock_mode = True  (default) → all actions are logged to console; no real
                                 hardware, ROS 2, or MQTT connection needed.

  mock_mode = False           → attempts real MQTT communication with the
                                 ESP32 robot.  Falls back to mock if the
                                 broker is unreachable.

MQTT topic layout (ESP32 firmware convention):
  factory_guardian/motor   → JSON  {"action": "forward|backward|left|right|stop",
                                     "duration": <float>}
  factory_guardian/status  → JSON  {"ready": true/false, "message": "..."}
  factory_guardian/action_done  ← robot publishes 1 when a manoeuvre finishes

----------------------------------------------------------------------
Original ROS 2 bridge preserved in ros_bridge_legacy.py for future use.
----------------------------------------------------------------------
"""

from __future__ import annotations

import json
import logging
import random
import threading
import time
from typing import Callable

from settings import settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
#  Optional MQTT client — imported lazily so mock mode has zero deps
# ═══════════════════════════════════════════════════════════════════════════

def _try_import_mqtt():
    """Attempt to import paho-mqtt; return the client class or None."""
    try:
        import paho.mqtt.client as mqtt  # type: ignore
        return mqtt
    except ImportError:
        logger.warning(
            "paho-mqtt not installed — MQTT features disabled.  "
            "Install with:  pip install paho-mqtt"
        )
        return None


# ═══════════════════════════════════════════════════════════════════════════
#  MQTT Bridge  (real hardware path)
# ═══════════════════════════════════════════════════════════════════════════

class MQTTBridge:
    """
    Thin wrapper around a paho-mqtt client.

    Publishes motor commands to the ESP32 and subscribes to feedback.
    Falls back to 'not connected' status if the broker is unreachable.
    """

    def __init__(
        self,
        broker: str = "localhost",
        port: int = 1883,
        topic_motor: str = "factory_guardian/motor",
        topic_status: str = "factory_guardian/status",
        topic_action_done: str = "factory_guardian/action_done",
    ) -> None:
        self.broker = broker
        self.port = port
        self.topic_motor = topic_motor
        self.topic_status = topic_status
        self.topic_action_done = topic_action_done
        self.connected = False

        self._action_done_callbacks: list[Callable[[int], None]] = []

        mqtt = _try_import_mqtt()
        if mqtt is None:
            self._client = None
            return

        self._client = mqtt.Client(
            client_id="factory_guardian_bridge",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

        # Non-blocking connect attempt
        try:
            self._client.connect(self.broker, self.port, keepalive=60)
            self._client.loop_start()
            logger.info("MQTT connecting to %s:%d …", self.broker, self.port)
        except Exception as exc:
            logger.warning("MQTT connection failed (%s) — running without broker.", exc)
            self._client = None

    # -- paho callbacks ---------------------------------------------------

    def _on_connect(self, client, userdata, flags, rc, properties=None) -> None:
        if rc == 0:
            self.connected = True
            logger.info("MQTT connected to %s:%d", self.broker, self.port)
            client.subscribe(self.topic_action_done)
            client.subscribe(self.topic_status)
        else:
            logger.warning("MQTT connect failed with code %d", rc)

    def _on_message(self, client, userdata, msg) -> None:
        logger.info("MQTT ← %s: %s", msg.topic, msg.payload.decode())
        if msg.topic == self.topic_action_done:
            try:
                value = int(msg.payload.decode())
                for cb in self._action_done_callbacks:
                    cb(value)
            except ValueError:
                pass

    # -- public API -------------------------------------------------------

    def publish(self, topic: str, payload: dict) -> None:
        """Publish a JSON payload to a topic."""
        data = json.dumps(payload)
        if self._client and self.connected:
            self._client.publish(topic, data)
            logger.info("MQTT → %s: %s", topic, data)
        else:
            logger.info("[MQTT-stub] → %s: %s", topic, data)

    def publish_motor(self, action: str, duration: float = 1.0) -> None:
        """Send a motor command to the ESP32."""
        self.publish(self.topic_motor, {"action": action, "duration": duration})

    def register_action_done(self, cb: Callable[[int], None]) -> None:
        self._action_done_callbacks.append(cb)

    def shutdown(self) -> None:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            logger.info("MQTT client disconnected.")


# ═══════════════════════════════════════════════════════════════════════════
#  HardwareBridge  (drop-in replacement for ROSBridge)
# ═══════════════════════════════════════════════════════════════════════════

class HardwareBridge:
    """
    Unified hardware bridge for Factory Guardian.

    Provides the SAME public methods as the original ROSBridge:
        publish_strategy(values)
        publish_start(value)
        call_status()          → (bool, str)
        on_action_done(cb)
        shutdown()

    Plus new Factory Guardian helpers:
        send_motor_command(action, duration)
        get_status_report()
    """

    def __init__(self) -> None:
        self.mock_mode: bool = getattr(settings, "mock_mode", True)
        self._action_done_callbacks: list[Callable[[int], None]] = []
        self._robot_ready: bool = True  # simulated state

        # Initialise MQTT bridge (even in mock mode — it gracefully no-ops)
        if not self.mock_mode:
            self._mqtt = MQTTBridge(
                broker=getattr(settings, "mqtt_broker", "localhost"),
                port=getattr(settings, "mqtt_port", 1883),
                topic_motor=getattr(
                    settings, "mqtt_topic_motor", "factory_guardian/motor"
                ),
            )
            self._mqtt.register_action_done(self._handle_action_done)
        else:
            self._mqtt = None

        mode_label = "MOCK" if self.mock_mode else "LIVE"
        logger.info(
            "HardwareBridge ready  [%s]  robot=%s",
            mode_label,
            settings.robot_name,
        )

    # ------------------------------------------------------------------
    #  Original ROSBridge interface (backward-compatible)
    # ------------------------------------------------------------------

    def publish_strategy(self, values: list[float]) -> None:
        """
        Replaces ROS Float32MultiArray publish to <robot>/strategy.
        In mock mode, logs the payload.
        In live mode, translates to MQTT motor commands.
        """
        if self.mock_mode:
            logger.info("[MOCK] strategy → %s", values)
        else:
            # Translate legacy strategy array to motor command
            # values[0] = command code, values[1:] = params
            if self._mqtt:
                self._mqtt.publish(
                    self._mqtt.topic_motor,
                    {"strategy": values},
                )
        self._robot_ready = False

    def publish_start(self, value: int = 1) -> None:
        """
        Replaces ROS Int32 publish to <robot>/start.
        In mock mode, logs the start signal.
        """
        if self.mock_mode:
            logger.info("[MOCK] start → %d", value)
        else:
            if self._mqtt:
                self._mqtt.publish(
                    self._mqtt.topic_motor,
                    {"action": "start", "signal": value},
                )
        self._robot_ready = False

    def call_status(self) -> tuple[bool, str]:
        """
        Replaces ROS Trigger service call to <robot>/status.
        In mock mode, returns a simulated status.
        """
        if self.mock_mode:
            state = "READY" if self._robot_ready else "EXECUTING"
            msg = (
                f"Robot '{settings.robot_name}' is {state}. "
                f"(mock mode — no real hardware connected)"
            )
            logger.info("[MOCK] status → ready=%s", self._robot_ready)
            return self._robot_ready, msg
        else:
            # In live mode, check MQTT connectivity as a proxy
            if self._mqtt and self._mqtt.connected:
                return True, f"Robot '{settings.robot_name}' MQTT link is UP."
            return False, f"Robot '{settings.robot_name}' MQTT link is DOWN."

    def on_action_done(self, cb: Callable[[int], None]) -> None:
        """Register a callback for action_done events."""
        self._action_done_callbacks.append(cb)

    def shutdown(self) -> None:
        """Clean up MQTT and any background threads."""
        if self._mqtt:
            self._mqtt.shutdown()
        logger.info("HardwareBridge shut down.")

    # ------------------------------------------------------------------
    #  NEW — Factory Guardian motor commands
    # ------------------------------------------------------------------

    def send_motor_command(self, action: str, duration: float = 1.0) -> str:
        """
        Send a directional motor command to the ESP32.

        Args:
            action:   one of 'forward', 'backward', 'left', 'right', 'stop'
            duration: how long to run the motors (seconds)

        Returns:
            Human-readable status string.
        """
        valid_actions = {"forward", "backward", "left", "right", "stop"}
        if action not in valid_actions:
            return f"Unknown action '{action}'. Valid: {sorted(valid_actions)}"

        if self.mock_mode:
            logger.info(
                "[MOCK] motor command: %s for %.1fs", action, duration
            )
            # Simulate execution time (non-blocking)
            self._robot_ready = False
            threading.Timer(
                duration,
                self._simulate_action_done,
            ).start()
            return (
                f"[MOCK] Robot moving '{action}' for {duration:.1f}s. "
                f"(simulated — no real motors)"
            )
        else:
            if self._mqtt:
                self._mqtt.publish_motor(action, duration)
                self._robot_ready = False
                return f"Motor command sent: {action} for {duration:.1f}s."
            return "MQTT not connected — command not sent."

    def get_status_report(self) -> str:
        """Formatted status suitable for display in the Gradio UI."""
        ready, msg = self.call_status()
        state_emoji = "🟢" if ready else "🟡"
        mode_label = "Simulation" if self.mock_mode else "Live"
        return (
            f"{state_emoji} **{settings.robot_name}** — "
            f"{'READY' if ready else 'BUSY'}\n"
            f"Mode: {mode_label}\n"
            f"Detail: {msg}"
        )

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------

    def _handle_action_done(self, value: int) -> None:
        """Called when the real robot reports action done via MQTT."""
        logger.info("action_done ← %d", value)
        self._robot_ready = True
        for cb in self._action_done_callbacks:
            cb(value)

    def _simulate_action_done(self) -> None:
        """Timer callback that fakes an action_done event in mock mode."""
        logger.info("[MOCK] action_done ← 1  (simulated)")
        self._robot_ready = True
        for cb in self._action_done_callbacks:
            cb(1)


# ═══════════════════════════════════════════════════════════════════════════
#  Module-level singleton  (same pattern as the original ros_bridge.py)
# ═══════════════════════════════════════════════════════════════════════════

hardware_bridge = HardwareBridge()

# Backward-compatible alias so `from hardware_bridge import ros_bridge` works
ros_bridge = hardware_bridge


# ═══════════════════════════════════════════════════════════════════════════
#  Demo sequence  (run this file directly to exercise the mock bridge)
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("=" * 60)
    print("  Factory Guardian — Hardware Bridge Demo")
    print("=" * 60)

    bridge = HardwareBridge()

    # Register action_done listener
    bridge.on_action_done(
        lambda v: print(f"  🔔 action_done callback fired (value={v})")
    )

    # 1. Check initial status
    print("\n▸ Checking status …")
    print(f"  {bridge.get_status_report()}")

    # 2. Send a patrol sequence
    patrol = [
        ("forward",  2.0),
        ("left",     1.0),
        ("forward",  3.0),
        ("right",    1.0),
        ("forward",  2.0),
        ("stop",     0.0),
    ]

    print("\n▸ Running patrol sequence …")
    for action, duration in patrol:
        result = bridge.send_motor_command(action, duration)
        print(f"  → {result}")
        time.sleep(0.3)  # small delay between commands for readability

    # 3. Wait for mock actions to complete
    print("\n▸ Waiting for simulated actions to complete …")
    time.sleep(4.0)

    # 4. Legacy interface test
    print("\n▸ Testing legacy ROSBridge interface …")
    bridge.publish_strategy([2.0, 5.0, 3.0, 0.3])
    bridge.publish_start(1)
    ready, msg = bridge.call_status()
    print(f"  call_status() → ready={ready}, msg='{msg}'")

    # 5. Final status
    time.sleep(1.0)
    print(f"\n▸ Final status:\n  {bridge.get_status_report()}")

    bridge.shutdown()
    print("\n✅ Demo complete.")

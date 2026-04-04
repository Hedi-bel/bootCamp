"""
Robot movement tools — directional motor commands for Factory Guardian.

Replaces the original coordinate-based tools (set_position, go_to) with
simple directional commands suitable for an ESP32-driven patrol robot:
    move_forward, move_backward, turn_left, turn_right, stop_robot, check_status

Each tool calls hardware_bridge.send_motor_command() which publishes via
MQTT in live mode or logs to console in mock mode.
"""

import logging

from hardware_bridge import hardware_bridge
from settings import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Tool implementations
# ---------------------------------------------------------------------------

def move_forward(duration: float = 2.0) -> str:
    """Move the robot forward for the given duration (seconds)."""
    duration = max(0.1, min(duration, 30.0))
    result = hardware_bridge.send_motor_command("forward", duration)
    logger.info("move_forward(%.1fs) → %s", duration, result)
    return f"🤖 Moving forward for {duration:.1f}s. {result}"


def move_backward(duration: float = 2.0) -> str:
    """Move the robot backward for the given duration (seconds)."""
    duration = max(0.1, min(duration, 30.0))
    result = hardware_bridge.send_motor_command("backward", duration)
    logger.info("move_backward(%.1fs) → %s", duration, result)
    return f"🤖 Moving backward for {duration:.1f}s. {result}"


def turn_left(duration: float = 1.0) -> str:
    """Turn the robot left for the given duration (seconds)."""
    duration = max(0.1, min(duration, 10.0))
    result = hardware_bridge.send_motor_command("left", duration)
    logger.info("turn_left(%.1fs) → %s", duration, result)
    return f"🤖 Turning left for {duration:.1f}s. {result}"


def turn_right(duration: float = 1.0) -> str:
    """Turn the robot right for the given duration (seconds)."""
    duration = max(0.1, min(duration, 10.0))
    result = hardware_bridge.send_motor_command("right", duration)
    logger.info("turn_right(%.1fs) → %s", duration, result)
    return f"🤖 Turning right for {duration:.1f}s. {result}"


def stop_robot() -> str:
    """Immediately stop all robot movement."""
    result = hardware_bridge.send_motor_command("stop", 0.0)
    logger.info("stop_robot() → %s", result)
    return f"🛑 Robot stopped. {result}"


def check_status() -> str:
    """Query the robot's current operational status."""
    report = hardware_bridge.get_status_report()
    logger.info("check_status() → %s", report)
    return report


# ---------------------------------------------------------------------------
#  Tool registry  (consumed by tools/__init__.py)
# ---------------------------------------------------------------------------

ROBOT_TOOLS: dict = {
    "move_forward": move_forward,
    "move_backward": move_backward,
    "turn_left": turn_left,
    "turn_right": turn_right,
    "stop_robot": stop_robot,
    "check_status": check_status,
}

# ---------------------------------------------------------------------------
#  LLM tool schemas  (OpenAI function-calling format)
# ---------------------------------------------------------------------------

ROBOT_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "move_forward",
            "description": (
                "Move the Factory Guardian robot forward. "
                "Use when the user says 'go forward', 'move ahead', 'advance', etc. "
                "Duration defaults to 2 seconds if not specified."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "duration": {
                        "type": "number",
                        "description": (
                            "How long to move forward in seconds (0.1–30). "
                            "Default: 2.0. 'a little' = 1s, 'a lot' = 5s."
                        ),
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_backward",
            "description": (
                "Move the Factory Guardian robot backward. "
                "Use when the user says 'go back', 'reverse', 'move backward', etc. "
                "Duration defaults to 2 seconds if not specified."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "duration": {
                        "type": "number",
                        "description": (
                            "How long to move backward in seconds (0.1–30). "
                            "Default: 2.0."
                        ),
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn_left",
            "description": (
                "Turn the Factory Guardian robot to the left. "
                "Use when the user says 'turn left', 'go left', 'rotate left', etc. "
                "Duration defaults to 1 second if not specified."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "duration": {
                        "type": "number",
                        "description": (
                            "How long to turn left in seconds (0.1–10). "
                            "Default: 1.0. 'slightly' = 0.5s, '90 degrees' ≈ 1s."
                        ),
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn_right",
            "description": (
                "Turn the Factory Guardian robot to the right. "
                "Use when the user says 'turn right', 'go right', 'rotate right', etc. "
                "Duration defaults to 1 second if not specified."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "duration": {
                        "type": "number",
                        "description": (
                            "How long to turn right in seconds (0.1–10). "
                            "Default: 1.0."
                        ),
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stop_robot",
            "description": (
                "Immediately stop all robot movement. "
                "Use when the user says 'stop', 'halt', 'freeze', 'emergency stop', etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_status",
            "description": (
                "Query the robot's current operational status. "
                "Returns whether the robot is READY or BUSY, plus mode info. "
                "Use when the user asks 'what is the status?', 'is the robot ready?', etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]

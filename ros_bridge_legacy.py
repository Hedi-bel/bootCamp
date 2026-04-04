"""
ROS 2 bridge — publishes commands to the robot and calls its status service.

Topic/service layout (mirrors the firmware's snprintf logic):
  <robot_name>/strategy     Float32MultiArray  → send command payloads
  <robot_name>/start        std_msgs/Int32     → send 1 to trigger execution
  <robot_name>/action_done  std_msgs/Int32     ← robot publishes when done
  <robot_name>/status       std_srvs/Trigger   ← service: ready=true / busy=false

Requirements:
  source /opt/ros/jazzy/setup.bash   before running app.py
"""

import logging
import os
import threading
from typing import Callable

from settings import settings

# Must be set before rclpy is imported/initialized
os.environ["RMW_IMPLEMENTATION"] = "rmw_fastrtps_cpp"
os.environ["ROS_DOMAIN_ID"] = str(settings.ros_domain_id)

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray, Int32
from std_srvs.srv import Trigger

logger = logging.getLogger(__name__)


class _RobotNode(Node):
    def __init__(self) -> None:
        super().__init__("robot_controller")

        # Publishers
        self._strategy_pub = self.create_publisher(
            Float32MultiArray, settings.topic_strategy, qos_profile=10
        )
        self._start_pub = self.create_publisher(
            Int32, settings.topic_start, qos_profile=10
        )

        # Service client
        self._status_client = self.create_client(Trigger, settings.service_status)

        # Subscriber — action_done feedback from the robot
        self._action_done_callbacks: list[Callable[[int], None]] = []
        self.create_subscription(
            Int32,
            settings.topic_action_done,
            self._on_action_done,
            qos_profile=10,
        )

        self.get_logger().info(
            f"Robot node ready | strategy={settings.topic_strategy}"
            f" | start={settings.topic_start}"
            f" | status={settings.service_status}"
        )

    # ------------------------------------------------------------------
    # Publishers
    # ------------------------------------------------------------------

    def publish_strategy(self, values: list[float]) -> None:
        count = self._strategy_pub.get_subscription_count()
        self.get_logger().info(f"strategy subscribers: {count}")
        msg = Float32MultiArray()
        msg.data = [float(v) for v in values]
        self._strategy_pub.publish(msg)
        self.get_logger().info(f"strategy → {values}")

    def publish_start(self, value: int = 1) -> None:
        msg = Int32()
        msg.data = value
        self._start_pub.publish(msg)
        self.get_logger().info(f"start → {value}")

    # ------------------------------------------------------------------
    # Service call
    # ------------------------------------------------------------------

    def call_status(self) -> tuple[bool, str]:
        """
        Call pami4/status (std_srvs/Trigger).
        Returns (success, message). Blocks up to settings.service_timeout_sec.
        """
        if not self._status_client.wait_for_service(
            timeout_sec=settings.service_timeout_sec
        ):
            return False, "Status service not available — is the robot connected?"

        future = self._status_client.call_async(Trigger.Request())

        # The background spin thread will resolve the future; we wait on an event.
        done = threading.Event()
        future.add_done_callback(lambda _: done.set())
        done.wait(timeout=settings.service_timeout_sec)

        if not future.done():
            return False, "Status service call timed out."

        result = future.result()
        return result.success, result.message.data

    # ------------------------------------------------------------------
    # Subscriber callback
    # ------------------------------------------------------------------

    def _on_action_done(self, msg: Int32) -> None:
        self.get_logger().info(f"action_done ← {msg.data}")
        for cb in self._action_done_callbacks:
            cb(msg.data)

    def register_action_done_callback(self, cb: Callable[[int], None]) -> None:
        self._action_done_callbacks.append(cb)


class ROSBridge:
    """
    Initialises rclpy and spins the node in a daemon thread so the
    Gradio event loop is never blocked.
    """

    def __init__(self) -> None:
        rclpy.init()
        self._node = _RobotNode()
        self._thread = threading.Thread(
            target=rclpy.spin,
            args=(self._node,),
            daemon=True,
            name="rclpy-spin",
        )
        self._thread.start()
        logger.info("ROS bridge ready (robot=%s, domain=%d)", settings.robot_name, settings.ros_domain_id)

    def publish_strategy(self, values: list[float]) -> None:
        self._node.publish_strategy(values)

    def publish_start(self, value: int = 1) -> None:
        self._node.publish_start(value)

    def call_status(self) -> tuple[bool, str]:
        return self._node.call_status()

    def on_action_done(self, cb: Callable[[int], None]) -> None:
        self._node.register_action_done_callback(cb)

    def shutdown(self) -> None:
        self._node.destroy_node()
        rclpy.shutdown()
        logger.info("ROS bridge shut down.")


ros_bridge = ROSBridge()

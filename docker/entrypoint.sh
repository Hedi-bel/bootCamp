#!/bin/bash
set -e

# Source ROS 2 base and the compiled micro-ROS agent overlay
source /opt/ros/jazzy/setup.bash
source /ws/install/setup.bash

echo "[micro-ROS Agent] Starting with args: $*"
exec ros2 run micro_ros_agent micro_ros_agent "$@"

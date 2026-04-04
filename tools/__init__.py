"""
Tool registry — aggregates all tool groups into TOOL_REGISTRY and
TOOL_SCHEMAS for the LLM agent.

Tool groups:
  - robot.py  : movement tools (forward, backward, left, right, stop, status)
  - camera.py : camera capture tool
  - safety.py : YOLO-based safety inspection tool
"""

from tools.robot import ROBOT_TOOLS, ROBOT_TOOL_SCHEMAS
from tools.camera import CAMERA_TOOLS, CAMERA_TOOL_SCHEMAS
from tools.safety import SAFETY_TOOLS, SAFETY_TOOL_SCHEMAS

TOOL_REGISTRY: dict = {
    **ROBOT_TOOLS,
    **CAMERA_TOOLS,
    **SAFETY_TOOLS,
}

TOOL_SCHEMAS: list[dict] = [
    *ROBOT_TOOL_SCHEMAS,
    *CAMERA_TOOL_SCHEMAS,
    *SAFETY_TOOL_SCHEMAS,
]

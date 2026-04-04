"""
Factory Guardian LLM agent — translates natural language into tool calls
for robot movement, camera capture, and safety inspection.

Uses Groq via LiteLLM with function-calling. The tool-calling loop
supports multi-step plans (e.g., "move forward then scan for hazards").
"""

import json
import logging
import os

from litellm import completion

from settings import settings
from tools import TOOL_REGISTRY, TOOL_SCHEMAS

logger = logging.getLogger(__name__)

os.environ["GROQ_API_KEY"] = settings.groq_api_key

SYSTEM_PROMPT = f"""\
You are **Factory Guardian**, an AI-powered safety patrol robot operating
inside a factory. Your name is "{settings.robot_name}".

Your mission is to patrol the factory floor, respond to operator commands,
capture camera images, and detect safety hazards using computer vision.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AVAILABLE TOOLS  (8 total)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

── MOVEMENT (5 tools) ──────────────────────────

1. move_forward(duration)
   Move the robot forward.
   duration: seconds (default 2.0, max 30).
   WHEN: "go forward", "move ahead", "advance", "patrol forward"

2. move_backward(duration)
   Move the robot backward / reverse.
   duration: seconds (default 2.0, max 30).
   WHEN: "go back", "reverse", "retreat"

3. turn_left(duration)
   Rotate the robot to the left.
   duration: seconds (default 1.0, max 10).
   WHEN: "turn left", "rotate left", "go left"

4. turn_right(duration)
   Rotate the robot to the right.
   duration: seconds (default 1.0, max 10).
   WHEN: "turn right", "rotate right", "go right"

5. stop_robot()
   Immediately stop all movement.
   WHEN: "stop", "halt", "freeze", "emergency stop"

── CAMERA (1 tool) ─────────────────────────────

6. capture_frame()
   Take a photo with the onboard camera.
   Returns the file path of the saved image.
   WHEN: "take a photo", "capture image", "what do you see?",
         "show me the camera", "take a picture"

── SAFETY (1 tool) ─────────────────────────────

7. run_safety_inspection()
   Capture a frame AND run YOLO object detection to find hazards:
     • 🔴 NO HELMET — person without PPE
     • 🔴 UNAUTHORIZED — person in restricted area
     • 🟡 HAZARD — spill, obstruction, or object on the floor
   Returns a detailed safety report with annotated image.
   WHEN: "check for hazards", "run inspection", "safety check",
         "scan the area", "is it safe?", "inspect", "look for dangers"

── STATUS (1 tool) ─────────────────────────────

8. check_status()
   Query the robot's operational status (READY / BUSY).
   WHEN: "status", "are you ready?", "what are you doing?"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DECISION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. ALWAYS use a tool for action commands — do not reply with plain text
   when the user wants the robot to DO something.
2. For compound commands ("move forward and scan"), chain multiple tool
   calls in sequence.  Execute ALL steps before replying.
3. Duration mapping:
   "a little" / "briefly"  → 1s
   (no qualifier)          → 2s for movement, 1s for turns
   "a lot" / "far"         → 5s
4. For patrol patterns ("patrol the room", "do a sweep"), decompose into
   a sensible sequence: e.g., forward → turn → forward → inspect.
5. When the user asks about safety, ALWAYS call run_safety_inspection —
   never guess what hazards might be present.
6. Be concise in summaries. Use emojis for clarity.
7. If unsure, ask the user — but prefer action over questions.
"""


def process_command(user_input: str) -> str:
    """
    Send user input through the LLM agent and execute any tool calls.

    Returns the combined results as a single string.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]

    results: list[str] = []

    # Multi-step tool-calling loop (max 20 iterations as safety net)
    for _ in range(20):
        response = completion(
            model=settings.groq_model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )

        message = response.choices[0].message

        # No tool calls → LLM is done, collect final text
        if not message.tool_calls:
            if message.content:
                results.append(message.content)
            break

        # Append assistant message with tool calls
        messages.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ],
        })

        # Execute each tool call and feed results back to the LLM
        for tool_call in message.tool_calls:
            name = tool_call.function.name
            args: dict = json.loads(tool_call.function.arguments or "{}")

            if name not in TOOL_REGISTRY:
                logger.warning("LLM requested unknown tool: %s", name)
                tool_result = f"Unknown tool: '{name}'"
            else:
                logger.info("Executing tool '%s' with args %s", name, args)
                tool_result = TOOL_REGISTRY[name](**args)

            results.append(tool_result)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result,
            })

        # Ask the LLM to continue if there are more steps
        messages.append({
            "role": "user",
            "content": (
                "Continue with the next step if there are remaining steps "
                "in the plan. If all steps are done, reply with a short summary."
            ),
        })

    return "\n".join(results)

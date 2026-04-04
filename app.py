"""
Factory Guardian — Gradio web interface.

Features:
  • Chat panel for natural language commands (text input)
  • Voice input via Gradio Audio component (speech-to-text)
  • Image display panel for camera captures and detection results
  • Quick-action buttons for common commands
"""

import atexit
import logging
import os

import gradio as gr

from agent import process_command
from hardware_bridge import hardware_bridge
from settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Clean shutdown of hardware bridge on exit
atexit.register(hardware_bridge.shutdown)


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _extract_image_path(text: str) -> str | None:
    """Extract an image file path from tool output if present."""
    import re
    # Look for paths ending in .jpg or .png
    match = re.search(r'[`"]?([A-Za-z]:\\[^`"]+\.(?:jpg|png))[`"]?', text)
    if match:
        path = match.group(1)
        if os.path.isfile(path):
            return path
    # Also check unix-style paths (for WSL / Linux)
    match = re.search(r'[`"]?(/[^`"]+\.(?:jpg|png))[`"]?', text)
    if match:
        path = match.group(1)
        if os.path.isfile(path):
            return path
    return None


def _transcribe_audio(audio_path: str) -> str:
    """
    Transcribe an audio file to text.
    Uses Groq Whisper via LiteLLM if available, otherwise basic fallback.
    """
    if not audio_path:
        return ""

    try:
        from litellm import transcription
        result = transcription(
            model="groq/whisper-large-v3",
            file=open(audio_path, "rb"),
        )
        text = result.text.strip()
        logger.info("Transcribed audio: '%s'", text)
        return text
    except Exception as exc:
        logger.warning("Audio transcription failed: %s", exc)
        return "[Could not transcribe audio — please type your command instead.]"


# ---------------------------------------------------------------------------
#  Command handler
# ---------------------------------------------------------------------------

def handle_message(
    message: str,
    history: list,
    image_state: str | None,
) -> tuple[str, str | None]:
    """
    Process a text command through the LLM agent.
    Returns (response_text, image_path_or_None).
    """
    if not message.strip():
        return "Please enter a command.", image_state

    try:
        result = process_command(message)
    except Exception as exc:
        logger.error("Error processing command: %s", exc, exc_info=True)
        return f"❌ Error: {exc}", image_state

    # Check if the result contains an image path
    img_path = _extract_image_path(result)
    if img_path:
        image_state = img_path

    return result, image_state


def handle_voice(audio_path: str, history: list, image_state: str | None):
    """Transcribe voice input and process as a command."""
    if not audio_path:
        return "No audio received.", history, image_state

    text = _transcribe_audio(audio_path)
    if not text or text.startswith("[Could not"):
        return text, history, image_state

    # Process the transcribed command
    response, image_state = handle_message(text, history, image_state)
    return f"🎤 *\"{text}\"*\n\n{response}", history, image_state


def handle_quick_action(action: str, history: list, image_state: str | None):
    """Handle quick-action button clicks."""
    response, image_state = handle_message(action, history, image_state)
    return response, image_state


# ---------------------------------------------------------------------------
#  UI builder
# ---------------------------------------------------------------------------

def build_ui() -> gr.Blocks:
    with gr.Blocks(
        title="🏭 Factory Guardian",
        theme=gr.themes.Soft(primary_hue="orange", secondary_hue="blue"),
        css="""
        .header { text-align: center; padding: 10px; }
        .status-bar { padding: 8px 12px; border-radius: 8px;
                      background: #1a1a2e; color: #e0e0e0; font-family: monospace; }
        """,
    ) as demo:

        # Header
        gr.Markdown(
            """
            <div class="header">
            <h1>🏭 Factory Guardian</h1>
            <p><em>AI-powered safety patrol robot — speak or type commands</em></p>
            </div>
            """,
        )

        # State for the latest image
        image_state = gr.State(value=None)

        with gr.Row():
            # ── Left column: Chat ──
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(
                    height=420,
                    label="Command Log",
                    placeholder="Factory Guardian is ready for commands…",
                )
                with gr.Row():
                    text_input = gr.Textbox(
                        placeholder="e.g. 'move forward', 'run safety inspection', 'take a photo'…",
                        label="Command",
                        scale=4,
                        lines=1,
                    )
                    send_btn = gr.Button("Send", variant="primary", scale=1)

                # Voice input
                audio_input = gr.Audio(
                    sources=["microphone"],
                    type="filepath",
                    label="🎤 Voice Command (click to record)",
                )

            # ── Right column: Image + Status ──
            with gr.Column(scale=2):
                image_display = gr.Image(
                    label="📸 Camera / Detection View",
                    height=300,
                )
                status_display = gr.Markdown(
                    value=hardware_bridge.get_status_report(),
                    label="Robot Status",
                    elem_classes=["status-bar"],
                )

                # Quick action buttons
                gr.Markdown("### ⚡ Quick Actions")
                with gr.Row():
                    gr.Button("⬆️ Forward").click(
                        fn=lambda h, s: handle_quick_action("move forward for 2 seconds", h, s),
                        inputs=[chatbot, image_state],
                        outputs=[chatbot, image_state],
                    )
                    gr.Button("⬇️ Back").click(
                        fn=lambda h, s: handle_quick_action("move backward for 2 seconds", h, s),
                        inputs=[chatbot, image_state],
                        outputs=[chatbot, image_state],
                    )
                with gr.Row():
                    gr.Button("⬅️ Left").click(
                        fn=lambda h, s: handle_quick_action("turn left", h, s),
                        inputs=[chatbot, image_state],
                        outputs=[chatbot, image_state],
                    )
                    gr.Button("➡️ Right").click(
                        fn=lambda h, s: handle_quick_action("turn right", h, s),
                        inputs=[chatbot, image_state],
                        outputs=[chatbot, image_state],
                    )
                with gr.Row():
                    gr.Button("🛑 Stop", variant="stop").click(
                        fn=lambda h, s: handle_quick_action("stop the robot", h, s),
                        inputs=[chatbot, image_state],
                        outputs=[chatbot, image_state],
                    )
                    gr.Button("🔍 Inspect", variant="secondary").click(
                        fn=lambda h, s: handle_quick_action("run a safety inspection", h, s),
                        inputs=[chatbot, image_state],
                        outputs=[chatbot, image_state],
                    )

        # ── Examples ──
        gr.Examples(
            examples=[
                "Move forward for 3 seconds",
                "Turn left and then move forward",
                "Run a safety inspection",
                "Take a photo",
                "What's the robot status?",
                "Patrol forward, turn right, move forward, then scan for hazards",
                "Stop the robot",
            ],
            inputs=text_input,
            label="💡 Example Commands",
        )

        # ── Event wiring ──

        def chat_respond(message, history, img_state):
            response, img_state = handle_message(message, history, img_state)
            history = history or []
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": response})
            img = img_state if img_state and os.path.isfile(str(img_state)) else None
            status = hardware_bridge.get_status_report()
            return history, "", img, status, img_state

        send_btn.click(
            fn=chat_respond,
            inputs=[text_input, chatbot, image_state],
            outputs=[chatbot, text_input, image_display, status_display, image_state],
        )
        text_input.submit(
            fn=chat_respond,
            inputs=[text_input, chatbot, image_state],
            outputs=[chatbot, text_input, image_display, status_display, image_state],
        )

        def voice_respond(audio_path, history, img_state):
            if not audio_path:
                return history, None, hardware_bridge.get_status_report(), img_state
            response, history, img_state = handle_voice(audio_path, history, img_state)
            history = history or []
            history.append({"role": "user", "content": "🎤 [Voice command]"})
            history.append({"role": "assistant", "content": response})
            img = img_state if img_state and os.path.isfile(str(img_state)) else None
            status = hardware_bridge.get_status_report()
            return history, img, status, img_state

        audio_input.stop_recording(
            fn=voice_respond,
            inputs=[audio_input, chatbot, image_state],
            outputs=[chatbot, image_display, status_display, image_state],
        )

    return demo


# ---------------------------------------------------------------------------
#  Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ui = build_ui()
    ui.launch(
        server_name=settings.gradio_server_name,
        server_port=settings.gradio_server_port,
    )

"""
Camera tools — frame capture for Factory Guardian.

Provides a single tool:
    capture_frame()  →  captures a frame from the configured camera source
                        (webcam, RTSP stream, or mock placeholder).

The captured frame is saved as a timestamped JPEG in a temp directory
and the path is returned for display in Gradio or further processing.
"""

import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

from settings import settings

logger = logging.getLogger(__name__)

# Directory for captured frames (persists across calls within a session)
CAPTURE_DIR = Path(tempfile.gettempdir()) / "factory_guardian" / "captures"
CAPTURE_DIR.mkdir(parents=True, exist_ok=True)


def _generate_mock_frame():
    """
    Create a synthetic placeholder image when no real camera is available.
    Returns a numpy array (BGR, 640×480) with a status overlay.
    """
    try:
        import numpy as np
        # Dark factory-themed background
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:] = (40, 35, 30)  # dark grey-brown

        # Try to draw text overlay using OpenCV
        try:
            import cv2
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, "FACTORY GUARDIAN", (120, 180),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 200, 255), 2)
            cv2.putText(frame, "[MOCK CAMERA FEED]", (150, 230),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 1)
            cv2.putText(frame, timestamp, (180, 280),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 180, 0), 1)
            # Simulated detection boxes for demo
            cv2.rectangle(frame, (50, 300), (200, 460), (0, 255, 255), 2)
            cv2.putText(frame, "person", (55, 295),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            cv2.rectangle(frame, (400, 320), (580, 450), (0, 0, 255), 2)
            cv2.putText(frame, "no_helmet", (405, 315),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        except ImportError:
            pass  # numpy-only fallback: plain dark frame

        return frame
    except ImportError:
        logger.warning("numpy not available — returning None for mock frame")
        return None


def _capture_from_camera():
    """
    Capture a single frame from the configured camera source.
    Returns a numpy array (BGR) or None on failure.
    """
    try:
        import cv2
    except ImportError:
        logger.warning("opencv not installed — falling back to mock frame")
        return _generate_mock_frame()

    # Determine source: URL overrides index
    source = settings.camera_url if settings.camera_url else settings.camera_index

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        logger.warning("Cannot open camera '%s' — using mock frame", source)
        return _generate_mock_frame()

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.camera_frame_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.camera_frame_height)

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        logger.warning("Failed to read frame — using mock frame")
        return _generate_mock_frame()

    return frame


# ---------------------------------------------------------------------------
#  Tool implementation
# ---------------------------------------------------------------------------

def capture_frame() -> str:
    """
    Capture a frame from the camera (or generate a mock) and save it.
    Returns the file path of the saved JPEG image.
    """
    if settings.mock_mode:
        logger.info("[MOCK] Capturing simulated camera frame")
        frame = _generate_mock_frame()
    else:
        logger.info("Capturing frame from camera")
        frame = _capture_from_camera()

    if frame is None:
        return "⚠️ Failed to capture frame — no camera or numpy available."

    # Save frame to disk
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"frame_{timestamp}.jpg"
    filepath = str(CAPTURE_DIR / filename)

    try:
        import cv2
        cv2.imwrite(filepath, frame)
    except ImportError:
        # Fallback: save raw bytes via PIL if available
        try:
            from PIL import Image
            import numpy as np
            img = Image.fromarray(frame[:, :, ::-1])  # BGR → RGB
            img.save(filepath)
        except ImportError:
            return "⚠️ Cannot save frame — neither opencv nor Pillow installed."

    logger.info("Frame saved → %s", filepath)
    return filepath


# ---------------------------------------------------------------------------
#  Tool registry
# ---------------------------------------------------------------------------

CAMERA_TOOLS: dict = {
    "capture_frame": capture_frame,
}

CAMERA_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "capture_frame",
            "description": (
                "Capture a single frame from the robot's camera and save it. "
                "Returns the file path of the captured image. "
                "Use when the user says 'take a photo', 'capture image', "
                "'what do you see?', 'show me the camera', etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]

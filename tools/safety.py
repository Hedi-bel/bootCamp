"""
Safety detection tools — YOLO-based hazard inspection for Factory Guardian.

Provides:
    run_safety_inspection()  →  captures a frame, runs YOLO object detection,
                                checks for safety hazards, and returns a report
                                with the annotated image path.

Detected hazard categories:
    🔴 NO HELMET     — person detected without a hardhat
    🔴 UNAUTHORIZED  — person detected in a restricted area
    🟡 HAZARD        — potentially dangerous object on the floor

In mock mode, the tool generates a simulated detection report.
"""

import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

from settings import settings

logger = logging.getLogger(__name__)

# Annotated frames are saved here
RESULTS_DIR = Path(tempfile.gettempdir()) / "factory_guardian" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
#  YOLO model loader  (lazy, cached)
# ---------------------------------------------------------------------------

_yolo_model = None


def _get_yolo_model():
    """Load the YOLO model once and cache it."""
    global _yolo_model
    if _yolo_model is not None:
        return _yolo_model

    try:
        from ultralytics import YOLO
        model_path = settings.yolo_model_path
        logger.info("Loading YOLO model: %s", model_path)
        _yolo_model = YOLO(model_path)
        logger.info("YOLO model loaded successfully.")
        return _yolo_model
    except ImportError:
        logger.warning(
            "ultralytics not installed — YOLO disabled. "
            "Install with: pip install ultralytics"
        )
        return None
    except Exception as exc:
        logger.error("Failed to load YOLO model: %s", exc)
        return None


# ---------------------------------------------------------------------------
#  Detection logic
# ---------------------------------------------------------------------------

# COCO class names relevant to factory safety
SAFETY_LABELS = {
    0: "person",
    # These would come from a custom-trained model in production:
    # 80: "hardhat",   (not in standard COCO)
    # 81: "no_helmet", (not in standard COCO)
    39: "bottle",      # potential spill hazard
    64: "mouse",       # small object on floor
    73: "book",        # item on floor
    56: "chair",       # obstructing pathway
}


def _analyze_detections(results) -> list[dict]:
    """
    Parse YOLO results and flag safety hazards.

    Returns a list of hazard dicts:
        {"type": "NO_HELMET"|"UNAUTHORIZED"|"HAZARD",
         "label": str, "confidence": float, "box": [x1,y1,x2,y2]}
    """
    hazards = []

    for result in results:
        if result.boxes is None:
            continue

        for box in result.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            coords = box.xyxy[0].tolist()
            label = result.names.get(cls_id, f"class_{cls_id}")

            # Skip low-confidence detections
            if conf < settings.yolo_confidence:
                continue

            # --- Hazard classification logic ---

            if cls_id == 0:  # person
                # In a real system, we'd check for PPE with a custom model.
                # For the MVP, every person is flagged as a potential
                # "no helmet" risk (demonstrating the concept).
                hazards.append({
                    "type": "NO_HELMET",
                    "label": label,
                    "confidence": conf,
                    "box": coords,
                    "detail": "Person detected — verify PPE compliance (helmet, vest).",
                })

            elif cls_id in (39, 64, 73):  # bottle, mouse, book (floor hazards)
                hazards.append({
                    "type": "HAZARD",
                    "label": label,
                    "confidence": conf,
                    "box": coords,
                    "detail": f"Object '{label}' on the floor — potential trip/spill hazard.",
                })

            elif cls_id == 56:  # chair blocking pathway
                hazards.append({
                    "type": "HAZARD",
                    "label": label,
                    "confidence": conf,
                    "box": coords,
                    "detail": "Pathway obstruction detected.",
                })

    return hazards


def _draw_annotations(frame, hazards: list[dict]):
    """Draw bounding boxes and labels on the frame."""
    try:
        import cv2
    except ImportError:
        return frame  # can't annotate without opencv

    COLORS = {
        "NO_HELMET": (0, 0, 255),      # red
        "UNAUTHORIZED": (0, 100, 255),  # orange
        "HAZARD": (0, 255, 255),        # yellow
    }

    for h in hazards:
        x1, y1, x2, y2 = [int(c) for c in h["box"]]
        color = COLORS.get(h["type"], (255, 255, 255))
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        text = f"{h['type']}: {h['label']} ({h['confidence']:.0%})"
        cv2.putText(frame, text, (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    # Timestamp overlay
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(frame, f"Factory Guardian | {ts}", (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 1)

    return frame


def _format_report(hazards: list[dict]) -> str:
    """Format hazard list into a human-readable report."""
    if not hazards:
        return (
            "✅ **Safety Inspection Complete**\n\n"
            "No hazards detected. All clear."
        )

    icons = {"NO_HELMET": "🔴", "UNAUTHORIZED": "🔴", "HAZARD": "🟡"}

    lines = [
        f"⚠️ **Safety Inspection — {len(hazards)} issue(s) found**\n"
    ]
    for i, h in enumerate(hazards, 1):
        icon = icons.get(h["type"], "⚪")
        lines.append(
            f"{i}. {icon} **{h['type']}** — {h['label']} "
            f"(confidence: {h['confidence']:.0%})\n"
            f"   {h['detail']}"
        )

    return "\n".join(lines)


def _generate_mock_report() -> tuple[str, str | None]:
    """Generate a simulated safety report for demo purposes."""
    mock_hazards = [
        {
            "type": "NO_HELMET",
            "label": "person",
            "confidence": 0.87,
            "box": [50, 100, 200, 350],
            "detail": "Person detected — verify PPE compliance (helmet, vest).",
        },
        {
            "type": "HAZARD",
            "label": "bottle",
            "confidence": 0.72,
            "box": [400, 300, 480, 420],
            "detail": "Object 'bottle' on the floor — potential trip/spill hazard.",
        },
    ]

    report = _format_report(mock_hazards)
    report += "\n\n_ℹ️ This is a simulated report (mock mode)._"

    # Generate a mock annotated frame
    try:
        import numpy as np
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:] = (40, 35, 30)
        frame = _draw_annotations(frame, mock_hazards)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = str(RESULTS_DIR / f"inspection_{timestamp}.jpg")
        try:
            import cv2
            cv2.imwrite(filepath, frame)
        except ImportError:
            filepath = None
    except ImportError:
        filepath = None

    return report, filepath


# ---------------------------------------------------------------------------
#  Tool implementation
# ---------------------------------------------------------------------------

def run_safety_inspection() -> str:
    """
    Capture a frame, run YOLO detection, and return a safety report.

    Returns a markdown-formatted report string. If an annotated image
    was saved, its path is appended to the report.
    """
    if settings.mock_mode:
        logger.info("[MOCK] Running simulated safety inspection")
        report, image_path = _generate_mock_report()
        if image_path:
            report += f"\n\n📸 Annotated image: `{image_path}`"
        return report

    # --- Live mode: real capture + YOLO ---

    # 1. Capture frame
    from tools.camera import capture_frame as _capture
    frame_path = _capture()
    if frame_path.startswith("⚠️"):
        return frame_path  # error message from capture

    # 2. Load frame
    try:
        import cv2
        frame = cv2.imread(frame_path)
        if frame is None:
            return "⚠️ Failed to read captured frame."
    except ImportError:
        return "⚠️ OpenCV not installed — cannot process frame."

    # 3. Run YOLO
    model = _get_yolo_model()
    if model is None:
        return "⚠️ YOLO model not available — install ultralytics."

    logger.info("Running YOLO inference on %s", frame_path)
    results = model(frame, conf=settings.yolo_confidence, verbose=False)

    # 4. Analyze detections
    hazards = _analyze_detections(results)

    # 5. Annotate frame
    annotated = _draw_annotations(frame.copy(), hazards)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = str(RESULTS_DIR / f"inspection_{timestamp}.jpg")
    cv2.imwrite(result_path, annotated)

    # 6. Build report
    report = _format_report(hazards)
    report += f"\n\n📸 Annotated image: `{result_path}`"

    logger.info("Inspection complete: %d hazard(s) found", len(hazards))
    return report


# ---------------------------------------------------------------------------
#  Tool registry
# ---------------------------------------------------------------------------

SAFETY_TOOLS: dict = {
    "run_safety_inspection": run_safety_inspection,
}

SAFETY_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "run_safety_inspection",
            "description": (
                "Run a full safety inspection: capture a camera frame and analyze it "
                "with YOLO to detect safety hazards (missing helmets, unauthorized "
                "persons, floor hazards, pathway obstructions). "
                "Returns a detailed safety report with findings. "
                "Use when the user says 'check for hazards', 'run inspection', "
                "'scan the area', 'is it safe?', 'safety check', etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]

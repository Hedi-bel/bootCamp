# 🏭 Factory Guardian

**AI-powered mobile robot for factory safety patrol** — understands natural language commands, navigates the factory floor, captures camera images, and detects safety hazards with YOLO in real time.

Built on top of the [esprit-workshop](https://github.com/fayezzouari/esprit-workshop) architecture.

---

## Features

| Feature | Description |
|---------|-------------|
| 💬 **Text Commands** | Type natural language commands in the chat |
| 🎤 **Voice Commands** | Record voice commands (Whisper transcription) |
| 🤖 **Robot Movement** | Forward, backward, left, right, stop |
| 📸 **Camera Capture** | Take photos from webcam or RTSP stream |
| 🔍 **Safety Inspection** | YOLO-based hazard detection with annotated images |
| 📊 **Real-time Status** | Live robot status in the dashboard |
| 🧪 **Mock Mode** | Full demo without any hardware connected |

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/fayezzouari/esprit-workshop.git
cd esprit-workshop

# Create virtual environment (recommended)
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
# source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure

```bash
copy .env.example .env
# Edit .env and set your GROQ_API_KEY
```

> **Minimum required**: Only `GROQ_API_KEY` is needed. Everything else has sensible defaults.

### 3. Run

```bash
python app.py
```

Open **http://localhost:7860** in your browser.

---

## Demo Scenario (3 minutes)

Use this script for a live hackathon demo:

1. **Open the UI** at `http://localhost:7860`
2. **Move the robot**: Type `"Move forward for 3 seconds"` → see movement logged
3. **Safety inspection**: Type `"Run a safety inspection"` → YOLO results + annotated image
4. **Compound command**: Type `"Turn left, move forward, then scan for hazards"` → agent chains 3 tools
5. **Voice command**: Click the microphone and say `"Stop the robot"` → voice transcribed + stop executed
6. **Quick buttons**: Click ⬆️ Forward, ⬅️ Left, 🔍 Inspect buttons
7. **Check status**: Type `"What's the robot status?"` → status report

---

## Project Structure

```
esprit-workshop/
├── app.py                  # Gradio web UI (entry point)
├── agent.py                # LLM agent (Groq + tool calling)
├── hardware_bridge.py      # Mock-friendly hardware bridge (MQTT/ROS stubs)
├── settings.py             # Configuration (pydantic-settings + .env)
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── tools/
│   ├── __init__.py         # Tool registry
│   ├── robot.py            # Movement tools (forward/back/left/right/stop)
│   ├── camera.py           # Camera capture tool
│   └── safety.py           # YOLO safety inspection tool
├── ros_bridge_legacy.py    # Original ROS 2 bridge (preserved)
└── docker/                 # Docker config for micro-ROS agent (preserved)
```

---

## Configuration

All settings are in `.env` (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | — | **Required.** Groq API key for LLM |
| `MOCK_MODE` | `true` | Set to `false` for real hardware |
| `MQTT_BROKER` | `localhost` | ESP32 MQTT broker address |
| `CAMERA_INDEX` | `0` | Webcam index (0 = default) |
| `CAMERA_URL` | — | RTSP/HTTP camera stream URL |
| `YOLO_MODEL_PATH` | `yolov8n.pt` | YOLO model (auto-downloaded) |
| `YOLO_CONFIDENCE` | `0.40` | Detection confidence threshold |

---

## Architecture

```
User (text/voice)
  │
  ▼
┌─────────────┐    ┌──────────────┐    ┌──────────────────┐
│  Gradio UI  │───▶│  LLM Agent   │───▶│  Tool Registry   │
│  (app.py)   │    │  (agent.py)  │    │  (tools/*.py)    │
└─────────────┘    └──────────────┘    └────────┬─────────┘
                                                │
                          ┌─────────────────────┼───────────────┐
                          ▼                     ▼               ▼
                   ┌────────────┐     ┌──────────────┐  ┌────────────┐
                   │  Movement  │     │   Camera     │  │  Safety    │
                   │  (MQTT)    │     │  (OpenCV)    │  │  (YOLO)    │
                   └────────────┘     └──────────────┘  └────────────┘
```

---

## Future Work

- 🔧 Real ESP32 MQTT firmware integration
- 🤖 Full ROS 2 navigation (uncomment `ros_bridge_legacy.py`)
- 🎯 Custom YOLO model fine-tuned for PPE (hardhats, vests)
- 🗺️ Restricted zone mapping and geofencing
- 💾 Persistent incident logging to database
- 📱 Mobile app companion

---

## License

See the original repository for license terms.

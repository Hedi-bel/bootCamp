"""
Factory Guardian — centralised configuration.

All values can be overridden via environment variables or a .env file.
Pydantic-settings loads them automatically (case-insensitive).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ──────────────────────────────────────────────────────────────────
    #  LLM / Groq
    # ──────────────────────────────────────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "groq/llama3-groq-70b-8192-tool-use-preview"

    # ──────────────────────────────────────────────────────────────────
    #  Robot identity
    # ──────────────────────────────────────────────────────────────────
    robot_name: str = "factory_guardian"

    # ──────────────────────────────────────────────────────────────────
    #  Simulation / Mock mode
    # ──────────────────────────────────────────────────────────────────
    # When True, all hardware interactions are simulated (no MQTT/ROS).
    # Set MOCK_MODE=false in .env to use real hardware.
    mock_mode: bool = True

    # ──────────────────────────────────────────────────────────────────
    #  MQTT  (ESP32 motor control)
    # ──────────────────────────────────────────────────────────────────
    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    mqtt_topic_motor: str = "factory_guardian/motor"
    mqtt_topic_status: str = "factory_guardian/status"
    mqtt_topic_action_done: str = "factory_guardian/action_done"

    # ──────────────────────────────────────────────────────────────────
    #  Camera
    # ──────────────────────────────────────────────────────────────────
    # Index of local webcam (0 = default) or an RTSP/HTTP stream URL.
    camera_index: int = 0
    camera_url: str = ""              # overrides camera_index when set
    camera_frame_width: int = 640
    camera_frame_height: int = 480

    # ──────────────────────────────────────────────────────────────────
    #  YOLO / Safety detection
    # ──────────────────────────────────────────────────────────────────
    yolo_model_path: str = "yolov8n.pt"       # auto-downloaded by ultralytics
    yolo_confidence: float = 0.40             # minimum detection confidence
    # COCO class IDs relevant to factory safety
    # 0 = person (for helmet/PPE checks and unauthorized presence)
    yolo_safety_classes: str = "0"            # comma-separated COCO class IDs

    # ──────────────────────────────────────────────────────────────────
    #  Speed constraints  (kept for backward compat)
    # ──────────────────────────────────────────────────────────────────
    robot_default_speed: float = 0.3   # m/s
    robot_max_speed: float = 1.0       # m/s

    # ──────────────────────────────────────────────────────────────────
    #  Legacy ROS 2  (preserved for future hardware integration)
    # ──────────────────────────────────────────────────────────────────
    ros_domain_id: int = 0
    cmd_set_position: float = 1.0
    cmd_go_to: float = 2.0
    service_timeout_sec: float = 3.0

    # ──────────────────────────────────────────────────────────────────
    #  Gradio UI
    # ──────────────────────────────────────────────────────────────────
    gradio_server_name: str = "0.0.0.0"
    gradio_server_port: int = 7860

    # ──────────────────────────────────────────────────────────────────
    #  Derived topic / service names  (legacy ROS 2 compat)
    # ──────────────────────────────────────────────────────────────────
    @property
    def topic_strategy(self) -> str:
        return f"{self.robot_name}/strategy"

    @property
    def topic_start(self) -> str:
        return f"{self.robot_name}/start"

    @property
    def topic_action_done(self) -> str:
        return f"{self.robot_name}/action_done"

    @property
    def service_status(self) -> str:
        return f"{self.robot_name}/status"

    # ──────────────────────────────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────────────────────────────
    @property
    def safety_class_ids(self) -> list[int]:
        """Parse the comma-separated YOLO class IDs into a list of ints."""
        return [int(c.strip()) for c in self.yolo_safety_classes.split(",") if c.strip()]


settings = Settings()

"""
COMPASS Configuration
Structured application settings using Pydantic.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    app_name: str = "COMPASS"
    app_version: str = "2.0.0"
    environment: str = "development"
    debug: bool = False

    # Server network binding
    host: str = "127.0.0.1"
    port: int = 8000

    # CORS
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    # Storage & Persistence
    storage_dir: Path = ROOT_DIR / "storage"
    database_path: Path = ROOT_DIR / "storage" / "compass.db"

    # Logging
    logs_dir: Path = ROOT_DIR / "logs"
    log_file: Path = ROOT_DIR / "logs" / "compass.log"
    log_level: str = "INFO"

    # Overlay Settings
    overlay_enabled: bool = True
    overlay_click_through: bool = True

    # Phase 2: Perception & Automation
    captures_dir: Path = ROOT_DIR / "storage" / "captures"
    uia_max_depth: int = 3
    uia_max_elements: int = 200
    uia_timeout_sec: float = 5.0
    perception_poll_interval_sec: float = 0.5
    capture_enabled: bool = True
    action_foreground_check: bool = True  # Require target in foreground


settings = Settings()

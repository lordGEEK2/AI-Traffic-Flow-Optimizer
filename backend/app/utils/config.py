"""
config.py — Centralized Configuration
=======================================
Loads environment variables from .env and provides typed accessors.
Validates critical settings at startup.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load .env from project root (two levels up from this file)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"

if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)
else:
    # Try backend-level .env
    _BACKEND_ENV = Path(__file__).resolve().parent.parent.parent / ".env"
    if _BACKEND_ENV.exists():
        load_dotenv(_BACKEND_ENV)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int = 0) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _env_float(key: str, default: float = 0.0) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key, str(default)).lower()
    return val in ("true", "1", "yes")


# ===========================================================================
# Video Source
# ===========================================================================
VIDEO_SOURCE_MODE: str = _env("VIDEO_SOURCE_MODE", "simulation")  # webcam | rtsp | video_file | simulation
VIDEO_SOURCE: str = _env("VIDEO_SOURCE", "sample_videos/traffic_sample.mp4")
WEBCAM_INDEX: int = _env_int("WEBCAM_INDEX", 0)
RTSP_URL: str = _env("RTSP_URL", "")
RTSP_TIMEOUT: int = _env_int("RTSP_TIMEOUT", 10)
TARGET_FPS: float = _env_float("TARGET_FPS", 15.0)

# ===========================================================================
# YOLO / Detection
# ===========================================================================
YOLO_MODEL: str = _env("YOLO_MODEL", "yolov8n.pt")
YOLO_CONFIDENCE: float = _env_float("YOLO_CONFIDENCE", 0.4)

# ===========================================================================
# Emergency Detection
# ===========================================================================
EMERGENCY_CONFIDENCE: float = _env_float("EMERGENCY_CONFIDENCE", 0.5)
EMERGENCY_MIN_FRAMES: int = _env_int("EMERGENCY_MIN_FRAMES", 5)
EMERGENCY_CONF_THRESHOLD: float = _env_float("EMERGENCY_CONF_THRESHOLD", 0.6)

# ===========================================================================
# Density Analysis
# ===========================================================================
DENSITY_THRESHOLD: int = _env_int("DENSITY_THRESHOLD", 60)
EMA_ALPHA: float = _env_float("EMA_ALPHA", 0.3)
STABILITY_WINDOW: int = _env_int("STABILITY_WINDOW", 3)  # seconds

# ===========================================================================
# Signal Timing
# ===========================================================================
BASE_GREEN_TIME: int = _env_int("BASE_GREEN_TIME", 30)
MAX_GREEN_TIME: int = _env_int("MAX_GREEN_TIME", 90)
MIN_GREEN_TIME: int = _env_int("MIN_GREEN_TIME", 10)
YELLOW_TIME: int = _env_int("YELLOW_TIME", 5)
ALL_RED_TIME: int = _env_int("ALL_RED_TIME", 2)
MAX_CYCLE_TIME: int = _env_int("MAX_CYCLE_TIME", 180)

# ===========================================================================
# Server
# ===========================================================================
BACKEND_HOST: str = _env("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT: int = _env_int("BACKEND_PORT", 8000)
FRONTEND_URL: str = _env("FRONTEND_URL", "http://localhost:5173")
WS_INTERVAL_MS: int = _env_int("WS_INTERVAL_MS", 500)

# ===========================================================================
# Simulation
# ===========================================================================
SIMULATION_MODE: bool = _env_bool("SIMULATION_MODE", True)

# ===========================================================================
# Logging
# ===========================================================================
LOG_LEVEL: str = _env("LOG_LEVEL", "INFO").upper()

# ===========================================================================
# Lane Config Path
# ===========================================================================
LANE_CONFIG_PATH: str = _env(
    "LANE_CONFIG_PATH",
    str(Path(__file__).resolve().parent.parent.parent / "config" / "lane_config.json")
)

# ===========================================================================
# Database
# ===========================================================================
DB_PATH: str = _env(
    "DB_PATH",
    str(Path(__file__).resolve().parent.parent.parent / "data" / "traffic.db")
)
DB_WRITE_INTERVAL: int = _env_int("DB_WRITE_INTERVAL", 5)  # write every N ticks

# ===========================================================================
# Audit trail
# ===========================================================================
SIGNAL_STATE_LOG_PATH: str = _env(
    "SIGNAL_STATE_LOG_PATH",
    str(Path(__file__).resolve().parent.parent.parent / "data" / "signal_state.json")
)

# ===========================================================================
# Logger Setup
# ===========================================================================
def setup_logging() -> logging.Logger:
    """Configure the root logger with structured format."""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("traffic-ai")
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    return logger


# ===========================================================================
# Lane Config Loader
# ===========================================================================
def load_lane_config() -> Dict[str, Any]:
    """Load lane polygon configuration from JSON file."""
    config_path = Path(LANE_CONFIG_PATH)
    if not config_path.exists():
        logging.getLogger("traffic-ai.config").warning(
            "Lane config not found at %s. Using defaults.", config_path
        )
        return {
            "frame_width": 1280,
            "frame_height": 720,
            "lanes": [
                {"id": "NORTH", "polygon": [[540,0],[740,0],[700,320],[580,320]], "signal_group": "NS"},
                {"id": "SOUTH", "polygon": [[540,720],[740,720],[700,400],[580,400]], "signal_group": "NS"},
                {"id": "EAST", "polygon": [[1280,300],[1280,420],[760,380],[760,340]], "signal_group": "EW"},
                {"id": "WEST", "polygon": [[0,300],[0,420],[520,380],[520,340]], "signal_group": "EW"},
            ],
        }
    with open(config_path, "r") as f:
        data = json.load(f)
    logging.getLogger("traffic-ai.config").info(
        "Loaded lane config: %d lanes from %s", len(data.get("lanes", [])), config_path
    )
    return data


# ===========================================================================
# Startup Validation
# ===========================================================================
def validate_config() -> List[str]:
    """Validate configuration at startup. Returns list of warnings."""
    warnings = []
    if MIN_GREEN_TIME >= MAX_GREEN_TIME:
        warnings.append(f"MIN_GREEN_TIME ({MIN_GREEN_TIME}) >= MAX_GREEN_TIME ({MAX_GREEN_TIME})")
    if BASE_GREEN_TIME > MAX_GREEN_TIME:
        warnings.append(f"BASE_GREEN_TIME ({BASE_GREEN_TIME}) > MAX_GREEN_TIME ({MAX_GREEN_TIME})")
    if YELLOW_TIME < 3:
        warnings.append(f"YELLOW_TIME ({YELLOW_TIME}) is below recommended minimum of 3s")
    if WS_INTERVAL_MS < 100:
        warnings.append(f"WS_INTERVAL_MS ({WS_INTERVAL_MS}) is very low, may cause performance issues")
    if VIDEO_SOURCE_MODE == "rtsp" and not RTSP_URL:
        warnings.append("VIDEO_SOURCE_MODE=rtsp but RTSP_URL is empty")
    if EMERGENCY_MIN_FRAMES < 1:
        warnings.append("EMERGENCY_MIN_FRAMES must be >= 1")
    return warnings


logger = setup_logging()

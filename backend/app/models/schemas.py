"""
schemas.py — Pydantic Data Models
===================================
Defines all data transfer objects for the API, WebSocket, and
internal communication between modules.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class DensityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class VideoSourceMode(str, Enum):
    WEBCAM = "webcam"
    RTSP = "rtsp"
    VIDEO_FILE = "video_file"
    SIMULATION = "simulation"


# ---------------------------------------------------------------------------
# Video Source
# ---------------------------------------------------------------------------
class VideoSourceStats(BaseModel):
    mode: str = "simulation"
    healthy: bool = True
    frames_read: int = 0
    frames_dropped: int = 0
    reconnections: int = 0
    fps_actual: float = 0.0
    source_width: int = 0
    source_height: int = 0
    uptime_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
class VehicleInfo(BaseModel):
    vehicle_class: str = Field("car", alias="class")
    confidence: float = 0.0
    bbox: List[int] = []

    class Config:
        populate_by_name = True


class LaneDetection(BaseModel):
    lane_id: str = ""
    vehicle_count: int = 0
    density_score: float = 0.0
    raw_density: float = 0.0
    smoothed_density: float = 0.0
    level: str = "low"
    trend: str = "stable"


class DetectionResult(BaseModel):
    total_vehicles: int = 0
    lanes: List[LaneDetection] = []
    vehicle_types: Dict[str, int] = {}
    fps: float = 0.0
    frame_count: int = 0


# ---------------------------------------------------------------------------
# Signal State
# ---------------------------------------------------------------------------
class DirectionSignal(BaseModel):
    state: str = "RED"
    countdown: float = 0.0
    density: float = 0.0


class IntersectionState(BaseModel):
    intersection_id: str = "INT-001"
    signals: Dict[str, DirectionSignal] = {}
    current_phase: str = ""
    phase_stage: str = ""
    cycle_time: float = 0.0
    emergency_active: bool = False
    emergency_direction: Optional[str] = None


# ---------------------------------------------------------------------------
# Emergency / Corridor
# ---------------------------------------------------------------------------
class EmergencyStatus(BaseModel):
    emergency_detected: bool = False
    vehicle_type: str = ""
    lane_id: str = ""
    confidence: float = 0.0
    confirmation_frames: int = 0


class CorridorStatus(BaseModel):
    active: bool = False
    direction: Optional[str] = None
    vehicle_type: Optional[str] = None
    duration: float = 0.0
    corridor_path: List[str] = []
    cooldown_remaining: float = 0.0


# ---------------------------------------------------------------------------
# Dashboard Payload (WebSocket)
# ---------------------------------------------------------------------------
class DashboardPayload(BaseModel):
    timestamp: str = ""
    detection: DetectionResult = DetectionResult()
    density: Dict[str, Any] = {}
    intersection: IntersectionState = IntersectionState()
    corridor: CorridorStatus = CorridorStatus()
    video_source: VideoSourceStats = VideoSourceStats()
    alerts: List[Dict[str, Any]] = []
    system_health: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# API Responses
# ---------------------------------------------------------------------------
class StatusResponse(BaseModel):
    status: str = "running"
    version: str = "2.0.0"
    simulation_mode: bool = True
    video_mode: str = "simulation"
    uptime_seconds: float = 0.0
    video_healthy: bool = True
    database_connected: bool = False
    active_ws_connections: int = 0


class HealthResponse(BaseModel):
    healthy: bool = True
    checks: Dict[str, bool] = {}
    warnings: List[str] = []


class SystemConfig(BaseModel):
    video_source_mode: str = "simulation"
    density_threshold: int = 60
    base_green_time: int = 30
    max_green_time: int = 90
    min_green_time: int = 10
    yellow_time: int = 5
    all_red_time: int = 2
    max_cycle_time: int = 180
    ws_interval_ms: int = 500
    emergency_min_frames: int = 5
    emergency_conf_threshold: float = 0.6
    yolo_model: str = "yolov8n.pt"
    yolo_confidence: float = 0.4
    simulation_mode: bool = True

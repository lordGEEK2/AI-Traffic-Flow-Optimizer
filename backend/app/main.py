"""
main.py -- FastAPI Application (ITMS Traffic Platform v4.0)
============================================================
Multi-lane video upload + YOLOv8 annotated streaming + ambulance priority.

Core flow:
  1. User uploads 4 lane videos via /api/upload
  2. /api/start-processing begins round-robin YOLOv8 analysis
  3. Annotated frames served via /api/frames/{lane_id}
  4. Per-lane stats via /api/lane-stats, efficiency via /api/efficiency
  5. WebSocket for real-time dashboard updates
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Optional, Set

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .utils.config import (
    BACKEND_HOST, BACKEND_PORT, FRONTEND_URL, WS_INTERVAL_MS,
    SIMULATION_MODE, TARGET_FPS,
    DENSITY_THRESHOLD, BASE_GREEN_TIME, MAX_GREEN_TIME, MIN_GREEN_TIME,
    YELLOW_TIME, ALL_RED_TIME, MAX_CYCLE_TIME,
    EMERGENCY_MIN_FRAMES, EMERGENCY_CONF_THRESHOLD,
    YOLO_MODEL, YOLO_CONFIDENCE,
    DB_PATH, DB_WRITE_INTERVAL,
    validate_config, load_lane_config,
)
from .utils.database import Database
from .cv_engine.vehicle_detector import VehicleDetector
from .cv_engine.emergency_detector import EmergencyDetector
from .cv_engine.density_analyzer import DensityAnalyzer
from .cv_engine.frame_streamer import FrameStreamer
from .signal_logic.signal_controller import SignalController
from .signal_logic.green_corridor import GreenCorridorManager

logger = logging.getLogger("traffic-ai.main")

# ---------------------------------------------------------------------------
# Upload directory
# ---------------------------------------------------------------------------
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
detector: VehicleDetector | None = None
emergency_detector: EmergencyDetector | None = None
density_analyzer: DensityAnalyzer | None = None
signal_controller: SignalController | None = None
corridor_manager: GreenCorridorManager | None = None
frame_streamer: FrameStreamer | None = None
database: Database | None = None

connected_clients: Set[WebSocket] = set()
latest_payload: Dict = {}
start_time: float = 0.0
tick_count: int = 0
processing_task: asyncio.Task | None = None
processing_active: bool = False

# Per-lane video captures
lane_captures: Dict[str, cv2.VideoCapture] = {}
lane_video_paths: Dict[str, str] = {}

# Cumulative per-lane stats
lane_cumulative: Dict[str, Dict[str, int]] = {}
lane_ambulance_status: Dict[str, bool] = {}
lane_ambulance_time: Dict[str, Optional[int]] = {}

# Signal timing history for efficiency comparison
signal_history: List[Dict] = []

LANE_IDS = ["Lane 1", "Lane 2", "Lane 3", "Lane 4"]


def _reset_lane_stats():
    global lane_cumulative, lane_ambulance_status, lane_ambulance_time
    for lid in LANE_IDS:
        lane_cumulative[lid] = {
            "cars": 0, "buses": 0, "trucks": 0,
            "motorcycles": 0, "ambulances": 0, "total": 0,
        }
        lane_ambulance_status[lid] = False
        lane_ambulance_time[lid] = None


_reset_lane_stats()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global detector, emergency_detector, density_analyzer
    global signal_controller, corridor_manager, frame_streamer
    global database, start_time

    logger.info("=" * 60)
    logger.info("  ITMS — Intelligent Traffic Management System v4.0")
    logger.info("  Multi-Lane Video Analysis + Ambulance Priority")
    logger.info("=" * 60)

    warnings = validate_config()
    for w in warnings:
        logger.warning("CONFIG WARNING: %s", w)

    start_time = time.time()

    # Detection modules
    detector = VehicleDetector()
    emergency_detector = EmergencyDetector()
    density_analyzer = DensityAnalyzer()

    # Signal control
    signal_controller = SignalController(intersection_id="ITMS-001")
    corridor_manager = GreenCorridorManager()

    # Frame streamer
    frame_streamer = FrameStreamer()

    # Database
    database = Database(db_path=DB_PATH)
    try:
        await database.initialize()
        logger.info("Database connected: %s", DB_PATH)
    except Exception as e:
        logger.error("Database init failed: %s", e)
        database = None

    logger.info("System ready. Waiting for video uploads...")
    logger.info("=" * 60)

    yield

    logger.info("Shutting down...")
    _close_all_captures()
    if database:
        await database.close()
    for ws in list(connected_clients):
        try:
            await ws.close()
        except Exception:
            pass
    logger.info("Shutdown complete.")


def _close_all_captures():
    for cap in lane_captures.values():
        if cap and cap.isOpened():
            cap.release()
    lane_captures.clear()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ITMS — Intelligent Traffic Management System",
    description="Multi-lane video upload, YOLOv8 detection, ambulance priority, signal optimization",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://localhost:5174", "http://localhost:5175",
        "http://localhost:5176", "http://localhost:5177", "http://localhost:5178",
        "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:5174",
        FRONTEND_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Processing Loop — Round-robin across all 4 lane videos
# ---------------------------------------------------------------------------
async def _processing_loop() -> None:
    global latest_payload, tick_count, processing_active, signal_history

    interval = max(WS_INTERVAL_MS / 1000.0, 0.03)
    lane_frame_indices = {lid: 0 for lid in LANE_IDS}

    while processing_active:
        try:
            tick_count += 1
            lane_results = {}
            all_vehicles_this_tick = 0

            for lane_id in LANE_IDS:
                cap = lane_captures.get(lane_id)
                if not cap or not cap.isOpened():
                    continue

                ret, frame = cap.read()
                if not ret:
                    # Loop the video
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret:
                        continue

                lane_frame_indices[lane_id] += 1

                # YOLOv8 detection
                detection = detector.detect(frame) if detector else {}
                vehicles = []
                for lane_data in detection.get("lanes", []):
                    vehicles.extend(lane_data.get("vehicles", []))
                if not vehicles:
                    # Use all detections (flat list approach)
                    for lane_data in detection.get("lanes", []):
                        vehicles.extend(lane_data.get("vehicles", []))

                # Check for ambulance via emergency detector
                emergency = emergency_detector.detect(frame, detection) if emergency_detector else {}
                ambulance_here = emergency.get("emergency_detected", False)

                # Update cumulative counts
                vtypes = detection.get("vehicle_types", {})
                cum = lane_cumulative[lane_id]
                cum["cars"] += vtypes.get("car", 0)
                cum["buses"] += vtypes.get("bus", 0)
                cum["trucks"] += vtypes.get("truck", 0)
                cum["motorcycles"] += vtypes.get("motorcycle", 0)
                if ambulance_here:
                    cum["ambulances"] += 1
                cum["total"] += detection.get("total_vehicles", 0)

                lane_ambulance_status[lane_id] = ambulance_here

                # Density for this lane
                density_count = detection.get("total_vehicles", 0)
                all_vehicles_this_tick += density_count

                # Determine signal color for this lane
                lane_idx = LANE_IDS.index(lane_id)
                signal_color = "green" if (tick_count // 20) % 4 == lane_idx else "red"

                # Compute dynamic green time
                green_time = None
                if signal_color == "green":
                    green_time = min(MAX_GREEN_TIME, max(MIN_GREEN_TIME,
                        BASE_GREEN_TIME + (density_count - 5) * 2))

                if ambulance_here:
                    signal_color = "green"
                    green_time = 20
                    lane_ambulance_time[lane_id] = 20

                # Annotate frame and store
                if frame_streamer:
                    all_detections = []
                    for ld in detection.get("lanes", []):
                        all_detections.extend(ld.get("vehicles", []))
                    frame_streamer.annotate_and_store(
                        lane_id=lane_id,
                        frame=frame,
                        detections=all_detections,
                        density=density_count,
                        ambulance_detected=ambulance_here,
                        green_time=green_time,
                        signal_color=signal_color,
                    )

                lane_results[lane_id] = {
                    "density": density_count,
                    "ambulance": ambulance_here,
                    "signal": signal_color,
                    "green_time": green_time,
                    "vehicle_types": vtypes,
                    "frame_index": lane_frame_indices[lane_id],
                }

                # Handle ambulance -> green corridor
                if ambulance_here and corridor_manager and signal_controller:
                    direction = lane_id.replace("Lane ", "LANE_")
                    corridor_manager.activate(
                        direction="NORTH",
                        vehicle_type="ambulance",
                        controller=signal_controller,
                        confidence=emergency.get("confidence", 0.8),
                    )

            # Dynamic signal timing for efficiency tracking
            for lane_id in LANE_IDS:
                lr = lane_results.get(lane_id, {})
                density_count = lr.get("density", 0)
                smart_time = min(MAX_GREEN_TIME, max(MIN_GREEN_TIME,
                    BASE_GREEN_TIME + (density_count - 5) * 2))
                signal_history.append({
                    "lane": lane_id,
                    "smart_time": smart_time,
                    "traditional_time": 30,
                    "tick": tick_count,
                })

            # Keep only last 1000 signal entries
            if len(signal_history) > 1000:
                signal_history = signal_history[-1000:]

            # Build broadcast payload
            payload = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "tick": tick_count,
                "lanes": lane_results,
                "cumulative": lane_cumulative,
                "ambulance_status": lane_ambulance_status,
                "total_vehicles": all_vehicles_this_tick,
                "processing": True,
                "system_health": {
                    "status": "operational",
                    "uptime_seconds": round(time.time() - start_time, 1),
                    "tick_count": tick_count,
                    "active_connections": len(connected_clients),
                },
            }
            latest_payload = payload

            # Broadcast via WebSocket
            if connected_clients:
                msg = json.dumps(payload)
                stale = set()
                for ws in connected_clients:
                    try:
                        await ws.send_text(msg)
                    except Exception:
                        stale.add(ws)
                connected_clients.difference_update(stale)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Processing loop error: %s", e, exc_info=True)

        await asyncio.sleep(interval)


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.add(ws)
    logger.info("WebSocket client connected. Total: %d", len(connected_clients))
    try:
        while True:
            data = await ws.receive_text()
            # Handle any commands from client
            try:
                cmd = json.loads(data)
                logger.debug("WS command: %s", cmd)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.discard(ws)
        logger.info("WebSocket client disconnected. Total: %d", len(connected_clients))


# ---------------------------------------------------------------------------
# Video Upload
# ---------------------------------------------------------------------------
@app.post("/api/upload")
async def upload_videos(
    lane1: UploadFile = File(...),
    lane2: UploadFile = File(...),
    lane3: UploadFile = File(...),
    lane4: UploadFile = File(...),
):
    """Upload 4 lane videos for processing."""
    global processing_active, processing_task

    # Stop any existing processing
    processing_active = False
    if processing_task and not processing_task.done():
        processing_task.cancel()
        try:
            await processing_task
        except (asyncio.CancelledError, Exception):
            pass

    _close_all_captures()
    _reset_lane_stats()

    files = {"Lane 1": lane1, "Lane 2": lane2, "Lane 3": lane3, "Lane 4": lane4}
    saved = {}

    for lane_id, upload in files.items():
        safe_name = f"{lane_id.replace(' ', '_').lower()}{Path(upload.filename).suffix}"
        dest = UPLOAD_DIR / safe_name
        with open(dest, "wb") as f:
            shutil.copyfileobj(upload.file, f)
        lane_video_paths[lane_id] = str(dest)
        saved[lane_id] = str(dest)
        logger.info("Saved %s -> %s", lane_id, dest)

    return {"status": "uploaded", "files": saved}


@app.post("/api/start-processing")
async def start_processing():
    """Begin YOLOv8 analysis on uploaded lane videos."""
    global processing_active, processing_task, tick_count

    if not lane_video_paths:
        return {"error": "No videos uploaded. Use /api/upload first."}

    # Stop existing task
    processing_active = False
    if processing_task and not processing_task.done():
        processing_task.cancel()
        try:
            await processing_task
        except (asyncio.CancelledError, Exception):
            pass

    _close_all_captures()
    tick_count = 0

    # Open video captures
    for lane_id, path in lane_video_paths.items():
        cap = cv2.VideoCapture(path)
        if cap.isOpened():
            lane_captures[lane_id] = cap
            logger.info("Opened video for %s: %s", lane_id, path)
        else:
            logger.error("Failed to open video for %s: %s", lane_id, path)

    if not lane_captures:
        return {"error": "No videos could be opened."}

    processing_active = True
    processing_task = asyncio.create_task(_processing_loop())
    logger.info("Processing started for %d lanes", len(lane_captures))

    return {"status": "processing", "lanes": list(lane_captures.keys())}


@app.post("/api/stop-processing")
async def stop_processing():
    """Stop the processing loop."""
    global processing_active, processing_task
    processing_active = False
    if processing_task and not processing_task.done():
        processing_task.cancel()
        try:
            await processing_task
        except (asyncio.CancelledError, Exception):
            pass
    return {"status": "stopped"}


# ---------------------------------------------------------------------------
# Annotated Frame Serving
# ---------------------------------------------------------------------------
@app.get("/api/frames/{lane_id}")
async def get_frame(lane_id: str):
    """Get the latest annotated JPEG frame for a lane."""
    # Map lane_id: "1" -> "Lane 1", "Lane 1" -> "Lane 1"
    if lane_id.isdigit():
        lane_id = f"Lane {lane_id}"

    if frame_streamer:
        jpeg = frame_streamer.get_frame(lane_id)
        if jpeg:
            return Response(content=jpeg, media_type="image/jpeg")
        # Return placeholder
        placeholder = frame_streamer.get_placeholder_frame(lane_id)
        return Response(content=placeholder, media_type="image/jpeg")

    return Response(content=b"", status_code=404)


# ---------------------------------------------------------------------------
# Lane Stats
# ---------------------------------------------------------------------------
@app.get("/api/lane-stats")
async def get_lane_stats():
    """Get cumulative vehicle counts per lane."""
    return {
        "lanes": lane_cumulative,
        "ambulance_status": lane_ambulance_status,
        "ambulance_time": lane_ambulance_time,
    }


# ---------------------------------------------------------------------------
# Efficiency — Smart vs Traditional
# ---------------------------------------------------------------------------
@app.get("/api/efficiency")
async def get_efficiency():
    """Get smart vs traditional signal timing comparison."""
    if not signal_history:
        return {"lanes": {}, "summary": {}}

    lane_data = {}
    for lid in LANE_IDS:
        entries = [s for s in signal_history if s["lane"] == lid]
        if entries:
            avg_smart = sum(e["smart_time"] for e in entries[-50:]) / min(len(entries), 50)
            avg_trad = 30
            lane_data[lid] = {
                "smart_avg": round(avg_smart, 1),
                "traditional_avg": avg_trad,
                "savings_pct": round((1 - avg_smart / avg_trad) * 100, 1) if avg_trad > 0 else 0,
            }

    return {"lanes": lane_data}


# ---------------------------------------------------------------------------
# Status & Health
# ---------------------------------------------------------------------------
@app.get("/api/status")
async def get_status():
    return {
        "processing": processing_active,
        "lanes_loaded": list(lane_captures.keys()),
        "tick_count": tick_count,
        "uptime_seconds": round(time.time() - start_time, 1),
        "connections": len(connected_clients),
    }


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "4.0.0"}


@app.get("/api/dashboard")
async def get_dashboard():
    """Return the latest state payload for polling clients."""
    return latest_payload


# ---------------------------------------------------------------------------
# Emergency Control (manual trigger)
# ---------------------------------------------------------------------------
@app.post("/api/emergency/trigger")
async def trigger_emergency(
    lane: str = Query("Lane 1"),
):
    """Manually trigger ambulance priority for a lane."""
    lane_ambulance_status[lane] = True
    lane_ambulance_time[lane] = 20

    if corridor_manager and signal_controller:
        corridor_manager.activate(
            direction="NORTH",
            vehicle_type="ambulance",
            controller=signal_controller,
            confidence=1.0,
        )
    return {"status": "emergency_triggered", "lane": lane}


@app.post("/api/emergency/clear")
async def clear_emergency():
    """Clear emergency state."""
    for lid in LANE_IDS:
        lane_ambulance_status[lid] = False
        lane_ambulance_time[lid] = None
    if corridor_manager:
        corridor_manager.clear()
    return {"status": "cleared"}

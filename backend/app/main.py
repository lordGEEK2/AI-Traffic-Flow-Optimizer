"""
main.py -- FastAPI Application (Delhi Smart Traffic Platform v3.0)
===================================================================
Core application integrating all system components:
  - VideoSource for real-time camera/RTSP/file ingestion
  - VehicleDetector + DensityAnalyzer for traffic analysis
  - EmergencyDetector + GreenCorridorManager for emergency handling
  - SignalController for traffic signal management
  - ViolationDetector for traffic rule enforcement
  - TrafficAnalyzer for advanced analytics and AI reasoning
  - Database for persistent storage
  - WebSocket for real-time dashboard updates
  - REST API for status, config, health, history, violations, analytics
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, List, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

from .utils.config import (
    BACKEND_HOST, BACKEND_PORT, FRONTEND_URL, WS_INTERVAL_MS,
    SIMULATION_MODE, VIDEO_SOURCE_MODE, VIDEO_SOURCE,
    WEBCAM_INDEX, RTSP_URL, RTSP_TIMEOUT, TARGET_FPS,
    DENSITY_THRESHOLD, BASE_GREEN_TIME, MAX_GREEN_TIME, MIN_GREEN_TIME,
    YELLOW_TIME, ALL_RED_TIME, MAX_CYCLE_TIME,
    EMERGENCY_MIN_FRAMES, EMERGENCY_CONF_THRESHOLD,
    YOLO_MODEL, YOLO_CONFIDENCE,
    DB_PATH, DB_WRITE_INTERVAL,
    validate_config, load_lane_config,
)
from .utils.database import Database
from .cv_engine.video_source import VideoSource
from .cv_engine.vehicle_detector import VehicleDetector
from .cv_engine.emergency_detector import EmergencyDetector
from .cv_engine.density_analyzer import DensityAnalyzer
from .cv_engine.violation_detector import ViolationDetector
from .signal_logic.signal_controller import SignalController
from .signal_logic.green_corridor import GreenCorridorManager
from .analytics.traffic_analyzer import TrafficAnalyzer

logger = logging.getLogger("traffic-ai.main")

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
video_source: VideoSource | None = None
detector: VehicleDetector | None = None
emergency_detector: EmergencyDetector | None = None
density_analyzer: DensityAnalyzer | None = None
signal_controller: SignalController | None = None
corridor_manager: GreenCorridorManager | None = None
violation_detector: ViolationDetector | None = None
traffic_analyzer: TrafficAnalyzer | None = None
database: Database | None = None
weather_state: str = "clear"

connected_clients: Set[WebSocket] = set()
latest_payload: Dict = {}
start_time: float = 0.0
tick_count: int = 0
processing_task: asyncio.Task | None = None
ai_paused: bool = False


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global video_source, detector, emergency_detector, density_analyzer
    global signal_controller, corridor_manager, violation_detector
    global traffic_analyzer, database, start_time, processing_task

    logger.info("=" * 60)
    logger.info("  Delhi Smart Traffic Command & Analytics Platform v3.0")
    logger.info("  Intersection: ITO, Delhi")
    logger.info("=" * 60)

    warnings = validate_config()
    for w in warnings:
        logger.warning("CONFIG WARNING: %s", w)

    start_time = time.time()

    # Video source
    mode = VIDEO_SOURCE_MODE if not SIMULATION_MODE else "simulation"
    video_source = VideoSource(
        mode=mode, device_index=WEBCAM_INDEX, rtsp_url=RTSP_URL,
        video_path=VIDEO_SOURCE, target_fps=TARGET_FPS, rtsp_timeout=RTSP_TIMEOUT,
    )
    video_source.start()

    # Detection modules
    detector = VehicleDetector()
    emergency_detector = EmergencyDetector()
    density_analyzer = DensityAnalyzer()

    # Signal control
    signal_controller = SignalController(intersection_id="ITO-INT-001")
    corridor_manager = GreenCorridorManager()

    # Violation detection (load bus priority lanes from Delhi profile)
    try:
        import json as _json
        from pathlib import Path
        _profile_path = Path(__file__).resolve().parent.parent / "config" / "city_profile_delhi.json"
        with open(_profile_path) as _f:
            _profile = _json.load(_f)
        bus_lanes = _profile.get("bus_priority_lanes", [])
    except Exception:
        bus_lanes = []
    violation_detector = ViolationDetector(bus_priority_lanes=bus_lanes)

    # Analytics engine
    traffic_analyzer = TrafficAnalyzer()

    # Database
    database = Database(db_path=DB_PATH)
    try:
        await database.initialize()
        logger.info("Database connected: %s", DB_PATH)
    except Exception as e:
        logger.error("Database initialization failed: %s", e)
        database = None

    processing_task = asyncio.create_task(_processing_loop())
    logger.info("System ready. Video: %s | Simulation: %s", mode, SIMULATION_MODE)
    logger.info("=" * 60)

    yield

    logger.info("Shutting down...")
    if processing_task:
        processing_task.cancel()
        try:
            await processing_task
        except asyncio.CancelledError:
            pass
    if video_source:
        video_source.stop()
    if database:
        await database.close()
    for ws in list(connected_clients):
        try:
            await ws.close()
        except Exception:
            pass
    logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Delhi Smart Traffic Command & Analytics Platform",
    description="Real-time traffic management with CV-based detection, violation monitoring, and smart signal control for ITO Intersection, Delhi",
    version="3.0.0",
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
# Processing Loop
# ---------------------------------------------------------------------------
async def _processing_loop() -> None:
    global latest_payload, tick_count

    interval = WS_INTERVAL_MS / 1000.0

    while True:
        try:
            tick_count += 1

            # If AI is paused, just send last payload
            if ai_paused:
                await asyncio.sleep(interval)
                continue

            # 1. Read frame
            frame = video_source.read() if video_source else None

            # 2. Vehicle detection
            detection = detector.detect(frame) if detector else {}

            # 3. Density analysis
            density = density_analyzer.analyze(detection) if density_analyzer else {}

            # 4. Emergency detection
            emergency = emergency_detector.detect(frame, detection) if emergency_detector else {}

            # 5. Handle emergency events
            if emergency.get("emergency_detected") and corridor_manager and signal_controller:
                corridor_manager.activate(
                    direction=emergency.get("lane_id", "NORTH"),
                    vehicle_type=emergency.get("vehicle_type", "ambulance"),
                    controller=signal_controller,
                    confidence=emergency.get("confidence", 0.0),
                )

            # 6. Corridor timeout
            if corridor_manager and signal_controller:
                corridor_manager.check_timeout(signal_controller)

            # 7. Signal controller
            total_pedestrians = detection.get("vehicle_types", {}).get("person", 0)
            if signal_controller:
                signal_controller.set_weather(weather_state)
                intersection = signal_controller.update(density, total_pedestrians)
            else:
                intersection = {}

            # 8. Violation detection
            violations = []
            if violation_detector:
                violations = violation_detector.detect(
                    detection, intersection, density, tick_count
                )

            # 9. Traffic analytics
            analytics = {}
            if traffic_analyzer:
                analytics = traffic_analyzer.analyze(detection, density, intersection)

            # 10. Build payload
            vs_stats = video_source.get_stats() if video_source else {}
            corridor_status = corridor_manager.get_status() if corridor_manager else {}
            alerts = corridor_manager.get_alerts(10) if corridor_manager else []

            payload = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "detection": detection,
                "density": density,
                "intersection": intersection,
                "corridor": corridor_status,
                "video_source": vs_stats,
                "alerts": alerts,
                "violations": {
                    "recent": violations,
                    "summary": violation_detector.get_summary() if violation_detector else {},
                },
                "analytics": analytics,
                "system_health": {
                    "status": "operational",
                    "uptime_seconds": round(time.time() - start_time, 1),
                    "tick_count": tick_count,
                    "active_connections": len(connected_clients),
                    "video_healthy": video_source.is_healthy if video_source else False,
                    "database_connected": database is not None,
                    "ai_paused": ai_paused,
                },
            }
            latest_payload = payload

            # 11. Broadcast
            if connected_clients:
                msg = json.dumps(payload)
                stale = set()
                for ws in connected_clients:
                    try:
                        await ws.send_text(msg)
                    except Exception:
                        stale.add(ws)
                connected_clients.difference_update(stale)

            # 12. Periodic DB writes
            if database and tick_count % DB_WRITE_INTERVAL == 0:
                try:
                    for lane in density.get("lanes", []):
                        await database.insert_traffic_metric(
                            lane_id=lane.get("lane_id", ""),
                            vehicle_count=lane.get("vehicle_count", 0),
                            density_score=lane.get("smoothed_density", 0.0),
                            density_level=lane.get("level", "low"),
                            total_vehicles=detection.get("total_vehicles", 0),
                            fps=detection.get("fps", 0.0),
                        )
                    # Write violations
                    for v in violations:
                        await database.insert_violation(v)
                    # Write health snapshot
                    health = analytics.get("health", {})
                    trends = analytics.get("trends", {})
                    await database.insert_health_snapshot(
                        health_score=health.get("intersection_health_score", 50),
                        signal_efficiency=health.get("signal_efficiency", 50),
                        avg_wait=health.get("avg_wait_time_seconds", 0),
                        trend=trends.get("congestion_trend", "stable"),
                        weather=weather_state,
                    )
                    await database.insert_health_log(
                        status="operational",
                        video_healthy=video_source.is_healthy if video_source else False,
                        video_mode=vs_stats.get("mode", "simulation"),
                        fps=detection.get("fps", 0.0),
                        connections=len(connected_clients),
                        uptime=round(time.time() - start_time, 1),
                    )
                except Exception as e:
                    logger.debug("DB write error: %s", e)

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
            try:
                cmd = json.loads(data)
                await _handle_ws_command(cmd)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        connected_clients.discard(ws)
        logger.info("WebSocket client disconnected. Total: %d", len(connected_clients))


async def _handle_ws_command(cmd: Dict) -> None:
    action = cmd.get("action")
    if action == "trigger_emergency":
        direction = cmd.get("direction", "NORTH")
        vehicle_type = cmd.get("vehicle_type", "ambulance")
        if corridor_manager and signal_controller:
            corridor_manager.activate(direction, vehicle_type, signal_controller, 1.0)
            if database:
                await database.insert_emergency_event(
                    event_type="manual_trigger", vehicle_type=vehicle_type,
                    lane_id=direction, intersection_id="ITO-INT-001",
                )
    elif action == "clear_emergency":
        if corridor_manager and signal_controller:
            corridor_manager.deactivate(signal_controller, reason="manual_clear")
        if emergency_detector:
            emergency_detector.clear()


# ---------------------------------------------------------------------------
# REST API — Status
# ---------------------------------------------------------------------------
@app.get("/api/status")
async def get_status():
    return {
        "status": "running",
        "version": "3.0.0",
        "city": "Delhi",
        "intersection": "ITO-INT-001",
        "simulation_mode": SIMULATION_MODE,
        "video_mode": video_source.mode.value if video_source else "simulation",
        "uptime_seconds": round(time.time() - start_time, 1),
        "video_healthy": video_source.is_healthy if video_source else False,
        "database_connected": database is not None,
        "active_ws_connections": len(connected_clients),
        "ai_paused": ai_paused,
    }


@app.get("/api/health")
async def health_check():
    checks = {
        "video_source": video_source.is_healthy if video_source else False,
        "detector": detector is not None,
        "signal_controller": signal_controller is not None,
        "violation_detector": violation_detector is not None,
        "traffic_analyzer": traffic_analyzer is not None,
        "database": database is not None and database._initialized,
    }
    healthy = all(checks.values())
    return {"healthy": healthy, "checks": checks, "warnings": validate_config()}


@app.get("/api/config")
async def get_config():
    return {
        "video_source_mode": VIDEO_SOURCE_MODE,
        "density_threshold": DENSITY_THRESHOLD,
        "base_green_time": BASE_GREEN_TIME,
        "max_green_time": MAX_GREEN_TIME,
        "min_green_time": MIN_GREEN_TIME,
        "yellow_time": YELLOW_TIME,
        "all_red_time": ALL_RED_TIME,
        "max_cycle_time": MAX_CYCLE_TIME,
        "ws_interval_ms": WS_INTERVAL_MS,
        "emergency_min_frames": EMERGENCY_MIN_FRAMES,
        "emergency_conf_threshold": EMERGENCY_CONF_THRESHOLD,
        "yolo_model": YOLO_MODEL,
        "yolo_confidence": YOLO_CONFIDENCE,
        "simulation_mode": SIMULATION_MODE,
        "city": "Delhi",
    }


@app.get("/api/dashboard")
async def get_dashboard():
    return latest_payload or {"message": "No data yet."}


@app.get("/api/lanes")
async def get_lane_config():
    return load_lane_config()


# ---------------------------------------------------------------------------
# Emergency Control
# ---------------------------------------------------------------------------
@app.post("/api/emergency/trigger")
async def trigger_emergency(
    direction: str = Query("NORTH"), vehicle_type: str = Query("ambulance"),
):
    if corridor_manager and signal_controller:
        success = corridor_manager.activate(direction, vehicle_type, signal_controller, 1.0)
        if database:
            await database.insert_emergency_event(
                event_type="manual_trigger", vehicle_type=vehicle_type,
                lane_id=direction, intersection_id="ITO-INT-001",
            )
        return {"success": success, "message": f"Emergency {'triggered' if success else 'rejected'}: {vehicle_type} from {direction}"}
    return {"success": False, "message": "System not ready"}


@app.post("/api/emergency/clear")
async def clear_emergency():
    if corridor_manager and signal_controller:
        corridor_manager.deactivate(signal_controller, reason="api_clear")
    if emergency_detector:
        emergency_detector.clear()
    return {"success": True, "message": "Emergency cleared"}


# ---------------------------------------------------------------------------
# Weather Control
# ---------------------------------------------------------------------------
@app.post("/api/system/weather")
async def set_weather(state: str = Query("clear")):
    global weather_state
    if state not in ("clear", "rain"):
        return {"success": False, "message": "Invalid state. Use 'clear' or 'rain'."}
    weather_state = state
    return {"success": True, "message": f"Weather updated to {state}"}


# ---------------------------------------------------------------------------
# Operator Controls
# ---------------------------------------------------------------------------
@app.post("/api/operator/pause")
async def pause_ai():
    global ai_paused
    ai_paused = True
    return {"success": True, "message": "AI processing paused"}


@app.post("/api/operator/resume")
async def resume_ai():
    global ai_paused
    ai_paused = False
    return {"success": True, "message": "AI processing resumed"}


@app.post("/api/operator/force-signal")
async def force_signal(direction: str = Query("NORTH"), duration: int = Query(30)):
    if signal_controller:
        signal_controller.emergency_preempt(direction)
        async def _auto_release():
            await asyncio.sleep(duration)
            if signal_controller:
                signal_controller.emergency_release()
        asyncio.create_task(_auto_release())
        return {"success": True, "message": f"Signal forced GREEN for {direction} for {duration}s"}
    return {"success": False, "message": "System not ready"}


@app.post("/api/operator/adjust-threshold")
async def adjust_threshold(threshold: int = Query(60)):
    import app.utils.config as cfg
    cfg.DENSITY_THRESHOLD = max(10, min(100, threshold))
    return {"success": True, "message": f"Density threshold adjusted to {cfg.DENSITY_THRESHOLD}"}


# ---------------------------------------------------------------------------
# Test Mode
# ---------------------------------------------------------------------------
@app.post("/api/system/test-emergency")
async def test_emergency(
    direction: str = Query("NORTH"), vehicle_type: str = Query("ambulance"),
    duration_seconds: int = Query(10),
):
    if corridor_manager and signal_controller:
        success = corridor_manager.activate(direction, vehicle_type, signal_controller, 0.99)
        if not success:
            return {"success": False, "message": "Cannot trigger (cooldown or already active)"}
        if database:
            await database.insert_emergency_event(
                event_type="test", vehicle_type=vehicle_type,
                lane_id=direction, intersection_id="ITO-INT-001",
            )
        async def _auto_clear():
            await asyncio.sleep(duration_seconds)
            if corridor_manager and signal_controller and corridor_manager.is_active:
                corridor_manager.deactivate(signal_controller, reason="test_auto_clear")
                if emergency_detector:
                    emergency_detector.clear()
        asyncio.create_task(_auto_clear())
        return {"success": True, "message": f"Test emergency activated: {vehicle_type} from {direction}. Auto-clears in {duration_seconds}s."}
    return {"success": False, "message": "System not ready"}


# ---------------------------------------------------------------------------
# Violations
# ---------------------------------------------------------------------------
@app.get("/api/violations/recent")
async def get_violations(limit: int = Query(50, le=200)):
    if database:
        return await database.get_recent_violations(limit)
    if violation_detector:
        return violation_detector.get_recent(limit)
    return []


@app.get("/api/violations/summary")
async def get_violation_summary():
    if violation_detector:
        return violation_detector.get_summary()
    return {"total_violations": 0, "by_type": {}}


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
@app.get("/api/analytics/current")
async def get_current_analytics():
    return latest_payload.get("analytics", {})


@app.get("/api/analytics/history")
async def get_analytics_history(limit: int = Query(100, le=500)):
    if database:
        return await database.get_health_history(limit)
    return []


@app.get("/api/intersection/health")
async def get_intersection_health():
    analytics = latest_payload.get("analytics", {})
    return {
        "health": analytics.get("health", {}),
        "forecast": analytics.get("forecast", {}),
        "trends": analytics.get("trends", {}),
    }


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------
@app.get("/api/history/metrics")
async def get_metrics_history(limit: int = Query(100, le=500)):
    if database:
        return await database.get_recent_metrics(limit)
    return []


@app.get("/api/history/emergencies")
async def get_emergency_history(limit: int = Query(50, le=200)):
    if database:
        return await database.get_recent_emergencies(limit)
    return []


@app.get("/api/history/signals")
async def get_signal_history(limit: int = Query(100, le=500)):
    if signal_controller:
        return signal_controller.get_audit_log(limit)
    return []


@app.get("/api/history/emergencies/today")
async def get_emergency_count_today():
    if database:
        count = await database.get_emergency_count_today()
        return {"count": count}
    return {"count": 0}

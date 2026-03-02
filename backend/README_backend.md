# Backend — Dynamic AI Traffic Flow Optimizer

## Overview

FastAPI-based backend providing:
- **CV Engine**: YOLOv8 vehicle detection, emergency detection, density analysis
- **Signal Logic**: State-machine signal controller with dynamic timing + green corridor
- **REST API**: Status, config, emergency trigger/clear endpoints
- **WebSocket**: Real-time dashboard updates every ~500ms

## Quick Start

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/status` | System status + uptime |
| GET | `/api/config` | Current configuration |
| GET | `/api/dashboard` | Latest dashboard data (REST fallback) |
| POST | `/api/emergency/trigger` | Manually trigger emergency |
| POST | `/api/emergency/clear` | Clear active emergency |
| WS | `/ws` | Real-time WebSocket feed |

## Module Reference

| Module | Purpose |
|--------|---------|
| `cv_engine/vehicle_detector.py` | YOLOv8 vehicle detection with lane assignment |
| `cv_engine/emergency_detector.py` | Emergency detection (YOLO + HSV heuristic) |
| `cv_engine/density_analyzer.py` | EMA-smoothed traffic density scoring |
| `signal_logic/signal_controller.py` | Traffic signal state machine |
| `signal_logic/green_corridor.py` | Multi-intersection emergency corridor |
| `models/schemas.py` | Pydantic data models |
| `utils/config.py` | Environment config loader |

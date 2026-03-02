# Smart Traffic Command Center v2.0

> Real-world-ready intelligent traffic management platform with computer vision,
> dynamic signal control, emergency green corridor, and persistent analytics.

---

## Architecture

```
                         +-----------------------+
                         |   COMMAND CENTER UI   |
                         |   (React + Vite)      |
                         +-----------+-----------+
                                     | WebSocket (~500ms)
                         +-----------+-----------+
                         |   FastAPI BACKEND     |
                         |   (Uvicorn)           |
                         +-----------+-----------+
                                     |
         +---------------------------+---------------------------+
         |               |               |               |       |
  +------+------+ +------+------+ +------+------+ +------+------+
  | VideoSource | | Vehicle     | | Emergency   | | Signal      |
  | (Webcam/    | | Detector    | | Detector    | | Controller  |
  |  RTSP/File) | | (YOLOv8)   | | (Multi-frm) | | (State M/C) |
  +------+------+ +------+------+ +------+------+ +------+------+
         |               |               |               |
         +---------------+-------+-------+---------------+
                                 |
                         +-------+-------+
                         | SQLite DB     |
                         | (Persistent)  |
                         +---------------+
```

---

## Quick Start

### Prerequisites

| Requirement       | Version   | Notes                                |
|--------------------|-----------|--------------------------------------|
| Python             | 3.10+     | Required                             |
| Node.js            | 18+       | Required for frontend                |
| GPU                | Optional  | CUDA GPU speeds up YOLO inference    |
| Webcam / RTSP cam  | Optional  | System works in simulation mode      |

### 1. Configure

```bash
cp .env.example .env
# Edit .env to set VIDEO_SOURCE_MODE, RTSP_URL, etc.
```

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

---

## Video Source Modes

Configure `VIDEO_SOURCE_MODE` in `.env`:

| Mode          | Setting                              | Use Case                           |
|---------------|--------------------------------------|------------------------------------|
| `simulation`  | `VIDEO_SOURCE_MODE=simulation`       | Demo/testing without camera        |
| `webcam`      | `VIDEO_SOURCE_MODE=webcam`           | Local USB/integrated camera        |
| `rtsp`        | `VIDEO_SOURCE_MODE=rtsp`             | IP camera / CCTV / NVR stream      |
| `video_file`  | `VIDEO_SOURCE_MODE=video_file`       | Pre-recorded traffic footage       |

### RTSP Camera Setup

```env
VIDEO_SOURCE_MODE=rtsp
RTSP_URL=rtsp://admin:password@192.168.1.100:554/stream1
RTSP_TIMEOUT=10
TARGET_FPS=15
```

Common RTSP URL formats:
- Hikvision: `rtsp://admin:password@IP:554/Streaming/Channels/101`
- Dahua: `rtsp://admin:password@IP:554/cam/realmonitor?channel=1&subtype=0`
- Generic: `rtsp://user:pass@IP:PORT/path`

RTSP Troubleshooting:
1. Verify camera is reachable: `ping <camera-ip>`
2. Test stream externally: `ffplay rtsp://...`
3. Check firewall allows port 554
4. Try TCP transport: set `RTSP_TIMEOUT=15`
5. If stream drops frequently, lower `TARGET_FPS`

---

## Lane Polygon Calibration

Lane regions are defined in `backend/config/lane_config.json`.

### Calibration Steps

1. Capture a frame from your camera:
   ```python
   import cv2
   cap = cv2.VideoCapture(0)  # or RTSP URL
   ret, frame = cap.read()
   cv2.imwrite("calibration_frame.png", frame)
   cap.release()
   ```

2. Open the frame in an image editor and note pixel coordinates
   for each lane boundary polygon (4+ points per lane).

3. Update `lane_config.json`:
   ```json
   {
     "frame_width": 1280,
     "frame_height": 720,
     "lanes": [
       {
         "id": "NORTH",
         "polygon": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]],
         "signal_group": "NS"
       }
     ]
   }
   ```

4. Restart the backend to apply.

---

## Emergency Detection Calibration

The system uses multi-signal confirmation:

| Parameter                 | Default | Description                          |
|---------------------------|---------|--------------------------------------|
| `EMERGENCY_MIN_FRAMES`    | 5       | Consecutive frames required          |
| `EMERGENCY_CONF_THRESHOLD`| 0.6     | Minimum YOLO confidence              |

To test: `POST http://localhost:8000/api/system/test-emergency?direction=NORTH&duration_seconds=10`

---

## API Reference

| Method | Path                           | Description                        |
|--------|--------------------------------|------------------------------------|
| GET    | `/api/status`                  | System status                      |
| GET    | `/api/health`                  | Health checks                      |
| GET    | `/api/config`                  | Current configuration              |
| GET    | `/api/dashboard`               | Latest dashboard data              |
| GET    | `/api/lanes`                   | Lane polygon configuration         |
| POST   | `/api/emergency/trigger`       | Trigger emergency                  |
| POST   | `/api/emergency/clear`         | Clear emergency                    |
| POST   | `/api/system/test-emergency`   | Test emergency through pipeline    |
| GET    | `/api/history/metrics`         | Historical traffic metrics         |
| GET    | `/api/history/emergencies`     | Emergency event history            |
| GET    | `/api/history/signals`         | Signal state change audit log      |
| WS     | `/ws`                          | Real-time WebSocket feed           |

---

## Database

SQLite database at `backend/data/traffic.db`:

| Table                 | Purpose                          |
|-----------------------|----------------------------------|
| `traffic_metrics`     | Per-tick density and counts      |
| `emergency_events`    | Emergency detection log          |
| `signal_history`      | Signal state change audit        |
| `system_health_logs`  | System health snapshots          |

---

## Hardware Requirements

### Minimum (Simulation/Demo)
- CPU: Any modern processor
- RAM: 4 GB
- GPU: Not required

### Recommended (Real-Time with Camera)
- CPU: Intel i5 / Ryzen 5 or better
- RAM: 8 GB
- GPU: NVIDIA GPU with CUDA (GTX 1050+) for faster YOLO inference
- Camera: USB webcam or IP camera with RTSP support

### Production Deployment
- CPU: Intel i7 / Ryzen 7
- RAM: 16 GB
- GPU: NVIDIA RTX 2060+ for multi-stream processing
- Network: Stable LAN connection to cameras
- Storage: SSD for database writes

---

## Manual Configuration Checklist

Before deploying, the operator must:

1. Set `VIDEO_SOURCE_MODE` and camera URL in `.env`
2. Calibrate lane polygons in `backend/config/lane_config.json`
3. Test emergency detection threshold (`EMERGENCY_MIN_FRAMES`)
4. Verify camera angle covers the full intersection
5. Configure firewall to allow ports 8000 (backend) and 5173 (frontend)
6. Install NVIDIA GPU drivers if using GPU acceleration
7. Run the test emergency endpoint to validate the full pipeline

---

## Performance Tuning

| Scenario              | TARGET_FPS | YOLO_CONFIDENCE | Notes                |
|-----------------------|------------|-----------------|----------------------|
| Low-power device      | 5          | 0.5             | Reduce load          |
| Standard desktop      | 15         | 0.4             | Default              |
| GPU-accelerated       | 30         | 0.3             | Full throughput      |
| Multiple cameras      | 10         | 0.45            | Per-camera           |

---

## Known Limitations

- Single intersection support (multi-intersection requires additional controllers)
- Emergency detection relies on visual cues (no audio/siren detection yet)
- YOLO detects COCO classes only (no custom emergency vehicle model)
- SQLite is single-writer (use PostgreSQL for high-concurrency production)
- Lane polygons require manual calibration per camera

---

## Scaling to Multiple Intersections

To add more intersections:
1. Create additional `SignalController` instances with unique IDs
2. Add per-intersection lane configs in `lane_config.json`
3. Route video sources to corresponding detectors
4. Extend the WebSocket payload with multi-intersection data

For city-scale deployment, consider:
- PostgreSQL instead of SQLite
- Redis for inter-process messaging
- Docker Compose for containerized deployment
- Kubernetes for orchestration

---

## License

MIT License. Free for personal and commercial use.

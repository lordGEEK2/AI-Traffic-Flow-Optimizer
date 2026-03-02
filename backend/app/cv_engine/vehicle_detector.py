"""
vehicle_detector.py — YOLOv8 Vehicle Detection with Polygon Lane Assignment
=============================================================================
Detects vehicles using YOLOv8 and assigns them to lanes based on
configurable polygon ROIs loaded from lane_config.json.

Production features:
  - Polygon-based lane assignment using cv2.pointPolygonTest
  - Per-lane vehicle counting with type breakdown
  - Density scoring normalized by lane polygon area
  - Simulation fallback when YOLO or camera unavailable
  - FPS tracking and statistics
"""

from __future__ import annotations

import logging
import random
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..utils.config import (
    YOLO_MODEL, YOLO_CONFIDENCE, SIMULATION_MODE, load_lane_config
)

logger = logging.getLogger("traffic-ai.vehicle_detector")

# YOLO class IDs for vehicles (COCO dataset)
VEHICLE_CLASSES: Dict[int, str] = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


class VehicleDetector:
    """
    Detects vehicles in frames using YOLOv8 and assigns them to
    polygon-defined lane regions.

    In simulation mode, generates realistic synthetic detection data.
    """

    def __init__(self) -> None:
        self.model = None
        self.simulation_mode = SIMULATION_MODE
        self._lane_config = load_lane_config()
        self._lane_polygons: Dict[str, np.ndarray] = {}
        self._lane_areas: Dict[str, float] = {}
        self._frame_count: int = 0
        self._fps: float = 0.0
        self._fps_timer: float = time.time()
        self._fps_counter: int = 0

        # Prepare lane polygons as numpy arrays and compute areas
        self._init_lane_polygons()

        # Load YOLO model
        if not self.simulation_mode:
            self._load_model()
        else:
            logger.info("VehicleDetector initialized in SIMULATION mode.")

    def _init_lane_polygons(self) -> None:
        """Convert JSON polygon definitions to numpy arrays and compute areas."""
        for lane in self._lane_config.get("lanes", []):
            lid = lane["id"]
            poly_pts = np.array(lane["polygon"], dtype=np.int32)
            self._lane_polygons[lid] = poly_pts
            # Compute polygon area using Shoelace formula
            area = float(abs(np.cross(
                poly_pts - poly_pts[0],
                np.roll(poly_pts, -1, axis=0) - poly_pts[0]
            ).sum()) / 2.0)
            self._lane_areas[lid] = max(area, 1.0)  # prevent division by zero
        logger.info(
            "Initialized %d lane polygons. Areas: %s",
            len(self._lane_polygons),
            {k: f"{v:.0f}px^2" for k, v in self._lane_areas.items()},
        )

    def _load_model(self) -> None:
        """Load YOLOv8 model. Falls back to simulation on failure."""
        try:
            from ultralytics import YOLO
            self.model = YOLO(YOLO_MODEL)
            logger.info("YOLOv8 model loaded: %s", YOLO_MODEL)
        except Exception as e:
            logger.warning("Failed to load YOLO model: %s. Falling back to simulation.", e)
            self.simulation_mode = True

    def detect(self, frame: Optional[np.ndarray] = None) -> Dict:
        """
        Run detection on a frame.

        Args:
            frame: BGR numpy array from VideoSource. None = simulation.

        Returns:
            Dict with keys:
              - total_vehicles: int
              - lanes: list of {lane_id, vehicle_count, density_score, vehicles: [{class, bbox, confidence}]}
              - vehicle_types: {car: N, truck: N, ...}
              - fps: float
              - frame_count: int
        """
        self._frame_count += 1
        self._update_fps()

        if self.simulation_mode or frame is None:
            return self._simulate()

        return self._detect_real(frame)

    def _detect_real(self, frame: np.ndarray) -> Dict:
        """Run real YOLO detection and assign vehicles to polygon lanes."""
        import cv2

        # Run YOLO inference
        results = self.model(frame, conf=YOLO_CONFIDENCE, verbose=False)

        # Collect all detected vehicles
        all_vehicles: List[Dict] = []
        vehicle_types: Dict[str, int] = {"car": 0, "truck": 0, "bus": 0, "motorcycle": 0}

        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls_id = int(box.cls[0])
                if cls_id not in VEHICLE_CLASSES:
                    continue

                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                vtype = VEHICLE_CLASSES[cls_id]
                vehicle_types[vtype] = vehicle_types.get(vtype, 0) + 1

                all_vehicles.append({
                    "class": vtype,
                    "confidence": round(conf, 2),
                    "bbox": [x1, y1, x2, y2],
                    "center": (cx, cy),
                })

        # Assign vehicles to lanes using polygon containment
        lane_data = []
        for lane in self._lane_config.get("lanes", []):
            lid = lane["id"]
            poly = self._lane_polygons[lid]
            lane_vehicles = []

            for v in all_vehicles:
                cx, cy = v["center"]
                # Check if vehicle center is inside lane polygon
                dist = cv2.pointPolygonTest(poly, (float(cx), float(cy)), False)
                if dist >= 0:
                    lane_vehicles.append(v)

            count = len(lane_vehicles)
            area = self._lane_areas.get(lid, 1.0)
            # Density: vehicles per 10000 px^2, clamped to 0-100
            raw_density = min(100.0, (count / area) * 100000.0)

            lane_data.append({
                "lane_id": lid,
                "vehicle_count": count,
                "density_score": round(raw_density, 1),
                "vehicles": lane_vehicles,
            })

        total = len(all_vehicles)

        return {
            "total_vehicles": total,
            "lanes": lane_data,
            "vehicle_types": vehicle_types,
            "fps": self._fps,
            "frame_count": self._frame_count,
        }

    def _simulate(self) -> Dict:
        """Generate realistic simulated detection data."""
        # Vary traffic volume with time-based patterns
        base = 8 + int(5 * abs(np.sin(self._frame_count * 0.02)))

        lanes = []
        vehicle_types = {"car": 0, "truck": 0, "bus": 0, "motorcycle": 0}

        for lane in self._lane_config.get("lanes", []):
            lid = lane["id"]
            variance = random.randint(-3, 5)
            count = max(0, base + variance)

            # Distribute by type
            cars = int(count * 0.6)
            trucks = int(count * 0.15)
            buses = int(count * 0.1)
            motos = count - cars - trucks - buses

            vehicle_types["car"] += cars
            vehicle_types["truck"] += trucks
            vehicle_types["bus"] += buses
            vehicle_types["motorcycle"] += motos

            # Density based on simulated saturation
            density = min(100.0, count * 6.5 + random.uniform(-3, 3))

            lanes.append({
                "lane_id": lid,
                "vehicle_count": count,
                "density_score": round(max(0, density), 1),
                "vehicles": [],
            })

        total = sum(l["vehicle_count"] for l in lanes)

        return {
            "total_vehicles": total,
            "lanes": lanes,
            "vehicle_types": vehicle_types,
            "fps": self._fps or 15.0,
            "frame_count": self._frame_count,
        }

    def _update_fps(self) -> None:
        """Track detection FPS."""
        self._fps_counter += 1
        now = time.time()
        elapsed = now - self._fps_timer
        if elapsed >= 1.0:
            self._fps = round(self._fps_counter / elapsed, 1)
            self._fps_counter = 0
            self._fps_timer = now

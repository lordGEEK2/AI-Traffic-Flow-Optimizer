"""
emergency_detector.py — Multi-Frame Emergency Vehicle Detection
================================================================
Detects emergency vehicles using a multi-signal confirmation system:
  1. YOLO class match (truck/bus in emergency proximity)
  2. HSV color heuristic (flashing red/blue lights)
  3. Frame persistence — trigger only after N consecutive frames

Production features:
  - Configurable frame threshold (EMERGENCY_MIN_FRAMES)
  - Configurable confidence threshold (EMERGENCY_CONF_THRESHOLD)
  - Per-lane emergency tracking
  - Extensibility hooks for siren detection and priority registry
  - Simulation mode with periodic random events
"""

from __future__ import annotations

import logging
import random
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..utils.config import (
    EMERGENCY_CONFIDENCE,
    EMERGENCY_MIN_FRAMES,
    EMERGENCY_CONF_THRESHOLD,
    SIMULATION_MODE,
    load_lane_config,
)

logger = logging.getLogger("traffic-ai.emergency_detector")


class EmergencyDetector:
    """
    Multi-frame confirmation emergency vehicle detector.

    Requires both YOLO detection AND color heuristic match for
    N consecutive frames before triggering an emergency event.
    """

    def __init__(self) -> None:
        self.simulation_mode = SIMULATION_MODE
        self.min_frames = max(1, EMERGENCY_MIN_FRAMES)
        self.conf_threshold = EMERGENCY_CONF_THRESHOLD

        # Per-lane frame counters for confirmation
        self._detection_counters: Dict[str, int] = {}
        self._active_emergency: bool = False
        self._emergency_lane: Optional[str] = None
        self._emergency_vehicle_type: Optional[str] = None
        self._frame_count: int = 0

        # Simulation state
        self._sim_last_trigger: float = time.time()
        self._sim_interval: float = random.uniform(30, 60)
        self._sim_active: bool = False
        self._sim_start_time: float = 0.0

        # Lane config
        self._lane_config = load_lane_config()
        for lane in self._lane_config.get("lanes", []):
            self._detection_counters[lane["id"]] = 0

        # Extensibility hooks (placeholders)
        self._siren_detector: Optional[SirenDetectorInterface] = None
        self._priority_registry: Optional[PriorityRegistryInterface] = None

        logger.info(
            "EmergencyDetector initialized: min_frames=%d, conf_threshold=%.2f, simulation=%s",
            self.min_frames, self.conf_threshold, self.simulation_mode,
        )

    def detect(self, frame: Optional[np.ndarray] = None, detections: Optional[Dict] = None) -> Dict:
        """
        Run emergency detection on a frame and its YOLO detections.

        Args:
            frame: BGR numpy array (None in simulation mode).
            detections: Output from VehicleDetector.detect().

        Returns:
            Dict with:
              - emergency_detected: bool
              - vehicle_type: str (ambulance | fire_truck | "")
              - lane_id: str
              - confidence: float
              - confirmation_frames: int (how many consecutive frames)
              - siren_detected: bool (placeholder, always False for now)
        """
        self._frame_count += 1

        if self.simulation_mode or frame is None:
            return self._simulate()

        return self._detect_real(frame, detections or {})

    def _detect_real(self, frame: np.ndarray, detections: Dict) -> Dict:
        """
        Real detection pipeline:
        Step 1: Check for YOLO-detected large vehicles (truck, bus) in each lane
        Step 2: Check HSV color heuristic for flashing lights near those vehicles
        Step 3: Require N consecutive frames for confirmation
        """
        import cv2

        result = {
            "emergency_detected": False,
            "vehicle_type": "",
            "lane_id": "",
            "confidence": 0.0,
            "confirmation_frames": 0,
            "siren_detected": False,
        }

        # Step 1: Find potential emergency vehicles from YOLO detections
        for lane_data in detections.get("lanes", []):
            lid = lane_data["lane_id"]
            has_yolo_match = False
            has_color_match = False
            best_conf = 0.0

            for v in lane_data.get("vehicles", []):
                if v["class"] in ("truck", "bus") and v.get("confidence", 0) >= self.conf_threshold:
                    has_yolo_match = True
                    best_conf = max(best_conf, v.get("confidence", 0))

                    # Step 2: HSV color heuristic in the vehicle bounding box area
                    bbox = v.get("bbox", [])
                    if len(bbox) == 4:
                        x1, y1, x2, y2 = bbox
                        # Check upper portion for lights
                        light_h = max(1, (y2 - y1) // 3)
                        roi = frame[max(0, y1):max(1, y1 + light_h), max(0, x1):max(1, x2)]
                        if roi.size > 0:
                            has_color_match = self._check_emergency_colors(roi)

            # Step 3: Frame persistence
            if has_yolo_match and has_color_match:
                self._detection_counters[lid] = self._detection_counters.get(lid, 0) + 1
            else:
                # Reset counter if not detected this frame
                self._detection_counters[lid] = max(0, self._detection_counters.get(lid, 0) - 1)

            # Check if threshold met
            count = self._detection_counters.get(lid, 0)
            if count >= self.min_frames and not self._active_emergency:
                self._active_emergency = True
                self._emergency_lane = lid
                self._emergency_vehicle_type = "ambulance"  # Default; could be refined
                result["emergency_detected"] = True
                result["vehicle_type"] = "ambulance"
                result["lane_id"] = lid
                result["confidence"] = round(best_conf, 2)
                result["confirmation_frames"] = count
                logger.warning(
                    "EMERGENCY CONFIRMED: %s in lane %s after %d frames (conf=%.2f)",
                    result["vehicle_type"], lid, count, best_conf,
                )
                break

        # Check siren detector hook
        if self._siren_detector is not None:
            result["siren_detected"] = self._siren_detector.detect()

        return result

    def _check_emergency_colors(self, roi: np.ndarray) -> bool:
        """
        Check for red/blue flashing light colors in a region of interest.
        Uses HSV color space analysis.

        Returns True if significant red or blue pixels detected.
        """
        import cv2

        if roi.size == 0:
            return False

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        total_pixels = hsv.shape[0] * hsv.shape[1]
        if total_pixels == 0:
            return False

        # Red detection (wraps around hue)
        red_low1 = cv2.inRange(hsv, np.array([0, 120, 100]), np.array([10, 255, 255]))
        red_low2 = cv2.inRange(hsv, np.array([170, 120, 100]), np.array([180, 255, 255]))
        red_mask = cv2.bitwise_or(red_low1, red_low2)

        # Blue detection
        blue_mask = cv2.inRange(hsv, np.array([100, 120, 100]), np.array([130, 255, 255]))

        red_ratio = float(np.count_nonzero(red_mask)) / total_pixels
        blue_ratio = float(np.count_nonzero(blue_mask)) / total_pixels

        # Require at least 5% coverage of either color
        return red_ratio > 0.05 or blue_ratio > 0.05

    def _simulate(self) -> Dict:
        """Simulate emergency events periodically."""
        result = {
            "emergency_detected": False,
            "vehicle_type": "",
            "lane_id": "",
            "confidence": 0.0,
            "confirmation_frames": 0,
            "siren_detected": False,
        }

        now = time.time()

        # Handle active simulation emergency
        if self._sim_active:
            if now - self._sim_start_time > 15.0:  # Emergency lasts 15s in sim
                self._sim_active = False
                self._active_emergency = False
                self._sim_last_trigger = now
                self._sim_interval = random.uniform(30, 60)
                logger.info("Simulation emergency expired.")
            return result

        # Trigger new emergency
        if now - self._sim_last_trigger > self._sim_interval and not self._active_emergency:
            lanes = self._lane_config.get("lanes", [])
            if lanes:
                lane = random.choice(lanes)
                result["emergency_detected"] = True
                result["vehicle_type"] = random.choice(["ambulance", "fire_truck"])
                result["lane_id"] = lane["id"]
                result["confidence"] = round(random.uniform(0.7, 0.95), 2)
                result["confirmation_frames"] = self.min_frames

                self._sim_active = True
                self._sim_start_time = now
                self._active_emergency = True
                self._emergency_lane = lane["id"]

                logger.warning(
                    "SIMULATION EMERGENCY: %s in lane %s",
                    result["vehicle_type"], result["lane_id"],
                )

        return result

    def clear(self) -> None:
        """Clear the current emergency state."""
        self._active_emergency = False
        self._emergency_lane = None
        self._emergency_vehicle_type = None
        self._sim_active = False
        for k in self._detection_counters:
            self._detection_counters[k] = 0
        logger.info("Emergency state cleared.")

    @property
    def is_active(self) -> bool:
        return self._active_emergency


# ---------------------------------------------------------------------------
# Extensibility Hook Interfaces (Placeholders)
# ---------------------------------------------------------------------------
class SirenDetectorInterface:
    """
    Placeholder interface for audio-based siren detection.

    To implement:
      1. Capture audio from a microphone near the intersection
      2. Run spectrogram analysis for siren frequency patterns
      3. Return True if siren detected within the last N seconds

    This is NOT required for the system to function. It provides
    an additional confirmation signal for emergency detection.
    """
    def detect(self) -> bool:
        raise NotImplementedError


class PriorityRegistryInterface:
    """
    Placeholder interface for vehicle priority registration.

    To implement:
      1. Connect to a registry service (e.g., RTO database)
      2. Match detected license plates to registered emergency vehicles
      3. Return priority level for the vehicle

    This requires OCR/ANPR integration and is NOT required for
    basic emergency detection.
    """
    def lookup(self, plate: str) -> Optional[int]:
        raise NotImplementedError

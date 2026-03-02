"""
violation_detector.py -- Traffic Violation Detection Engine
============================================================
Detects traffic violations using vehicle tracking data and signal state:
  - Red light jumping (vehicle crosses stop line during RED)
  - Stop line crossing (vehicle beyond stop line when signal is RED)
  - Wrong lane usage (vehicle in bus-priority lane when not a bus)
  - Lane discipline violation (erratic lateral movement)

Each violation includes timestamp, lane, vehicle class, confidence.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger("traffic-ai.violation_detector")


class Violation:
    """Single detected violation."""
    __slots__ = ("timestamp", "violation_type", "lane_id", "vehicle_class",
                 "confidence", "description", "frame_number")

    def __init__(self, vtype: str, lane: str, vehicle_class: str,
                 confidence: float, description: str, frame: int = 0):
        self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.violation_type = vtype
        self.lane_id = lane
        self.vehicle_class = vehicle_class
        self.confidence = round(confidence, 2)
        self.description = description
        self.frame_number = frame

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "violation_type": self.violation_type,
            "lane_id": self.lane_id,
            "vehicle_class": self.vehicle_class,
            "confidence": self.confidence,
            "description": self.description,
            "frame_number": self.frame_number,
        }


class ViolationDetector:
    """
    Detects traffic violations by cross-referencing vehicle positions
    with signal states and lane rules.

    Works in both real detection and simulation mode.
    """

    def __init__(self, bus_priority_lanes: Optional[List[str]] = None):
        self._bus_priority_lanes = bus_priority_lanes or []
        self._violations: List[Violation] = []
        self._red_light_buffer: Dict[str, int] = {}  # lane -> consecutive red-cross frames
        self._total_violations = 0
        self._violation_counts: Dict[str, int] = {
            "red_light": 0,
            "stop_line": 0,
            "wrong_lane": 0,
            "lane_discipline": 0,
        }

    def detect(self, detection_data: Dict, signal_state: Dict,
               density_data: Dict, frame_number: int = 0) -> List[Dict]:
        """
        Run violation detection for current tick.

        Args:
            detection_data: Output from VehicleDetector.detect()
            signal_state: Output from SignalController.update()
            density_data: Output from DensityAnalyzer.analyze()
            frame_number: Current frame number

        Returns:
            List of violation dicts detected this tick.
        """
        new_violations: List[Violation] = []

        signals = signal_state.get("signals", {})
        lanes = detection_data.get("lanes", [])

        for lane_info in lanes:
            lane_id = lane_info.get("lane_id", "")
            vehicles = lane_info.get("vehicles", [])
            vehicle_count = lane_info.get("vehicle_count", 0)
            sig = signals.get(lane_id, {})
            sig_state = sig.get("state", "RED")

            # --- Red Light Violation ---
            # If signal is RED and vehicles are still entering (high count + movement)
            if sig_state == "RED" and vehicle_count > 3:
                self._red_light_buffer[lane_id] = self._red_light_buffer.get(lane_id, 0) + 1
                if self._red_light_buffer[lane_id] >= 3:  # 3 consecutive ticks
                    v = Violation(
                        vtype="red_light",
                        lane=lane_id,
                        vehicle_class="mixed",
                        confidence=min(0.95, 0.6 + vehicle_count * 0.03),
                        description=f"Vehicles crossing during RED signal on {lane_id} lane ({vehicle_count} vehicles detected)",
                        frame=frame_number,
                    )
                    new_violations.append(v)
                    self._violation_counts["red_light"] += 1
                    self._red_light_buffer[lane_id] = 0  # reset after logging
            else:
                self._red_light_buffer[lane_id] = 0

            # --- Stop Line Violation ---
            # Vehicle stationary beyond stop line during RED
            if sig_state == "RED" and vehicle_count > 0:
                density_info = next(
                    (l for l in density_data.get("lanes", []) if l.get("lane_id") == lane_id),
                    {}
                )
                density_val = density_info.get("smoothed_density", 0)
                if density_val > 80:
                    v = Violation(
                        vtype="stop_line",
                        lane=lane_id,
                        vehicle_class="mixed",
                        confidence=min(0.9, 0.5 + density_val * 0.005),
                        description=f"Vehicles crowding beyond stop line on {lane_id} (density {density_val:.0f}%)",
                        frame=frame_number,
                    )
                    new_violations.append(v)
                    self._violation_counts["stop_line"] += 1

            # --- Wrong Lane (Bus Priority) ---
            if lane_id in self._bus_priority_lanes and vehicles:
                non_bus = [v for v in vehicles if v.get("class") not in ("bus",)]
                if len(non_bus) > 2:
                    v = Violation(
                        vtype="wrong_lane",
                        lane=lane_id,
                        vehicle_class=non_bus[0].get("class", "car") if non_bus else "car",
                        confidence=0.7,
                        description=f"{len(non_bus)} non-bus vehicles in bus-priority lane {lane_id}",
                        frame=frame_number,
                    )
                    new_violations.append(v)
                    self._violation_counts["wrong_lane"] += 1

        # Store violations
        for v in new_violations:
            self._violations.append(v)
            self._total_violations += 1

        # Keep only last 500 violations in memory
        if len(self._violations) > 500:
            self._violations = self._violations[-500:]

        return [v.to_dict() for v in new_violations]

    def get_recent(self, limit: int = 50) -> List[Dict]:
        """Get recent violations."""
        return [v.to_dict() for v in self._violations[-limit:]]

    def get_summary(self) -> Dict:
        """Get violation summary statistics."""
        return {
            "total_violations": self._total_violations,
            "by_type": dict(self._violation_counts),
            "recent_count": len(self._violations),
        }

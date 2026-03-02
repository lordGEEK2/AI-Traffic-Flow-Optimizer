"""
density_analyzer.py — Polygon-Aware Traffic Density Analysis
==============================================================
Analyzes vehicle detection results with:
  - EMA (Exponential Moving Average) smoothing per lane
  - Temporal stability window to prevent rapid level flipping
  - Polygon-area-normalized density scoring
  - Congestion level classification (LOW / MEDIUM / HIGH / CRITICAL)
  - Trend detection (increasing / decreasing / stable)
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

from ..utils.config import EMA_ALPHA, DENSITY_THRESHOLD, STABILITY_WINDOW

logger = logging.getLogger("traffic-ai.density_analyzer")

# Congestion level thresholds
LEVELS = {
    "low": (0, 25),
    "medium": (25, 50),
    "high": (50, 75),
    "critical": (75, 101),
}


class DensityAnalyzer:
    """
    Smooths and classifies lane density data from the vehicle detector.

    Uses EMA smoothing and a temporal stability window to prevent
    rapid oscillation between congestion levels.
    """

    def __init__(self, alpha: float = EMA_ALPHA, stability_window: int = STABILITY_WINDOW) -> None:
        """
        Args:
            alpha: EMA smoothing factor (0-1). Higher = more responsive.
            stability_window: Seconds a new level must persist before being committed.
        """
        self.alpha = max(0.05, min(1.0, alpha))
        self.stability_window = max(0, stability_window)

        # Per-lane stored state
        self._smoothed: Dict[str, float] = {}
        self._levels: Dict[str, str] = {}
        self._pending_levels: Dict[str, str] = {}
        self._pending_since: Dict[str, float] = {}
        self._prev_smoothed: Dict[str, float] = {}  # for trend detection
        self._history: Dict[str, List[float]] = {}   # recent density values (last 30)

        logger.info(
            "DensityAnalyzer initialized: alpha=%.2f, stability_window=%ds",
            self.alpha, self.stability_window,
        )

    def analyze(self, detection_result: Dict) -> Dict:
        """
        Analyze detection output and produce smoothed density data.

        Args:
            detection_result: Output from VehicleDetector.detect().

        Returns:
            Dict with:
              - lanes: [{lane_id, raw_density, smoothed_density, level, trend, vehicle_count}]
              - overall_density: float (average across lanes)
              - overall_level: str
              - congestion_index: float (0-100)
        """
        now = time.time()
        output_lanes = []
        densities = []

        for lane in detection_result.get("lanes", []):
            lid = lane["lane_id"]
            raw = lane.get("density_score", 0.0)
            count = lane.get("vehicle_count", 0)

            # --- EMA smoothing ---
            prev = self._smoothed.get(lid, raw)
            smoothed = self.alpha * raw + (1.0 - self.alpha) * prev
            smoothed = round(min(100.0, max(0.0, smoothed)), 1)
            self._smoothed[lid] = smoothed

            # --- History for trend ---
            if lid not in self._history:
                self._history[lid] = []
            self._history[lid].append(smoothed)
            if len(self._history[lid]) > 30:
                self._history[lid] = self._history[lid][-30:]

            # --- Trend detection ---
            trend = "stable"
            if len(self._history[lid]) >= 5:
                recent_5 = self._history[lid][-5:]
                diff = recent_5[-1] - recent_5[0]
                if diff > 5:
                    trend = "increasing"
                elif diff < -5:
                    trend = "decreasing"

            # --- Level classification with stability window ---
            new_level = self._classify(smoothed)
            current_level = self._levels.get(lid, "low")

            if new_level != current_level:
                pending = self._pending_levels.get(lid)
                if pending == new_level:
                    # Already pending — check stability window
                    elapsed = now - self._pending_since.get(lid, now)
                    if elapsed >= self.stability_window:
                        self._levels[lid] = new_level
                        self._pending_levels.pop(lid, None)
                        self._pending_since.pop(lid, None)
                        logger.info(
                            "Lane %s level changed: %s -> %s (density=%.1f)",
                            lid, current_level, new_level, smoothed,
                        )
                else:
                    # New pending level
                    self._pending_levels[lid] = new_level
                    self._pending_since[lid] = now
            else:
                # Level matches current — clear any pending
                self._pending_levels.pop(lid, None)
                self._pending_since.pop(lid, None)

            final_level = self._levels.get(lid, "low")
            densities.append(smoothed)

            output_lanes.append({
                "lane_id": lid,
                "raw_density": round(raw, 1),
                "smoothed_density": smoothed,
                "level": final_level,
                "trend": trend,
                "vehicle_count": count,
            })

            # Store for next iteration
            self._prev_smoothed[lid] = smoothed

        # Overall metrics
        overall_density = round(sum(densities) / max(1, len(densities)), 1)
        overall_level = self._classify(overall_density)
        congestion_index = round(min(100, overall_density), 1)

        return {
            "lanes": output_lanes,
            "overall_density": overall_density,
            "overall_level": overall_level,
            "congestion_index": congestion_index,
        }

    @staticmethod
    def _classify(density: float) -> str:
        """Classify a density score into a congestion level."""
        if density < 25:
            return "low"
        elif density < 50:
            return "medium"
        elif density < 75:
            return "high"
        return "critical"

    def get_lane_history(self, lane_id: str) -> List[float]:
        """Get recent smoothed density history for a lane."""
        return list(self._history.get(lane_id, []))

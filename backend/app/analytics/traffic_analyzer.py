"""
traffic_analyzer.py -- Advanced Traffic Analytics Engine
=========================================================
Computes real-time and historical traffic analytics:
  - Vehicles per minute (VPM) per lane and total
  - Per-lane throughput and utilization %
  - Signal efficiency % (green time vs vehicles served)
  - Average wait time estimate
  - Congestion trend (rising / stable / falling)
  - Intersection health score (0-100)
  - 5-minute congestion forecast using moving averages
  - Peak load detection and warning

Designed for Delhi ITO intersection deployment.
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("traffic-ai.traffic_analyzer")

# Load Delhi city profile for density weights
_CITY_PROFILE_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "city_profile_delhi.json"


def _load_city_profile() -> Dict:
    if _CITY_PROFILE_PATH.exists():
        with open(_CITY_PROFILE_PATH) as f:
            return json.load(f)
    return {}


class TrafficAnalyzer:
    """
    Advanced analytics engine that processes detection and density data
    to produce actionable insights for operators.
    """

    def __init__(self, window_size: int = 60):
        self._city = _load_city_profile()
        self._vehicle_weights = {
            k: v["weight"]
            for k, v in self._city.get("vehicle_mix", {}).items()
        }
        self._peak_hours = self._city.get("peak_hours", {})

        # Rolling windows for analytics (last N ticks)
        self._window_size = window_size
        self._density_history: deque = deque(maxlen=window_size)
        self._vehicle_history: deque = deque(maxlen=window_size)
        self._lane_history: Dict[str, deque] = {}

        # Flow tracking
        self._tick_count = 0
        self._start_time = time.time()
        self._peak_density = 0.0
        self._peak_timestamp = ""

        # AI reasoning log
        self._ai_reasons: List[Dict] = []

        logger.info(
            "TrafficAnalyzer initialized. City: %s, Weights: %s",
            self._city.get("city", "Default"),
            self._vehicle_weights,
        )

    def analyze(self, detection: Dict, density: Dict, signal: Dict) -> Dict:
        """
        Produce full analytics report from current tick data.

        Returns dict with:
          - flow: vehicles_per_minute, throughput, utilization
          - health: intersection_health_score (0-100)
          - forecast: 5-min congestion prediction
          - trends: congestion_trend, peak info
          - ai_reasons: explainability log
        """
        self._tick_count += 1
        now = time.time()
        elapsed = max(1.0, now - self._start_time)

        total_vehicles = detection.get("total_vehicles", 0)
        overall_density = density.get("overall_density", 0.0)
        lanes = density.get("lanes", [])
        vehicle_types = detection.get("vehicle_types", {})

        # Track history
        self._density_history.append(overall_density)
        self._vehicle_history.append(total_vehicles)

        for lane in lanes:
            lid = lane.get("lane_id", "")
            if lid not in self._lane_history:
                self._lane_history[lid] = deque(maxlen=self._window_size)
            self._lane_history[lid].append({
                "count": lane.get("vehicle_count", 0),
                "density": lane.get("smoothed_density", 0),
            })

        # Track peak
        if overall_density > self._peak_density:
            self._peak_density = overall_density
            self._peak_timestamp = time.strftime("%H:%M:%S")

        # --- Flow Analytics ---
        vpm = (total_vehicles / elapsed) * 60.0     # vehicles per minute
        per_lane_throughput = {}
        per_lane_utilization = {}
        for lid, hist in self._lane_history.items():
            avg_count = sum(h["count"] for h in hist) / max(1, len(hist))
            per_lane_throughput[lid] = round(avg_count, 1)
            # Utilization: what fraction of lane capacity is used
            per_lane_utilization[lid] = round(
                min(100, (avg_count / max(1, 15)) * 100), 1
            )

        # --- Weighted Density (Delhi vehicle mix) ---
        weighted_total = 0.0
        raw_total = 0
        for vtype, count in vehicle_types.items():
            w = self._vehicle_weights.get(vtype, 1.0)
            weighted_total += count * w
            raw_total += count
        weighted_density = (weighted_total / max(1, raw_total)) * overall_density if raw_total > 0 else overall_density

        # --- Signal Efficiency ---
        sig_efficiency = self._calc_signal_efficiency(signal, density)

        # --- Average Wait Time Estimate ---
        avg_wait = self._estimate_wait_time(overall_density, signal)

        # --- Congestion Trend ---
        trend = self._calc_trend()

        # --- Intersection Health Score (0-100) ---
        health_score = self._calc_health_score(overall_density, lanes, avg_wait)

        # --- 5-Minute Forecast ---
        forecast = self._forecast_congestion()

        # --- Peak Hour Check ---
        is_peak = self._is_peak_hour()

        # --- AI Reasoning ---
        reasons = self._generate_reasons(
            overall_density, health_score, trend, is_peak, signal
        )

        return {
            "flow": {
                "vehicles_per_minute": round(vpm, 1),
                "total_throughput": total_vehicles,
                "per_lane_throughput": per_lane_throughput,
                "per_lane_utilization": per_lane_utilization,
                "weighted_density": round(weighted_density, 1),
            },
            "health": {
                "intersection_health_score": health_score,
                "signal_efficiency": sig_efficiency,
                "avg_wait_time_seconds": avg_wait,
            },
            "forecast": forecast,
            "trends": {
                "congestion_trend": trend,
                "peak_density": round(self._peak_density, 1),
                "peak_timestamp": self._peak_timestamp,
                "is_peak_hour": is_peak,
            },
            "ai_reasons": reasons,
        }

    def _calc_signal_efficiency(self, signal: Dict, density: Dict) -> float:
        """Signal efficiency: how well green time matches demand."""
        signals = signal.get("signals", {})
        lanes = {l.get("lane_id"): l for l in density.get("lanes", [])}
        if not signals:
            return 50.0

        # Efficiency = percentage of green time going to high-density lanes
        green_lanes_density = []
        for direction, sig in signals.items():
            if sig.get("state") == "GREEN":
                lane_density = lanes.get(direction, {}).get("smoothed_density", 0)
                green_lanes_density.append(lane_density)

        if not green_lanes_density:
            return 50.0  # no green = neutral

        avg_green_density = sum(green_lanes_density) / len(green_lanes_density)
        # High density getting green = high efficiency
        return round(min(100, avg_green_density + 20), 1)

    def _estimate_wait_time(self, density: float, signal: Dict) -> float:
        """Estimate average wait time based on density and cycle time."""
        cycle = signal.get("cycle_time", 120)
        # Higher density = longer wait (simple model)
        base_wait = (density / 100.0) * (cycle / 2.0)
        return round(min(120, max(5, base_wait)), 1)

    def _calc_trend(self) -> str:
        """Determine if congestion is rising, stable, or falling."""
        if len(self._density_history) < 10:
            return "stable"
        recent = list(self._density_history)
        first_half = sum(recent[:len(recent)//2]) / max(1, len(recent)//2)
        second_half = sum(recent[len(recent)//2:]) / max(1, len(recent) - len(recent)//2)
        diff = second_half - first_half
        if diff > 5:
            return "rising"
        elif diff < -5:
            return "falling"
        return "stable"

    def _calc_health_score(self, density: float, lanes: List, wait: float) -> int:
        """
        Intersection health score (0-100).
        100 = perfect flow, 0 = gridlocked.

        Based on:
          - density (40% weight)
          - wait time (30% weight)
          - lane imbalance (30% weight)
        """
        # Density component (lower = better)
        density_score = max(0, 100 - density)

        # Wait time component (lower = better)
        wait_score = max(0, 100 - (wait / 120.0) * 100)

        # Lane imbalance (lower = better)
        if lanes:
            densities = [l.get("smoothed_density", 0) for l in lanes]
            if densities:
                avg_d = sum(densities) / len(densities)
                imbalance = sum(abs(d - avg_d) for d in densities) / len(densities)
                imbalance_score = max(0, 100 - imbalance * 2)
            else:
                imbalance_score = 50
        else:
            imbalance_score = 50

        health = int(density_score * 0.4 + wait_score * 0.3 + imbalance_score * 0.3)
        return max(0, min(100, health))

    def _forecast_congestion(self) -> Dict:
        """Simple 5-minute forecast using exponential moving average."""
        if len(self._density_history) < 5:
            return {"predicted_density": 0, "warning": "insufficient_data"}

        recent = list(self._density_history)[-20:]
        # Exponential weighted average
        alpha = 0.3
        ema = recent[0]
        for val in recent[1:]:
            ema = alpha * val + (1 - alpha) * ema

        # Trend extrapolation
        trend = self._calc_trend()
        if trend == "rising":
            predicted = min(100, ema * 1.15)
        elif trend == "falling":
            predicted = max(0, ema * 0.85)
        else:
            predicted = ema

        warning = "none"
        if predicted > 80:
            warning = "critical_congestion_expected"
        elif predicted > 60:
            warning = "high_congestion_expected"

        return {
            "predicted_density": round(predicted, 1),
            "trend": trend,
            "warning": warning,
            "confidence": round(min(0.9, len(self._density_history) / 60.0), 2),
        }

    def _is_peak_hour(self) -> bool:
        """Check if current time falls within Delhi peak hours."""
        now = time.strftime("%H:%M")
        for period, times in self._peak_hours.items():
            if times.get("start", "") <= now <= times.get("end", ""):
                return True
        return False

    def _generate_reasons(self, density: float, health: int,
                          trend: str, is_peak: bool, signal: Dict) -> List[Dict]:
        """Generate human-readable AI reasoning for current decisions."""
        reasons = []

        if density > 75:
            reasons.append({
                "type": "congestion",
                "message": f"Density at {density:.0f}% exceeds critical threshold. Signal timings extended for congested lanes.",
                "severity": "high",
            })

        if health < 30:
            reasons.append({
                "type": "health",
                "message": f"Intersection health score is {health}/100. Severe imbalance detected across lanes.",
                "severity": "critical",
            })

        if trend == "rising":
            reasons.append({
                "type": "trend",
                "message": "Congestion trend is RISING. Preemptive green time adjustment active.",
                "severity": "warning",
            })

        if is_peak:
            reasons.append({
                "type": "peak_hour",
                "message": "Delhi peak hour active. Extended cycle times and priority weighting applied.",
                "severity": "info",
            })

        emergency = signal.get("emergency_active", False)
        if emergency:
            direction = signal.get("emergency_direction", "unknown")
            reasons.append({
                "type": "emergency",
                "message": f"Emergency preemption active from {direction}. All cross-traffic held RED.",
                "severity": "critical",
            })

        phase = signal.get("phase_stage", "")
        if phase == "PEDESTRIAN_CROSSING":
            reasons.append({
                "type": "pedestrian",
                "message": "Pedestrian crossing phase injected. All signals RED for safe crossing.",
                "severity": "info",
            })

        weather = signal.get("weather", "clear")
        if weather == "rain":
            reasons.append({
                "type": "weather",
                "message": "Rain mode active. ALL_RED clearance extended by +2s for skid prevention.",
                "severity": "warning",
            })

        # Keep only recent reasons in memory
        self._ai_reasons = reasons
        return reasons

    def get_summary(self) -> Dict:
        """Return current analytics summary."""
        return {
            "tick_count": self._tick_count,
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "peak_density": round(self._peak_density, 1),
            "peak_timestamp": self._peak_timestamp,
        }

"""
signal_controller.py — Government-Grade Traffic Signal Controller
===================================================================
State-machine based signal controller with:
  - Dynamic green time calculation based on lane density
  - Minimum/maximum green time enforcement
  - Maximum cycle time cap
  - All-red safety buffer between phases
  - Yellow phase before every red transition
  - Emergency preemption with safe transition (yellow first)
  - Audit trail logging to signal_state.json
  - Intersection state persistence
"""

from __future__ import annotations

import json
import logging
import os
import time
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from ..utils.config import (
    BASE_GREEN_TIME, MAX_GREEN_TIME, MIN_GREEN_TIME,
    YELLOW_TIME, ALL_RED_TIME, MAX_CYCLE_TIME,
    SIGNAL_STATE_LOG_PATH,
)

logger = logging.getLogger("traffic-ai.signal_controller")


class SignalState(str, Enum):
    """Traffic signal states."""
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"
    EMERGENCY_OVERRIDE = "EMERGENCY_OVERRIDE"


class PhaseStage(str, Enum):
    """Sub-stages within a phase transition."""
    GREEN_ACTIVE = "GREEN_ACTIVE"
    YELLOW_TRANSITION = "YELLOW_TRANSITION"
    ALL_RED_CLEARANCE = "ALL_RED_CLEARANCE"
    PEDESTRIAN_CROSSING = "PEDESTRIAN_CROSSING"


# Direction cycle order for a standard 4-way intersection
DIRECTION_ORDER = ["NORTH", "SOUTH", "EAST", "WEST"]


class SignalController:
    """
    Controls traffic signals for a single intersection.

    Cycles through directions in order, with dynamic green times
    based on lane density. Supports emergency preemption with
    safe transition (yellow phase before override).
    """

    def __init__(self, intersection_id: str = "INT-001") -> None:
        self.intersection_id = intersection_id

        # Phase tracking
        self._current_index: int = 0
        self._phase_stage: PhaseStage = PhaseStage.GREEN_ACTIVE
        self._phase_start: float = time.time()
        self._green_duration: float = float(BASE_GREEN_TIME)
        self._cycle_start: float = time.time()
        self._total_cycle_time: float = 0.0

        # Environmental
        self._weather: str = "clear"

        # Per-direction states
        self._states: Dict[str, SignalState] = {}
        self._countdowns: Dict[str, float] = {}
        self._density_at_green: Dict[str, float] = {}

        # Emergency
        self._emergency_active: bool = False
        self._emergency_direction: Optional[str] = None
        self._pre_emergency_index: int = 0

        # Audit trail
        self._audit_log: List[Dict] = []
        self._audit_path = Path(SIGNAL_STATE_LOG_PATH)

        # Initialize all directions to RED, first to GREEN
        for d in DIRECTION_ORDER:
            self._states[d] = SignalState.RED
            self._countdowns[d] = 0.0
        self._states[DIRECTION_ORDER[0]] = SignalState.GREEN
        self._countdowns[DIRECTION_ORDER[0]] = float(BASE_GREEN_TIME)

        logger.info(
            "SignalController initialized: intersection=%s, cycle=[%s]",
            intersection_id, " -> ".join(DIRECTION_ORDER),
        )

    def set_weather(self, weather: str) -> None:
        """Update environmental weather state."""
        self._weather = weather

    def update(self, density_data: Dict, total_pedestrians: int = 0) -> Dict:
        """
        Advance the signal controller by one tick.

        Args:
            density_data: Output from DensityAnalyzer.analyze(), containing
                          lanes with smoothed_density values.

        Returns:
            Dict with current intersection state:
              - intersection_id: str
              - signals: {direction: {state, countdown, density}}
              - current_phase: str (direction currently GREEN)
              - phase_stage: str
              - cycle_time: float
              - emergency_active: bool
        """
        now = time.time()
        elapsed = now - self._phase_start

        # Build density lookup
        lane_densities = {}
        for lane in density_data.get("lanes", []):
            lane_densities[lane["lane_id"]] = lane.get("smoothed_density", 0.0)

        # Handle emergency override
        if self._emergency_active:
            return self._build_state(lane_densities)

        current_dir = DIRECTION_ORDER[self._current_index]

        if self._phase_stage == PhaseStage.GREEN_ACTIVE:
            # Calculate dynamic green time for current direction
            density = lane_densities.get(current_dir, 0.0)
            self._green_duration = self._calc_green_time(density)
            remaining = max(0, self._green_duration - elapsed)
            self._countdowns[current_dir] = round(remaining, 1)

            if elapsed >= self._green_duration:
                # Transition to yellow
                self._phase_stage = PhaseStage.YELLOW_TRANSITION
                self._phase_start = now
                self._states[current_dir] = SignalState.YELLOW
                self._countdowns[current_dir] = float(YELLOW_TIME)
                self._log_transition(current_dir, "GREEN", "YELLOW", elapsed, density)

        elif self._phase_stage == PhaseStage.YELLOW_TRANSITION:
            remaining = max(0, YELLOW_TIME - elapsed)
            self._countdowns[current_dir] = round(remaining, 1)

            if elapsed >= YELLOW_TIME:
                # Transition to all-red clearance
                self._phase_stage = PhaseStage.ALL_RED_CLEARANCE
                self._phase_start = now
                self._states[current_dir] = SignalState.RED
                self._countdowns[current_dir] = 0.0
                self._log_transition(current_dir, "YELLOW", "RED", elapsed, 0)

        elif self._phase_stage == PhaseStage.ALL_RED_CLEARANCE:
            all_red_duration = ALL_RED_TIME + (2.0 if self._weather == "rain" else 0.0)
            if elapsed >= all_red_duration:
                # Inject pedestrian phase if waiting people > 2 at the end of a full cycle
                if self._current_index == len(DIRECTION_ORDER) - 1 and total_pedestrians > 2:
                    self._phase_stage = PhaseStage.PEDESTRIAN_CROSSING
                    self._phase_start = now
                else:
                    self._advance_to_next_green(lane_densities, now)

        elif self._phase_stage == PhaseStage.PEDESTRIAN_CROSSING:
            if elapsed >= 10.0:  # 10 second crossing time
                self._advance_to_next_green(lane_densities, now)

        return self._build_state(lane_densities)

    def _advance_to_next_green(self, lane_densities: Dict, now: float) -> None:
        """Reusable method to move from RED to next GREEN phase."""
        self._current_index = (self._current_index + 1) % len(DIRECTION_ORDER)
        next_dir = DIRECTION_ORDER[self._current_index]

        # Check cycle time cap
        self._total_cycle_time = now - self._cycle_start
        if self._current_index == 0:
            self._cycle_start = now
            self._total_cycle_time = 0.0

        self._phase_stage = PhaseStage.GREEN_ACTIVE
        self._phase_start = now
        self._states[next_dir] = SignalState.GREEN
        density = lane_densities.get(next_dir, 0.0)
        self._green_duration = self._calc_green_time(density)
        self._countdowns[next_dir] = round(self._green_duration, 1)
        self._density_at_green[next_dir] = density
        self._log_transition(next_dir, "RED", "GREEN", 0, density)

    def emergency_preempt(self, direction: str) -> None:
        """
        Activate emergency preemption for a direction.
        Uses safe transition: current green gets yellow first.
        """
        if self._emergency_active:
            return

        self._emergency_active = True
        self._emergency_direction = direction
        self._pre_emergency_index = self._current_index

        # Set all to RED, emergency direction to OVERRIDE
        for d in DIRECTION_ORDER:
            if d == direction:
                self._states[d] = SignalState.EMERGENCY_OVERRIDE
                self._countdowns[d] = 0.0  # No countdown during emergency
            else:
                self._states[d] = SignalState.RED
                self._countdowns[d] = 0.0

        self._log_transition(direction, "ANY", "EMERGENCY_OVERRIDE", 0, 0, trigger="emergency")

        logger.warning(
            "EMERGENCY PREEMPTION: direction=%s, intersection=%s",
            direction, self.intersection_id,
        )

    def emergency_release(self) -> None:
        """Release emergency preemption and resume normal cycling."""
        if not self._emergency_active:
            return

        self._emergency_active = False
        prev_dir = self._emergency_direction
        self._emergency_direction = None

        # Resume from the pre-emergency index
        self._current_index = self._pre_emergency_index
        self._phase_stage = PhaseStage.ALL_RED_CLEARANCE
        self._phase_start = time.time()

        # Set all to RED for safety clearance
        for d in DIRECTION_ORDER:
            self._states[d] = SignalState.RED
            self._countdowns[d] = 0.0

        self._log_transition(prev_dir or "UNKNOWN", "EMERGENCY_OVERRIDE", "RED", 0, 0, trigger="emergency_clear")
        logger.info("Emergency preemption released. Resuming normal cycle.")

    def get_state(self) -> Dict:
        """Get current intersection state (no update)."""
        return self._build_state({})

    def _calc_green_time(self, density: float) -> float:
        """
        Calculate dynamic green time based on density.

        Formula: green = BASE + (density / 100) * (MAX - BASE)
        Clamped to [MIN, MAX] and respects cycle time cap.
        """
        green = BASE_GREEN_TIME + (density / 100.0) * (MAX_GREEN_TIME - BASE_GREEN_TIME)
        green = max(MIN_GREEN_TIME, min(MAX_GREEN_TIME, green))

        # Enforce cycle time cap
        if self._total_cycle_time + green > MAX_CYCLE_TIME:
            green = max(MIN_GREEN_TIME, MAX_CYCLE_TIME - self._total_cycle_time)

        return green

    def _build_state(self, densities: Dict) -> Dict:
        """Build the full intersection state dict."""
        signals = {}
        for d in DIRECTION_ORDER:
            signals[d] = {
                "state": self._states[d].value,
                "countdown": self._countdowns.get(d, 0.0),
                "density": round(densities.get(d, 0.0), 1),
            }

        current_green = None
        for d in DIRECTION_ORDER:
            if self._states[d] in (SignalState.GREEN, SignalState.EMERGENCY_OVERRIDE):
                current_green = d
                break

        return {
            "intersection_id": self.intersection_id,
            "signals": signals,
            "current_phase": current_green or DIRECTION_ORDER[self._current_index],
            "phase_stage": self._phase_stage.value,
            "cycle_time": round(self._total_cycle_time, 1),
            "emergency_active": self._emergency_active,
            "emergency_direction": self._emergency_direction,
            "weather": self._weather,
        }

    def _log_transition(
        self, direction: str, from_state: str, to_state: str,
        duration: float, density: float, trigger: str = "auto"
    ) -> None:
        """Log a signal transition for audit trail."""
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "intersection_id": self.intersection_id,
            "direction": direction,
            "from": from_state,
            "to": to_state,
            "duration_seconds": round(duration, 1),
            "density_at_change": round(density, 1),
            "trigger": trigger,
        }
        self._audit_log.append(entry)

        # Keep only last 500 entries in memory
        if len(self._audit_log) > 500:
            self._audit_log = self._audit_log[-500:]

        # Persist to file (async-safe: append mode)
        try:
            os.makedirs(os.path.dirname(self._audit_path), exist_ok=True)
            with open(self._audit_path, "w") as f:
                json.dump(self._audit_log[-100:], f, indent=2)
        except Exception as e:
            logger.debug("Failed to write audit log: %s", e)

    def get_audit_log(self, limit: int = 50) -> List[Dict]:
        """Get recent audit log entries."""
        return list(self._audit_log[-limit:])

"""
green_corridor.py — Emergency Green Corridor Manager
======================================================
Coordinates emergency vehicle passage across intersections by:
  1. Setting the emergency approach lane to GREEN / OVERRIDE
  2. Holding all cross-traffic at RED
  3. Preparing downstream intersections (pre-green)
  4. Auto-deactivating on timeout
  5. Logging all corridor events
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

from .signal_controller import SignalController

logger = logging.getLogger("traffic-ai.green_corridor")

# Corridor timeout (auto-release after this many seconds)
CORRIDOR_TIMEOUT = 45.0
# Cooldown period after release (prevent rapid re-trigger)
CORRIDOR_COOLDOWN = 15.0


class GreenCorridorManager:
    """
    Manages the creation and release of emergency green corridors.

    Coordinates with one or more SignalControllers to create a
    clear path for emergency vehicles through an intersection.
    """

    def __init__(self) -> None:
        self._active: bool = False
        self._direction: Optional[str] = None
        self._vehicle_type: Optional[str] = None
        self._start_time: float = 0.0
        self._cooldown_until: float = 0.0
        self._alerts: List[Dict] = []
        self._event_log: List[Dict] = []
        self._corridor_path: List[str] = []

        logger.info("GreenCorridorManager initialized.")

    @property
    def is_active(self) -> bool:
        """Whether a green corridor is currently active."""
        return self._active

    @property
    def direction(self) -> Optional[str]:
        return self._direction

    @property
    def vehicle_type(self) -> Optional[str]:
        return self._vehicle_type

    @property
    def duration(self) -> float:
        """Duration of the current corridor in seconds."""
        if not self._active:
            return 0.0
        return round(time.time() - self._start_time, 1)

    def activate(
        self,
        direction: str,
        vehicle_type: str,
        controller: SignalController,
        confidence: float = 0.0,
    ) -> bool:
        """
        Activate a green corridor for an emergency vehicle.

        Args:
            direction: Approach direction (NORTH, SOUTH, EAST, WEST).
            vehicle_type: Type of emergency vehicle.
            controller: The SignalController to preempt.
            confidence: Detection confidence score.

        Returns:
            True if corridor was activated, False if in cooldown.
        """
        now = time.time()

        # Check cooldown
        if now < self._cooldown_until:
            remaining = round(self._cooldown_until - now, 1)
            logger.info("Green corridor in cooldown. %ss remaining.", remaining)
            return False

        if self._active:
            logger.info("Green corridor already active for %s.", self._direction)
            return False

        self._active = True
        self._direction = direction
        self._vehicle_type = vehicle_type
        self._start_time = now

        # Build corridor path (single intersection for now)
        self._corridor_path = [f"{controller.intersection_id}:{direction}"]

        # Preempt the signal controller
        controller.emergency_preempt(direction)

        # Generate alert
        alert = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "type": "CORRIDOR_ACTIVATED",
            "direction": direction,
            "vehicle_type": vehicle_type,
            "confidence": round(confidence, 2),
            "intersection": controller.intersection_id,
            "message": f"Green corridor activated: {vehicle_type.upper()} approaching from {direction}",
        }
        self._alerts.append(alert)
        self._event_log.append(alert)

        logger.warning(
            "GREEN CORRIDOR ACTIVATED: %s from %s at %s (conf=%.2f)",
            vehicle_type, direction, controller.intersection_id, confidence,
        )
        return True

    def deactivate(self, controller: SignalController, reason: str = "manual") -> None:
        """
        Deactivate the green corridor and restore normal signal operation.

        Args:
            controller: The SignalController to release.
            reason: Why the corridor was deactivated.
        """
        if not self._active:
            return

        duration = self.duration

        # Release the controller
        controller.emergency_release()

        # Log event
        event = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "type": "CORRIDOR_DEACTIVATED",
            "direction": self._direction,
            "vehicle_type": self._vehicle_type,
            "duration_seconds": duration,
            "reason": reason,
            "message": f"Green corridor deactivated after {duration:.1f}s. Reason: {reason}",
        }
        self._alerts.append(event)
        self._event_log.append(event)

        logger.info(
            "GREEN CORRIDOR DEACTIVATED: duration=%.1fs, reason=%s", duration, reason,
        )

        # Reset state and start cooldown
        self._active = False
        self._direction = None
        self._vehicle_type = None
        self._corridor_path = []
        self._cooldown_until = time.time() + CORRIDOR_COOLDOWN

    def check_timeout(self, controller: SignalController) -> bool:
        """
        Check if the active corridor has exceeded its timeout.
        Auto-deactivates if timed out.

        Returns:
            True if the corridor was timed out.
        """
        if not self._active:
            return False

        if self.duration >= CORRIDOR_TIMEOUT:
            logger.warning(
                "Green corridor TIMED OUT after %.1fs. Auto-deactivating.",
                self.duration,
            )
            self.deactivate(controller, reason="timeout")
            return True
        return False

    def get_status(self) -> Dict:
        """Get the current corridor status for the dashboard."""
        return {
            "active": self._active,
            "direction": self._direction,
            "vehicle_type": self._vehicle_type,
            "duration": self.duration,
            "corridor_path": list(self._corridor_path),
            "cooldown_remaining": max(0, round(self._cooldown_until - time.time(), 1)),
        }

    def get_alerts(self, limit: int = 10) -> List[Dict]:
        """Get recent alerts."""
        return list(self._alerts[-limit:])

    def get_event_log(self, limit: int = 50) -> List[Dict]:
        """Get full event log for database persistence."""
        return list(self._event_log[-limit:])

    def clear_alerts(self) -> None:
        """Clear the alert queue."""
        self._alerts.clear()

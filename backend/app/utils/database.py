"""
database.py — SQLite Persistence Layer
========================================
Manages persistent storage for traffic metrics, emergency events,
signal history, and system health logs.

Uses aiosqlite for async database operations. All writes are
batched and flushed periodically to minimize I/O overhead.

Tables:
  - traffic_metrics: per-tick density and vehicle counts
  - emergency_events: emergency detection log
  - signal_history: signal state changes
  - system_health_logs: system status snapshots
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("traffic-ai.database")

# Database file location
DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = DB_DIR / "traffic.db"

# SQL schema
_SCHEMA = """
CREATE TABLE IF NOT EXISTS traffic_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    lane_id TEXT NOT NULL,
    vehicle_count INTEGER NOT NULL DEFAULT 0,
    density_score REAL NOT NULL DEFAULT 0.0,
    density_level TEXT NOT NULL DEFAULT 'low',
    total_vehicles INTEGER NOT NULL DEFAULT 0,
    fps REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS emergency_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    vehicle_type TEXT,
    lane_id TEXT,
    intersection_id TEXT,
    corridor_path TEXT,
    duration_seconds REAL DEFAULT 0.0,
    resolved INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS signal_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    intersection_id TEXT NOT NULL,
    direction TEXT NOT NULL,
    state TEXT NOT NULL,
    duration_seconds REAL DEFAULT 0.0,
    density_at_change REAL DEFAULT 0.0,
    trigger TEXT DEFAULT 'auto'
);

CREATE TABLE IF NOT EXISTS system_health_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ok',
    video_source_healthy INTEGER NOT NULL DEFAULT 1,
    video_mode TEXT,
    fps REAL DEFAULT 0.0,
    active_connections INTEGER DEFAULT 0,
    uptime_seconds REAL DEFAULT 0.0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS violation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    violation_type TEXT NOT NULL,
    lane_id TEXT,
    vehicle_class TEXT,
    confidence REAL DEFAULT 0.0,
    description TEXT,
    frame_number INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS hourly_traffic_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    hour TEXT NOT NULL,
    total_vehicles INTEGER DEFAULT 0,
    avg_density REAL DEFAULT 0.0,
    health_score INTEGER DEFAULT 50,
    peak_density REAL DEFAULT 0.0,
    violations_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS intersection_health_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    health_score INTEGER DEFAULT 50,
    signal_efficiency REAL DEFAULT 50.0,
    avg_wait_time REAL DEFAULT 0.0,
    congestion_trend TEXT DEFAULT 'stable',
    weather TEXT DEFAULT 'clear'
);

CREATE INDEX IF NOT EXISTS idx_traffic_ts ON traffic_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_emergency_ts ON emergency_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_signal_ts ON signal_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_health_ts ON system_health_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_violation_ts ON violation_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_hourly_ts ON hourly_traffic_summary(timestamp);
CREATE INDEX IF NOT EXISTS idx_intersection_ts ON intersection_health_history(timestamp);
"""


class Database:
    """
    Async SQLite database manager for traffic data persistence.

    Usage:
        db = Database()
        await db.initialize()
        await db.insert_traffic_metric({...})
        await db.close()
    """

    def __init__(self, db_path: str = str(DB_PATH)) -> None:
        self.db_path = db_path
        self._conn = None
        self._initialized = False

    async def initialize(self) -> None:
        """Create the database file and tables if they don't exist."""
        import aiosqlite

        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self._conn = await aiosqlite.connect(self.db_path)
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()
        self._initialized = True
        logger.info("Database initialized at: %s", self.db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            self._initialized = False
            logger.info("Database connection closed.")

    # ------------------------------------------------------------------
    # Traffic Metrics
    # ------------------------------------------------------------------
    async def insert_traffic_metric(
        self,
        lane_id: str,
        vehicle_count: int,
        density_score: float,
        density_level: str,
        total_vehicles: int,
        fps: float,
    ) -> None:
        """Insert a traffic density measurement."""
        if not self._initialized:
            return
        ts = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            "INSERT INTO traffic_metrics (timestamp, lane_id, vehicle_count, density_score, density_level, total_vehicles, fps) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, lane_id, vehicle_count, round(density_score, 1), density_level, total_vehicles, round(fps, 1)),
        )
        await self._conn.commit()

    async def insert_traffic_metrics_batch(self, lanes: list, total_vehicles: int, fps: float) -> None:
        """Insert metrics for all lanes in one batch."""
        if not self._initialized:
            return
        ts = datetime.now(timezone.utc).isoformat()
        rows = []
        for lane in lanes:
            density = lane.get("density_score", lane.density_score if hasattr(lane, "density_score") else 0)
            count = lane.get("vehicle_count", lane.vehicle_count if hasattr(lane, "vehicle_count") else 0)
            lid = lane.get("lane_id", lane.lane_id if hasattr(lane, "lane_id") else "unknown")
            level = _classify(density)
            rows.append((ts, lid, count, round(density, 1), level, total_vehicles, round(fps, 1)))

        await self._conn.executemany(
            "INSERT INTO traffic_metrics (timestamp, lane_id, vehicle_count, density_score, density_level, total_vehicles, fps) VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        await self._conn.commit()

    # ------------------------------------------------------------------
    # Emergency Events
    # ------------------------------------------------------------------
    async def insert_emergency_event(
        self,
        event_type: str,
        vehicle_type: str = "",
        lane_id: str = "",
        intersection_id: str = "",
        corridor_path: str = "",
    ) -> int:
        """Insert an emergency event and return its ID."""
        if not self._initialized:
            return -1
        ts = datetime.now(timezone.utc).isoformat()
        cursor = await self._conn.execute(
            "INSERT INTO emergency_events (timestamp, event_type, vehicle_type, lane_id, intersection_id, corridor_path) VALUES (?, ?, ?, ?, ?, ?)",
            (ts, event_type, vehicle_type, lane_id, intersection_id, corridor_path),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def resolve_emergency(self, event_id: int, duration: float) -> None:
        """Mark an emergency event as resolved."""
        if not self._initialized:
            return
        await self._conn.execute(
            "UPDATE emergency_events SET resolved = 1, duration_seconds = ? WHERE id = ?",
            (round(duration, 1), event_id),
        )
        await self._conn.commit()

    # ------------------------------------------------------------------
    # Signal History
    # ------------------------------------------------------------------
    async def insert_signal_change(
        self,
        intersection_id: str,
        direction: str,
        state: str,
        duration: float = 0.0,
        density: float = 0.0,
        trigger: str = "auto",
    ) -> None:
        """Log a signal state change."""
        if not self._initialized:
            return
        ts = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            "INSERT INTO signal_history (timestamp, intersection_id, direction, state, duration_seconds, density_at_change, trigger) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, intersection_id, direction, state, round(duration, 1), round(density, 1), trigger),
        )
        await self._conn.commit()

    # ------------------------------------------------------------------
    # System Health
    # ------------------------------------------------------------------
    async def insert_health_log(
        self,
        status: str = "ok",
        video_healthy: bool = True,
        video_mode: str = "simulation",
        fps: float = 0.0,
        connections: int = 0,
        uptime: float = 0.0,
        error: str = "",
    ) -> None:
        """Insert a system health snapshot."""
        if not self._initialized:
            return
        ts = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            "INSERT INTO system_health_logs (timestamp, status, video_source_healthy, video_mode, fps, active_connections, uptime_seconds, error_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (ts, status, int(video_healthy), video_mode, round(fps, 1), connections, round(uptime, 1), error),
        )
        await self._conn.commit()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    async def get_recent_metrics(self, limit: int = 100) -> List[Dict]:
        """Get recent traffic metrics."""
        if not self._initialized:
            return []
        cursor = await self._conn.execute(
            "SELECT * FROM traffic_metrics ORDER BY id DESC LIMIT ?", (limit,)
        )
        cols = [d[0] for d in cursor.description]
        rows = await cursor.fetchall()
        return [dict(zip(cols, row)) for row in rows]

    async def get_recent_emergencies(self, limit: int = 50) -> List[Dict]:
        """Get recent emergency events."""
        if not self._initialized:
            return []
        cursor = await self._conn.execute(
            "SELECT * FROM emergency_events ORDER BY id DESC LIMIT ?", (limit,)
        )
        cols = [d[0] for d in cursor.description]
        rows = await cursor.fetchall()
        return [dict(zip(cols, row)) for row in rows]

    async def get_recent_signal_history(self, limit: int = 100) -> List[Dict]:
        """Get recent signal changes."""
        if not self._initialized:
            return []
        cursor = await self._conn.execute(
            "SELECT * FROM signal_history ORDER BY id DESC LIMIT ?", (limit,)
        )
        cols = [d[0] for d in cursor.description]
        rows = await cursor.fetchall()
        return [dict(zip(cols, row)) for row in rows]

    async def get_emergency_count_today(self) -> int:
        """Count emergency events today."""
        if not self._initialized:
            return 0
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cursor = await self._conn.execute(
            "SELECT COUNT(*) FROM emergency_events WHERE timestamp LIKE ?", (f"{today}%",)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    # ------------------------------------------------------------------
    # Violations
    # ------------------------------------------------------------------
    async def insert_violation(self, violation: Dict) -> None:
        """Insert a traffic violation."""
        if not self._initialized:
            return
        ts = violation.get("timestamp", datetime.now(timezone.utc).isoformat())
        await self._conn.execute(
            "INSERT INTO violation_logs (timestamp, violation_type, lane_id, vehicle_class, confidence, description, frame_number) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, violation.get("violation_type", ""), violation.get("lane_id", ""),
             violation.get("vehicle_class", ""), violation.get("confidence", 0),
             violation.get("description", ""), violation.get("frame_number", 0)),
        )
        await self._conn.commit()

    async def get_recent_violations(self, limit: int = 50) -> List[Dict]:
        """Get recent violations."""
        if not self._initialized:
            return []
        cursor = await self._conn.execute(
            "SELECT * FROM violation_logs ORDER BY id DESC LIMIT ?", (limit,)
        )
        cols = [d[0] for d in cursor.description]
        rows = await cursor.fetchall()
        return [dict(zip(cols, row)) for row in rows]

    # ------------------------------------------------------------------
    # Intersection Health History
    # ------------------------------------------------------------------
    async def insert_health_snapshot(self, health_score: int,
                                      signal_efficiency: float, avg_wait: float,
                                      trend: str, weather: str) -> None:
        if not self._initialized:
            return
        ts = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            "INSERT INTO intersection_health_history (timestamp, health_score, signal_efficiency, avg_wait_time, congestion_trend, weather) VALUES (?, ?, ?, ?, ?, ?)",
            (ts, health_score, round(signal_efficiency, 1), round(avg_wait, 1), trend, weather),
        )
        await self._conn.commit()

    async def get_health_history(self, limit: int = 100) -> List[Dict]:
        if not self._initialized:
            return []
        cursor = await self._conn.execute(
            "SELECT * FROM intersection_health_history ORDER BY id DESC LIMIT ?", (limit,)
        )
        cols = [d[0] for d in cursor.description]
        rows = await cursor.fetchall()
        return [dict(zip(cols, row)) for row in rows]


def _classify(density: float) -> str:
    """Classify density score into level."""
    if density < 25:
        return "low"
    elif density < 50:
        return "medium"
    elif density < 75:
        return "high"
    return "critical"

"""
frame_streamer.py — Annotated Frame Buffer & JPEG Streaming
============================================================
Manages per-lane frame buffers. Draws YOLOv8 bounding boxes,
class labels, confidence scores, density info, and ambulance
status onto frames using OpenCV. Encodes as JPEG for HTTP serving.
"""

from __future__ import annotations

import logging
import threading
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("traffic-ai.frame_streamer")

# Colors (BGR) for each vehicle class
CLASS_COLORS: Dict[str, Tuple[int, int, int]] = {
    "car":            (255, 180, 50),
    "truck":          (50, 180, 255),
    "bus":            (50, 255, 100),
    "motorcycle":     (255, 100, 255),
    "person":         (200, 200, 200),
    "auto_rickshaw":  (100, 255, 255),
    "e_rickshaw":     (255, 255, 100),
    "ambulance":      (0, 0, 255),
}


class FrameStreamer:
    """
    Manages per-lane annotated frame buffers.
    Thread-safe storage and retrieval of JPEG-encoded annotated frames.
    """

    def __init__(self):
        self._buffers: Dict[str, bytes] = {}  # lane_id -> JPEG bytes
        self._lock = threading.Lock()
        self._lane_stats: Dict[str, Dict] = {}  # lane_id -> stats dict

    def annotate_and_store(
        self,
        lane_id: str,
        frame: np.ndarray,
        detections: list,
        density: int,
        ambulance_detected: bool,
        green_time: Optional[int],
        signal_color: str = "red",
    ) -> None:
        """
        Draw bounding boxes + overlay text on frame, then store as JPEG.

        Args:
            lane_id: e.g. "Lane 1"
            frame: BGR numpy array (will be copied)
            detections: list of {class, confidence, bbox: [x1,y1,x2,y2]}
            density: vehicle count in this lane
            ambulance_detected: whether an ambulance is present
            green_time: seconds of green allocated (None if red)
            signal_color: "red" or "green"
        """
        annotated = frame.copy()
        h, w = annotated.shape[:2]

        # Draw bounding boxes
        for det in detections:
            cls_name = det.get("class", "unknown")
            conf = det.get("confidence", 0.0)
            bbox = det.get("bbox", [0, 0, 0, 0])
            x1, y1, x2, y2 = bbox

            color = CLASS_COLORS.get(cls_name, (200, 200, 200))
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            label = f"{cls_name.replace('_', ' ').title()} {conf:.2f}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(
                annotated,
                (x1, y1 - label_size[1] - 6),
                (x1 + label_size[0] + 4, y1),
                color, -1,
            )
            cv2.putText(
                annotated, label, (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA,
            )

        # Lane label overlay
        cv2.putText(
            annotated, lane_id, (w - 150, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA,
        )

        # Status bar at bottom
        amb_text = "YES!" if ambulance_detected else "No"
        time_text = str(green_time) if green_time else "--"
        status = f"Density: {density} | Ambulance: {amb_text} | Time: {time_text}"

        bar_h = 30
        cv2.rectangle(annotated, (0, h - bar_h), (w, h), (0, 0, 0), -1)
        cv2.putText(
            annotated, status, (10, h - 8),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA,
        )

        # Encode as JPEG
        _, jpeg_buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])

        with self._lock:
            self._buffers[lane_id] = jpeg_buf.tobytes()

    def get_frame(self, lane_id: str) -> Optional[bytes]:
        """Get latest JPEG frame for a lane."""
        with self._lock:
            return self._buffers.get(lane_id)

    def get_placeholder_frame(self, lane_id: str, width: int = 640, height: int = 480) -> bytes:
        """Generate a black placeholder frame with lane label."""
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        cv2.putText(
            frame, f"{lane_id} - Waiting for video...",
            (width // 6, height // 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 2, cv2.LINE_AA,
        )
        _, jpeg_buf = cv2.imencode(".jpg", frame)
        return jpeg_buf.tobytes()

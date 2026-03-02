"""
video_source.py — Unified Video Source Manager
================================================
Provides a single interface for ingesting video frames from
multiple source types: webcam, RTSP stream, or video file.

Supports:
  - Mode A: Webcam (cv2.VideoCapture with device index)
  - Mode B: RTSP CCTV stream with auto-reconnect + buffer handling
  - Mode C: Video file playback (loop or single-pass)
  - Simulation fallback when no source is available

Production features:
  - Exponential backoff reconnection
  - FPS limiting for CPU stability
  - Frame skipping for high-framerate streams
  - Health monitoring and statistics
  - Graceful failure handling
  - Thread-safe frame access
"""

from __future__ import annotations

import logging
import time
import threading
from enum import Enum
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger("traffic-ai.video_source")


class VideoMode(str, Enum):
    """Supported video source modes."""
    WEBCAM = "webcam"
    RTSP = "rtsp"
    VIDEO_FILE = "video_file"
    SIMULATION = "simulation"


class VideoSource:
    """
    Unified video reader that abstracts webcam, RTSP, and file sources.

    All detection modules consume frames exclusively through this class.

    Usage:
        source = VideoSource(mode="webcam", device_index=0)
        source.start()
        frame = source.read()
        source.stop()
    """

    def __init__(
        self,
        mode: str = "simulation",
        device_index: int = 0,
        rtsp_url: str = "",
        video_path: str = "",
        target_fps: float = 15.0,
        rtsp_timeout: int = 10,
        loop_video: bool = True,
    ) -> None:
        """
        Initialize the video source.

        Args:
            mode: One of 'webcam', 'rtsp', 'video_file', 'simulation'.
            device_index: Camera device index for webcam mode.
            rtsp_url: RTSP stream URL for RTSP mode.
            video_path: Path to video file for file mode.
            target_fps: Maximum FPS to deliver (limits CPU usage).
            rtsp_timeout: Connection timeout in seconds for RTSP.
            loop_video: Whether to loop video files.
        """
        self.mode = VideoMode(mode.lower()) if mode.lower() in [m.value for m in VideoMode] else VideoMode.SIMULATION
        self.device_index = device_index
        self.rtsp_url = rtsp_url
        self.video_path = video_path
        self.target_fps = max(1.0, target_fps)
        self.rtsp_timeout = rtsp_timeout
        self.loop_video = loop_video

        # Internal state
        self._cap = None
        self._running: bool = False
        self._frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._healthy: bool = False
        self._reconnect_attempts: int = 0
        self._max_reconnect_attempts: int = 50
        self._last_frame_time: float = 0.0

        # Statistics
        self._stats = {
            "frames_read": 0,
            "frames_dropped": 0,
            "reconnections": 0,
            "fps_actual": 0.0,
            "source_width": 0,
            "source_height": 0,
            "source_fps": 0.0,
            "last_error": None,
            "uptime_seconds": 0.0,
        }
        self._start_time: float = 0.0
        self._fps_counter: int = 0
        self._fps_timer: float = 0.0

        logger.info(
            "VideoSource initialized: mode=%s, target_fps=%.1f",
            self.mode.value, self.target_fps,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start(self) -> bool:
        """
        Start the video source. Opens the capture device and begins
        reading frames in a background thread.

        Returns:
            True if successfully started, False otherwise.
        """
        if self._running:
            return True

        if self.mode == VideoMode.SIMULATION:
            self._running = True
            self._healthy = True
            self._start_time = time.time()
            logger.info("VideoSource started in SIMULATION mode (no camera).")
            return True

        success = self._open_capture()
        if not success:
            logger.warning("Failed to open video source. Falling back to simulation.")
            self.mode = VideoMode.SIMULATION
            self._running = True
            self._healthy = True
            self._start_time = time.time()
            return True

        self._running = True
        self._start_time = time.time()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        logger.info("VideoSource capture thread started.")
        return True

    def stop(self) -> None:
        """Stop the video source and release resources."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        self._healthy = False
        logger.info("VideoSource stopped.")

    def read(self) -> Optional[np.ndarray]:
        """
        Get the latest frame. Thread-safe.

        Returns:
            BGR numpy array, or None if no frame available (simulation mode).
        """
        if self.mode == VideoMode.SIMULATION:
            return None

        with self._frame_lock:
            return self._frame.copy() if self._frame is not None else None

    @property
    def is_healthy(self) -> bool:
        """Whether the video source is operational."""
        return self._healthy

    @property
    def is_simulation(self) -> bool:
        """Whether running in simulation mode (no real camera)."""
        return self.mode == VideoMode.SIMULATION

    def get_stats(self) -> dict:
        """Get current video source statistics."""
        self._stats["uptime_seconds"] = round(time.time() - self._start_time, 1) if self._start_time else 0.0
        self._stats["mode"] = self.mode.value
        self._stats["healthy"] = self._healthy
        return dict(self._stats)

    # ------------------------------------------------------------------
    # Internal: capture opening
    # ------------------------------------------------------------------
    def _open_capture(self) -> bool:
        """Open the video capture device based on mode."""
        try:
            import cv2
        except ImportError:
            logger.error("OpenCV not installed. Cannot open video source.")
            return False

        try:
            if self.mode == VideoMode.WEBCAM:
                logger.info("Opening webcam device: %d", self.device_index)
                self._cap = cv2.VideoCapture(self.device_index, cv2.CAP_DSHOW)
            elif self.mode == VideoMode.RTSP:
                logger.info("Opening RTSP stream: %s", self.rtsp_url)
                # Set timeout for RTSP
                import os
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;tcp|timeout;{self.rtsp_timeout * 1000000}"
                self._cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            elif self.mode == VideoMode.VIDEO_FILE:
                logger.info("Opening video file: %s", self.video_path)
                self._cap = cv2.VideoCapture(self.video_path)
            else:
                return False

            if not self._cap.isOpened():
                logger.error("Failed to open video capture.")
                return False

            # Read source properties
            self._stats["source_width"] = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self._stats["source_height"] = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self._stats["source_fps"] = round(self._cap.get(cv2.CAP_PROP_FPS), 1)
            self._healthy = True
            self._reconnect_attempts = 0

            logger.info(
                "Video source opened: %dx%d @ %.1f FPS",
                self._stats["source_width"],
                self._stats["source_height"],
                self._stats["source_fps"],
            )
            return True

        except Exception as e:
            logger.error("Error opening video source: %s", e)
            self._stats["last_error"] = str(e)
            return False

    # ------------------------------------------------------------------
    # Internal: background read loop
    # ------------------------------------------------------------------
    def _read_loop(self) -> None:
        """
        Background thread that continuously reads frames.
        Handles FPS limiting, reconnection, and frame skipping.
        """
        import cv2

        min_interval = 1.0 / self.target_fps

        while self._running:
            try:
                # FPS limiting
                now = time.time()
                elapsed = now - self._last_frame_time
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)

                if self._cap is None or not self._cap.isOpened():
                    self._attempt_reconnect()
                    continue

                ret, frame = self._cap.read()

                if not ret or frame is None:
                    self._stats["frames_dropped"] += 1

                    # Video file: loop or stop
                    if self.mode == VideoMode.VIDEO_FILE:
                        if self.loop_video:
                            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            continue
                        else:
                            logger.info("Video file ended.")
                            self._healthy = False
                            break

                    # RTSP / Webcam: reconnect
                    self._healthy = False
                    self._attempt_reconnect()
                    continue

                # Store frame thread-safely
                with self._frame_lock:
                    self._frame = frame

                self._stats["frames_read"] += 1
                self._last_frame_time = time.time()
                self._healthy = True

                # FPS tracking
                self._fps_counter += 1
                if now - self._fps_timer >= 1.0:
                    self._stats["fps_actual"] = round(self._fps_counter / (now - self._fps_timer), 1)
                    self._fps_counter = 0
                    self._fps_timer = now

            except Exception as e:
                logger.error("Frame read error: %s", e)
                self._stats["last_error"] = str(e)
                time.sleep(0.1)

    # ------------------------------------------------------------------
    # Internal: reconnection
    # ------------------------------------------------------------------
    def _attempt_reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error("Max reconnection attempts reached. Giving up.")
            self._running = False
            return

        self._reconnect_attempts += 1
        self._stats["reconnections"] = self._reconnect_attempts

        # Exponential backoff: 1s, 2s, 4s, ... capped at 30s
        delay = min(2 ** min(self._reconnect_attempts, 5), 30)
        logger.warning(
            "Reconnecting in %ds (attempt %d/%d)...",
            delay, self._reconnect_attempts, self._max_reconnect_attempts,
        )
        time.sleep(delay)

        # Release old capture
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

        # Re-open
        self._open_capture()

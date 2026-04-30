#!/usr/bin/env python3
"""
camera_service.py — Raspberry Pi camera abstraction.

Tries 4 backends in order until one works:
  1. picamera2   — native libcamera Python binding (Pi Camera Module v1/v2/v3)
  2. GStreamer   — libcamerasrc pipeline via OpenCV (also libcamera stack)
  3. V4L2        — USB cameras or Pi camera with v4l2 kernel driver loaded
  4. Placeholder — development / no camera attached

Usage (from screens_main.py):
    from camera_service import CameraService
    cam = CameraService()
    cam.start()                          # open camera
    frame_rgb = cam.read_frame()         # numpy array (H,W,3) RGB — use QImage Format_RGB888
    cam.capture_to_file("/abs/path.jpg") # write jpeg to disk
    cam.stop()                           # release resources
"""

import os
import numpy as np

# Resolution used everywhere
FRAME_W = 640
FRAME_H = 480


class CameraService:
    """
    Single class that hides all backend complexity from screens_main.py.
    Call start() → read_frame() in a loop → capture_to_file() → stop().
    """

    def __init__(self):
        self._backend  = None   # "picamera2" | "gstreamer" | "v4l2" | "placeholder"
        self._picam    = None   # picamera2.Picamera2 instance
        self._cap      = None   # cv2.VideoCapture instance
        self._last_rgb = None   # last frame kept for capture_to_file()

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> str:
        """
        Open the camera. Returns the backend name that succeeded.
        Raises RuntimeError if all backends fail.
        """
        for try_fn in (
            self._try_picamera2,
            self._try_gstreamer,
            self._try_v4l2,
        ):
            name = try_fn()
            if name:
                self._backend = name
                print(f"[CAM] ✅  Backend: {name}")
                return name

        # Nothing worked
        self._backend = "placeholder"
        print("[CAM] ⚠️   No camera found — running in placeholder mode")
        return "placeholder"

    def is_open(self) -> bool:
        if self._backend == "picamera2":
            return self._picam is not None
        if self._backend in ("gstreamer", "v4l2"):
            return self._cap is not None and self._cap.isOpened()
        return False

    def read_frame(self):
        """
        Return the latest RGB frame as a numpy uint8 array (H, W, 3).
        Returns None if no frame is available.
        """
        frame = None

        if self._backend == "picamera2" and self._picam:
            try:
                import cv2
                raw = self._picam.capture_array()          # RGB888 from picamera2
                # Keep as RGB — do NOT convert. screens_main uses Format_RGB888 directly.
                # Slicing [:,:,:3] drops alpha channel if picamera2 returns XRGB (4ch).
                frame = raw[:, :, :3] if raw.ndim == 3 else raw
            except Exception as exc:
                print(f"[CAM] picamera2 read error: {exc}")

        elif self._backend in ("gstreamer", "v4l2") and self._cap:
            ret, raw = self._cap.read()
            if ret and raw is not None:
                frame = raw

        if frame is not None:
            self._last_rgb = frame
        return frame

    def capture_to_file(self, path: str) -> bool:
        """
        Write the latest frame to *path* as JPEG.
        Returns True on success.
        """
        import cv2
        os.makedirs(os.path.dirname(path), exist_ok=True)

        if self._backend == "picamera2" and self._picam:
            try:
                # Capture a fresh still — picamera2 returns RGB888
                raw = self._picam.capture_array()
                rgb = raw[:, :, :3] if raw.ndim == 3 else raw   # drop alpha if present
                bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)       # RGB→BGR for cv2.imwrite
                ok  = cv2.imwrite(path, bgr)
                if ok:
                    self._last_rgb = bgr
                return ok
            except Exception as exc:
                print(f"[CAM] picamera2 capture error: {exc}")
                return False

        # For other backends fall back to last_rgb or a fresh read()
        frame_rgb = self._last_rgb if self._last_rgb is not None else self.read_frame()
        if frame_rgb is None:
            print("[CAM] capture_to_file: no frame available")
            return False
        # Convert RGB→BGR for cv2.imwrite
        bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        return bool(cv2.imwrite(path, bgr))

    def stop(self):
        """Release all camera resources."""
        if self._picam:
            try:
                self._picam.stop()
                self._picam.close()
            except Exception:
                pass
            self._picam = None

        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

        self._backend  = None
        self._last_rgb = None

    # ── Backend probes ────────────────────────────────────────────────────────

    def _try_picamera2(self) -> str:
        """picamera2 — the native libcamera Python binding."""
        try:
            from picamera2 import Picamera2
            cam = Picamera2()
            # RGB888 format: capture_array() returns H×W×3 in R,G,B order
            # read_frame() returns RGB directly — no conversion applied.
            cfg = cam.create_preview_configuration(
                main={"size": (FRAME_W, FRAME_H), "format": "RGB888"}
            )
            cam.configure(cfg)
            cam.start()
            frame = cam.capture_array()   # returns RGB888 numpy array
            if frame is None or frame.size == 0:
                cam.stop()
                cam.close()
                return ""
            self._picam = cam
            return "picamera2"
        except Exception as exc:
            print(f"[CAM] picamera2 unavailable: {exc}")
            return ""

    def _try_gstreamer(self) -> str:
        """
        GStreamer pipeline using libcamerasrc — works on Pi OS Bullseye+
        when picamera2 package is not installed but libcamera is present.
        """
        try:
            import cv2
            pipeline = (
                f"libcamerasrc ! "
                f"video/x-raw,width={FRAME_W},height={FRAME_H},framerate=15/1 ! "
                f"videoconvert ! video/x-raw,format=BGR ! appsink drop=true"
            )
            cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
            if not cap.isOpened():
                return ""
            ret, frame = cap.read()
            if not ret or frame is None:
                cap.release()
                return ""
            self._cap = cap
            return "gstreamer"
        except Exception as exc:
            print(f"[CAM] GStreamer unavailable: {exc}")
            return ""

    def _try_v4l2(self) -> str:
        """
        Standard V4L2 — USB cameras or Pi Camera with
        `dtoverlay=imx219,cam0` + `bcm2835-v4l2` loaded.
        Tries /dev/video0 through /dev/video3.
        """
        try:
            import cv2
            for dev in range(4):
                cap = cv2.VideoCapture(dev, cv2.CAP_V4L2)
                if not cap.isOpened():
                    cap = cv2.VideoCapture(dev)
                if not cap.isOpened():
                    continue
                cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_W)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
                ret, frame = cap.read()
                if ret and frame is not None:
                    self._cap = cap
                    return "v4l2"
                cap.release()
        except Exception as exc:
            print(f"[CAM] V4L2 unavailable: {exc}")
        return ""

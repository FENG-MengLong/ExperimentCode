"""Synchronous, precision-preserving camera acquisition; no GUI dependency."""

from contextlib import contextmanager
from dataclasses import dataclass
import math
from threading import RLock, get_ident
import time

import numpy as np

from .sdk import open_sdk


@dataclass(frozen=True)
class Frame:
    """Owned raw pixels plus acquisition metadata (host time is not trigger time)."""

    image: np.ndarray
    serial: str
    frame_number: int
    host_time_ns: int
    camera_time_ns: int | None
    bit_depth: int
    exposure_us: int
    sensor_type: str

    def metadata(self) -> dict:
        return {
            "serial": self.serial,
            "frame_number": self.frame_number,
            "host_time_ns": self.host_time_ns,
            "camera_time_ns": self.camera_time_ns,
            "bit_depth": self.bit_depth,
            "exposure_us": self.exposure_us,
            "sensor_type": self.sensor_type,
            "shape": list(self.image.shape),
            "dtype": str(self.image.dtype),
        }

    def preview(self) -> np.ndarray:
        """Fixed full-scale 8-bit rendering; raw pixels are never modified.

        Bayer cameras are displayed as raw grayscale, not demosaiced color.
        """
        maximum = (1 << self.bit_depth) - 1
        return (np.clip(self.image.astype(np.float32), 0, maximum) * (255 / maximum)).astype(np.uint8)


def list_cameras() -> list[str]:
    """Discover serials. Call before opening a Camera/LiveMonitor."""
    sdk, _ = open_sdk()
    try:
        return list(sdk.discover_available_cameras())
    finally:
        sdk.dispose()


class Camera:
    """One camera/SDK connection shared by scripts OR a live acquisition worker.

    All SDK calls are serialized. During live acquisition, script calls fail
    explicitly rather than stealing frames from the monitor (or vice versa).
    """

    def __init__(self, serial: str | None = None):
        self._lock = RLock()
        self._owner = None
        self._armed = False
        self._camera = None
        self._sdk = None
        self._trigger = "software"
        self._sdk, self._modes = open_sdk()
        try:
            serials = list(self._sdk.discover_available_cameras())
            if not serials:
                raise RuntimeError("No camera found. Check USB connection and vendor udev permissions.")
            if serial is None:
                if len(serials) != 1:
                    raise ValueError(f"Select a serial explicitly; detected cameras: {serials}")
                serial = serials[0]
            if serial not in serials:
                raise ValueError(f"Camera {serial!r} not found; detected cameras: {serials}")
            self.serial = serial
            self._camera = self._sdk.open_camera(serial)
        except BaseException:
            self._sdk.dispose()
            self._sdk = None
            raise

    def _check_access(self):
        if self._camera is None:
            raise RuntimeError("Camera is closed.")
        if self._owner is not None and self._owner != get_ident():
            raise RuntimeError("Live acquisition owns the camera. Stop the live monitor first.")

    @contextmanager
    def _exclusive_acquisition(self):
        """Reserve SDK access for the live worker for its entire lifetime."""
        with self._lock:
            self._check_access()
            if self._owner is not None or self._armed:
                raise RuntimeError("Camera is already acquiring; disarm it before starting live mode.")
            self._owner = get_ident()
        try:
            yield
        finally:
            with self._lock:
                self._owner = None

    def configure(
        self,
        exposure_us: int = 10000,
        trigger: str = "software",
        continuous: bool = False,
        gain: int | None = None,
        fps: float | None = None,
    ) -> None:
        """Disarm and configure. Gain is in vendor SDK index units, not dB.

        Hardware mode produces one frame per external edge. Continuous mode is
        software-triggered only. Device-specific ranges are checked by the SDK.
        """
        if trigger not in ("software", "external"):
            raise ValueError("trigger must be 'software' or 'external'")
        if continuous and trigger != "software":
            raise ValueError("Continuous live mode requires software triggering.")
        if exposure_us <= 0 or int(exposure_us) != exposure_us:
            raise ValueError("exposure_us must be a positive integer")
        if fps is not None and (not math.isfinite(fps) or fps <= 0):
            raise ValueError("fps must be finite and positive")
        with self._lock:
            self._check_access()
            self.disarm()
            cam = self._camera
            cam.operation_mode = (
                self._modes.SOFTWARE_TRIGGERED if trigger == "software"
                else self._modes.HARDWARE_TRIGGERED
            )
            cam.exposure_time_us = int(exposure_us)
            cam.frames_per_trigger_zero_for_unlimited = 0 if continuous else 1
            cam.image_poll_timeout_ms = 50
            if gain is not None:
                cam.gain = int(gain)
            # Use the documented SDK property, not a guessed capability flag.
            # Vendor errors (unsupported device/range) are deliberately surfaced.
            has_fps_control = hasattr(cam, "is_frame_rate_control_enabled")
            if fps is not None:
                if not has_fps_control:
                    raise ValueError("This SDK does not expose frame-rate control.")
                # Zelux resets the rate when control is enabled: enable FIRST.
                cam.is_frame_rate_control_enabled = True
                cam.frame_rate_control_value = fps
            elif has_fps_control:
                cam.is_frame_rate_control_enabled = False
            self._trigger = trigger

    def arm(self, buffers: int = 8) -> None:
        if buffers < 1:
            raise ValueError("buffers must be positive")
        with self._lock:
            self._check_access()
            if not self._armed:
                self._camera.arm(buffers)
                self._armed = True

    def disarm(self) -> None:
        with self._lock:
            self._check_access()
            if self._armed:
                self._camera.disarm()
                self._armed = False

    def trigger(self) -> None:
        with self._lock:
            self._check_access()
            if not self._armed or self._trigger != "software":
                raise RuntimeError("Software triggering requires an armed camera in software mode.")
            self._camera.issue_software_trigger()

    def read_frame(self, timeout_s: float = 2.0) -> Frame:
        """Wait for the next queued frame, with a finite overall deadline.

        Does not trigger. Arm before starting the external experiment sequence.
        A timeout leaves the camera armed so the caller can retry or disarm.
        """
        if not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError("timeout_s must be finite and positive")
        with self._lock:
            self._check_access()
            if not self._armed:
                raise RuntimeError("Arm the camera before reading a frame.")
            deadline = time.monotonic() + timeout_s
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"No frame within {timeout_s:g} s ({self._trigger} trigger).")
                self._camera.image_poll_timeout_ms = max(1, min(50, math.ceil(remaining * 1000)))
                raw = self._camera.get_pending_frame_or_null()
                if raw is not None:
                    host_time = time.time_ns()
                    pixels = np.array(raw.image_buffer, copy=True).reshape(
                        self._camera.image_height_pixels, self._camera.image_width_pixels
                    )
                    pixels.flags.writeable = False
                    return Frame(
                        image=pixels,
                        serial=self.serial,
                        frame_number=int(raw.frame_count),
                        host_time_ns=host_time,
                        camera_time_ns=(
                            int(raw.time_stamp_relative_ns_or_null)
                            if getattr(raw, "time_stamp_relative_ns_or_null", None) is not None
                            else None
                        ),
                        bit_depth=int(self._camera.bit_depth),
                        exposure_us=int(self._camera.exposure_time_us),
                        sensor_type=str(self._camera.camera_sensor_type),
                    )

    def capture(self, exposure_us: int = 10000, timeout_s: float = 2.0) -> Frame:
        """Configure, arm, software-trigger and capture exactly one image."""
        with self._lock:
            self.configure(exposure_us=exposure_us)
            try:
                self.arm()
                self.trigger()
                return self.read_frame(timeout_s)
            finally:
                self.disarm()

    def close(self) -> None:
        """Idempotent cleanup. Stop any live worker before closing."""
        with self._lock:
            if self._camera is None:
                return
            self._check_access()
            try:
                self.disarm()
            finally:
                try:
                    self._camera.dispose()
                finally:
                    self._camera = None
                    self._armed = False
                    try:
                        self._sdk.dispose()
                    finally:
                        self._sdk = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

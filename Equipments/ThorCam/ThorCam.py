from pathlib import Path
from typing import Union

import numpy as np
import cv2

try:
    # If you are on Windows and using the relative-path DLL setup script
    from .windows_setup import configure_path
    configure_path()
except ImportError:
    pass
    print(1)

from thorlabs_tsi_sdk.tl_camera import TLCameraSDK, OPERATION_MODE


class ThorCamManager:
    """Small helper for finding connected camera serial numbers."""

    @staticmethod
    def list_available_serial_numbers() -> list[str]:
        """Return all detected Thorlabs camera serial numbers."""
        with TLCameraSDK() as sdk:
            return list(sdk.discover_available_cameras())


class Zelux:
    """Simple Thorlabs camera wrapper for single-frame acquisition."""

    def __init__(self, camera_serial: str):
        """Open one camera by serial number."""
        self.sdk = TLCameraSDK()
        available_cameras = list(self.sdk.discover_available_cameras())

        if not available_cameras:
            self.sdk.dispose()
            raise RuntimeError("No Thorlabs cameras detected.")

        if camera_serial not in available_cameras:
            self.sdk.dispose()
            raise ValueError(
                f"camera_serial={camera_serial!r} was not found. "
                f"Detected camera serial number(s): {available_cameras}"
            )

        self.camera_serial = camera_serial
        self.camera = self.sdk.open_camera(camera_serial)
        self._is_armed = False

    def set_trigger_mode(self, trigger_mode: str = "software") -> None:
        """Set the camera trigger mode."""
        trigger_mode = trigger_mode.strip().lower()

        if trigger_mode == "software":
            self.camera.operation_mode = OPERATION_MODE.SOFTWARE_TRIGGERED
        elif trigger_mode == "external":
            self.camera.operation_mode = OPERATION_MODE.HARDWARE_TRIGGERED
        else:
            raise ValueError("trigger_mode must be 'software' or 'external'.")

    def set_single_acquisition(
        self,
        exposure_time_us: int = 10000,
        trigger_mode: str = "software",
        image_poll_timeout_ms: int = 1000,
    ) -> None:
        """Set parameters for a single-frame acquisition.

        This method only configures the camera. It does not arm the camera.
        """
        self.camera.disarm()
        self.camera.exposure_time_us = exposure_time_us
        self.camera.image_poll_timeout_ms = image_poll_timeout_ms
        self.camera.frames_per_trigger_zero_for_unlimited = 1
        self.set_trigger_mode(trigger_mode)

    def arm(self, buffer_frame_count: int = 2) -> None:
        """Arm the camera for acquisition."""
        if self._is_armed:
            raise RuntimeError("Camera is already armed.")

        self.camera.arm(buffer_frame_count)
        self._is_armed = True

    def disarm(self) -> None:
        """Disarm the camera."""
        if self._is_armed:
            self.camera.disarm()
            self._is_armed = False

    def issue_software_trigger(self) -> None:
        """Issue a software trigger."""
        if not self._is_armed:
            raise RuntimeError("Camera must be armed before issuing a trigger.")

        if self.camera.operation_mode != OPERATION_MODE.SOFTWARE_TRIGGERED:
            raise RuntimeError(
                "Camera is not in software trigger mode. "
                "Set trigger_mode='software' first."
            )

        self.camera.issue_software_trigger()

    def read_frame(self) -> np.ndarray:
        """Read one pending frame and return it as a 2D NumPy array."""
        if not self._is_armed:
            raise RuntimeError("Camera must be armed before reading a frame.")

        frame = self.camera.get_pending_frame_or_null()
        if frame is None:
            raise RuntimeError("Unable to acquire image.")

        image_buffer_copy = np.copy(frame.image_buffer)
        return image_buffer_copy.reshape(
            self.camera.image_height_pixels,
            self.camera.image_width_pixels,
        )

    def grab_single_frame(
        self,
        exposure_time_us: int = 10000,
        trigger_mode: str = "software",
        image_poll_timeout_ms: int = 1000,
        buffer_frame_count: int = 2,
    ) -> np.ndarray:
        """Perform a complete single-frame acquisition."""
        self.set_single_acquisition(
            exposure_time_us=exposure_time_us,
            trigger_mode=trigger_mode,
            image_poll_timeout_ms=image_poll_timeout_ms,
        )
        self.arm(buffer_frame_count=buffer_frame_count)

        try:
            if trigger_mode.strip().lower() == "software":
                self.issue_software_trigger()

            return self.read_frame()
        finally:
            self.disarm()


    def close(self) -> None:
        """Close the camera and release SDK resources."""
        self.disarm()

        if self.camera is not None:
            self.camera.dispose()
            self.camera = None

        if self.sdk is not None:
            self.sdk.dispose()
            self.sdk = None
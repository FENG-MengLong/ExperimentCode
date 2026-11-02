"""Offline tests: no vendor SDK, USB access, or real video encoder required."""

import importlib.util
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from Equipments.ThorCamLinux import Camera, LiveStream, output_path, save_frame
from Equipments.ThorCamLinux.camera import list_cameras
from Equipments.ThorCamLinux.storage import VideoRecorder


class FakeDevice:
    image_height_pixels = 2
    image_width_pixels = 4
    bit_depth = 12
    camera_sensor_type = "MONOCHROME"
    exposure_time_us = 10000
    image_poll_timeout_ms = 50
    frames_per_trigger_zero_for_unlimited = 1
    _fps_enabled = False

    @property
    def is_frame_rate_control_enabled(self):
        return self._fps_enabled

    @is_frame_rate_control_enabled.setter
    def is_frame_rate_control_enabled(self, enabled):
        self._fps_enabled = enabled
        if enabled:
            # Observed on CS165MU1: enabling resets the configured frame rate.
            self.frame_rate_control_value = 34.815

    def __init__(self):
        self.armed = False
        self.pending = 0
        self.continuous = False
        self.disposed = False
        self.count = 0
        self.buffer = np.full((2, 4), 4095, dtype=np.uint16)
        self.fail_read = False

    def arm(self, buffers):
        self.armed = True

    def disarm(self):
        self.armed = self.continuous = False
        self.pending = 0

    def issue_software_trigger(self):
        self.pending += 1
        self.continuous = self.frames_per_trigger_zero_for_unlimited == 0

    def get_pending_frame_or_null(self):
        if self.fail_read:
            raise RuntimeError("simulated USB failure")
        if not self.continuous and not self.pending:
            time.sleep(self.image_poll_timeout_ms / 1000)
            return None
        time.sleep(0.002)
        self.pending = max(0, self.pending - 1)
        self.count += 1
        self.buffer.fill(4096 - self.count)
        return SimpleNamespace(
            image_buffer=self.buffer, frame_count=self.count,
            time_stamp_relative_ns_or_null=self.count * 10000000,
        )

    def dispose(self):
        self.disposed = True


class FakeSDK:
    def __init__(self, device):
        self.device = device
        self.disposed = False

    def discover_available_cameras(self):
        return ["test-serial"]

    def open_camera(self, serial):
        return self.device

    def dispose(self):
        self.disposed = True


class CameraTests(unittest.TestCase):
    def setUp(self):
        self.device = FakeDevice()
        self.sdk = FakeSDK(self.device)
        self.patch = patch(
            "Equipments.ThorCamLinux.camera.open_sdk",
            return_value=(self.sdk, SimpleNamespace(SOFTWARE_TRIGGERED=0, HARDWARE_TRIGGERED=1)),
        )
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.camera = Camera()
        self.addCleanup(self.camera.close)

    def test_capture_owned_raw_pixels(self):
        first = self.camera.capture()
        second = self.camera.capture()
        self.assertEqual(first.image.dtype, np.uint16)
        self.assertEqual(first.image.shape, (2, 4))
        self.assertEqual(first.image[0, 0], 4095)
        self.assertEqual(second.image[0, 0], 4094)
        self.assertFalse(first.image.flags.writeable)
        self.assertEqual(first.preview()[0, 0], 255)
        self.assertFalse(self.device.armed)
        self.assertEqual(first.camera_time_ns, 10000000)

    def test_external_trigger_and_timeout(self):
        self.camera.configure(exposure_us=900, trigger="external")
        self.camera.arm()
        with self.assertRaises(TimeoutError):
            self.camera.read_frame(timeout_s=0.02)
        self.assertTrue(self.device.armed)
        with self.assertRaises(RuntimeError):
            self.camera.trigger()
        self.device.pending = 1  # simulate one physical trigger edge
        self.assertEqual(self.camera.read_frame().exposure_us, 900)

    def test_read_requires_arm(self):
        with self.assertRaises(RuntimeError):
            self.camera.read_frame()

    def test_invalid_settings(self):
        for settings in ({"exposure_us": -1}, {"trigger": "invalid"}, {"fps": 0},
                         {"continuous": True, "trigger": "external"}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                self.camera.configure(**settings)

    def test_frame_rate_setting_and_reset(self):
        # Regression: setting FPS before enabling control silently loses the rate.
        self.camera.configure(fps=20)
        self.assertEqual(self.device.frame_rate_control_value, 20)
        self.assertTrue(self.device.is_frame_rate_control_enabled)
        self.camera.configure()
        self.assertFalse(self.device.is_frame_rate_control_enabled)

    def test_failed_capture_disarms(self):
        self.device.fail_read = True
        with self.assertRaises(RuntimeError):
            self.camera.capture()
        self.assertFalse(self.device.armed)

    def test_close_is_idempotent(self):
        self.camera.close()
        self.camera.close()
        self.assertTrue(self.device.disposed)
        self.assertTrue(self.sdk.disposed)
        with self.assertRaises(RuntimeError):
            self.camera.capture()

    def test_invalid_serial_releases_sdk(self):
        with self.assertRaises(ValueError):
            Camera("wrong")
        self.assertTrue(self.sdk.disposed)

    def test_discovery_releases_sdk(self):
        self.assertEqual(list_cameras(), ["test-serial"])
        self.assertTrue(self.sdk.disposed)

    def test_context_manager_cleanup(self):
        with self.camera:
            self.camera.capture()
        self.assertTrue(self.device.disposed)

    def test_cleanup_even_if_disarm_raises(self):
        self.camera.arm()
        with patch.object(self.device, "disarm", side_effect=RuntimeError("disarm failed")):
            with self.assertRaises(RuntimeError):
                self.camera.close()
        self.assertTrue(self.device.disposed)
        self.assertTrue(self.sdk.disposed)

    def test_stream_ownership_and_release(self):
        stream = LiveStream(self.camera)
        try:
            stream.start()
            deadline = time.monotonic() + 2
            while stream.latest is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertIsNotNone(stream.latest)
            with self.assertRaisesRegex(RuntimeError, "Stop the live monitor"):
                self.camera.capture()
            with self.assertRaises(RuntimeError):
                self.camera.close()
        finally:
            stream.stop()
        self.assertFalse(self.device.armed)
        self.assertIsNotNone(self.camera.capture())

    def test_stream_refuses_already_armed_camera(self):
        self.camera.configure(trigger="external")
        self.camera.arm()
        with self.assertRaises(RuntimeError):
            LiveStream(self.camera).start()
        self.assertTrue(self.device.armed)

    def test_stream_failure_releases_ownership(self):
        self.device.fail_read = True
        stream = LiveStream(self.camera)
        try:
            stream.start()
        except RuntimeError:
            pass  # failure can reach the caller during or just after startup
        deadline = time.monotonic() + 2
        while stream.running and time.monotonic() < deadline:
            time.sleep(0.01)
        with self.assertRaises(RuntimeError):
            stream.stop()
        self.assertFalse(self.device.armed)
        self.device.fail_read = False
        self.assertIsNotNone(self.camera.capture())

    def test_npy_snapshot_and_overwrite_protection(self):
        frame = self.camera.capture()
        with tempfile.TemporaryDirectory() as directory:
            path = output_path(directory, "shot", ".npy")
            save_frame(frame, path)
            np.testing.assert_array_equal(np.load(path), frame.image)
            metadata = json.loads(path.with_suffix(".npy.json").read_text())
            self.assertEqual(metadata["bit_depth"], 12)
            with self.assertRaises(FileExistsError):
                save_frame(frame, path)
            np.testing.assert_array_equal(np.load(path), frame.image)

    def test_existing_sidecar_not_overwritten(self):
        frame = self.camera.capture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shot.npy"
            sidecar = path.with_suffix(".npy.json")
            sidecar.write_text("original")
            with self.assertRaises(FileExistsError):
                save_frame(frame, path)
            self.assertFalse(path.exists())
            self.assertEqual(sidecar.read_text(), "original")

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "Pillow not installed")
    def test_png_keeps_raw_16bit_values(self):
        from PIL import Image
        frame = self.camera.capture()
        with tempfile.TemporaryDirectory() as directory:
            path = save_frame(frame, Path(directory) / "raw.png")
            with Image.open(path) as saved:
                np.testing.assert_array_equal(np.array(saved), frame.image)

    @unittest.skipUnless(importlib.util.find_spec("tifffile"), "tifffile not installed")
    def test_tiff_keeps_raw_values(self):
        import tifffile
        frame = self.camera.capture()
        with tempfile.TemporaryDirectory() as directory:
            path = save_frame(frame, Path(directory) / "raw.tif")
            np.testing.assert_array_equal(tifffile.imread(path), frame.image)

    def test_output_names_unique(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertNotEqual(output_path(directory), output_path(directory))
            with self.assertRaises(ValueError):
                output_path(directory, "../unsafe")

    def test_video_writer_and_metadata(self):
        frame = self.camera.capture()
        encoded = []
        writer = SimpleNamespace(
            isOpened=lambda: True, write=lambda image: encoded.append(image.copy()), release=lambda: None
        )
        cv2 = SimpleNamespace(VideoWriter=lambda *args: writer, VideoWriter_fourcc=lambda *args: 0)
        with tempfile.TemporaryDirectory() as directory, patch.dict("sys.modules", {"cv2": cv2}):
            path = Path(directory) / "test.mp4"
            recorder = VideoRecorder(path, frame, queue_size=4)
            for _ in range(3):
                recorder.submit(frame)
            recorder.close()
            recorder.close()
            self.assertEqual(recorder.written, 3)
            self.assertEqual(encoded[0].dtype, np.uint8)
            records = [json.loads(line) for line in path.with_suffix(".mp4.jsonl").read_text().splitlines()]
            self.assertEqual(records[-1]["written"], 3)
            self.assertEqual(records[1]["frame_number"], frame.frame_number)
            with self.assertRaises(FileExistsError):
                VideoRecorder(path, frame)

    def test_live_stop_finalizes_recording(self):
        released = []
        writer = SimpleNamespace(
            isOpened=lambda: True, write=lambda image: None, release=lambda: released.append(True)
        )
        cv2 = SimpleNamespace(VideoWriter=lambda *args: writer, VideoWriter_fourcc=lambda *args: 0)
        with tempfile.TemporaryDirectory() as directory, patch.dict("sys.modules", {"cv2": cv2}):
            stream = LiveStream(self.camera)
            try:
                stream.start()
                deadline = time.monotonic() + 2
                while stream.latest is None and time.monotonic() < deadline:
                    time.sleep(0.005)
                recorder = stream.start_recording(Path(directory) / "live.mp4")
                while recorder.written == 0 and time.monotonic() < deadline:
                    time.sleep(0.005)
            finally:
                stream.stop()
            self.assertGreater(recorder.written, 0)
            self.assertTrue(released)
            self.assertIsNone(stream.recorder)
            self.assertIsNotNone(self.camera.capture())

    def test_video_queue_overflow_is_counted(self):
        from threading import Event
        frame = self.camera.capture()
        entered, release = Event(), Event()

        def write(image):
            entered.set()
            release.wait(2)

        writer = SimpleNamespace(isOpened=lambda: True, write=write, release=lambda: None)
        cv2 = SimpleNamespace(VideoWriter=lambda *args: writer, VideoWriter_fourcc=lambda *args: 0)
        with tempfile.TemporaryDirectory() as directory, patch.dict("sys.modules", {"cv2": cv2}):
            recorder = VideoRecorder(Path(directory) / "test.mp4", frame, queue_size=1)
            try:
                recorder.submit(frame)
                self.assertTrue(entered.wait(1))
                recorder.submit(frame)
                recorder.submit(frame)
                self.assertEqual(recorder.dropped, 1)
            finally:
                release.set()
                recorder.close()
            self.assertEqual(recorder.written, 2)

    def test_video_encoder_failure_surfaces(self):
        def fail(image):
            raise OSError("disk full")

        writer = SimpleNamespace(isOpened=lambda: True, write=fail, release=lambda: None)
        cv2 = SimpleNamespace(VideoWriter=lambda *args: writer, VideoWriter_fourcc=lambda *args: 0)
        frame = self.camera.capture()
        with tempfile.TemporaryDirectory() as directory, patch.dict("sys.modules", {"cv2": cv2}):
            recorder = VideoRecorder(Path(directory) / "test.mp4", frame)
            recorder.submit(frame)
            with self.assertRaisesRegex(RuntimeError, "disk full"):
                recorder.close()


if __name__ == "__main__":
    unittest.main()

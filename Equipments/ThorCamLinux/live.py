"""Background acquisition independent of the notebook's display refresh rate."""

from threading import Event, RLock, Thread
import time

from .camera import Camera, Frame
from .storage import VideoRecorder, save_frame


class LiveStream:
    """Own a camera until stopped; keep only the newest frame for preview.

    Closing the stream stops acquisition/recording but leaves Camera open for
    experiment scripts. The camera is always disarmed when the worker exits.
    """

    def __init__(self, camera: Camera):
        self.camera = camera
        self._lock = RLock()
        self._stop = Event()
        self._ready = Event()
        self._thread = None
        self._latest = None
        self._recorder = None
        self.last_recording = None
        self.error = None
        self.frame_count = 0
        self.frame_gaps = 0
        self._started_at = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def latest(self) -> Frame | None:
        with self._lock:
            return self._latest

    @property
    def recorder(self) -> VideoRecorder | None:
        with self._lock:
            return self._recorder

    @property
    def fps(self) -> float:
        if self._started_at is None:
            return 0.0
        return self.frame_count / max(time.monotonic() - self._started_at, 1e-6)

    def start(self, exposure_us: int = 10000, gain: int | None = None, fps: float | None = None):
        if self.running:
            raise RuntimeError("Live stream is already running.")
        self.error = None
        self.frame_count = self.frame_gaps = 0
        self._latest = None
        self._stop.clear()
        self._ready.clear()
        self._thread = Thread(
            target=self._run, args=(exposure_us, gain, fps), name="zelux-acquisition", daemon=True
        )
        self._thread.start()
        # Initialization errors are returned to the initiating notebook cell.
        if not self._ready.wait(10):
            self._stop.set()
            raise TimeoutError("Camera initialization is still blocked in the SDK. Do not reopen it.")
        if self.error is not None:
            self._thread.join()
            raise RuntimeError(f"Could not start live capture: {self.error}") from self.error
        return self

    def _run(self, exposure_us, gain, fps):
        try:
            with self.camera._exclusive_acquisition():
                try:
                    self.camera.configure(exposure_us, continuous=True, gain=gain, fps=fps)
                    self.camera.arm()
                    self.camera.trigger()
                    self._started_at = time.monotonic()
                    self._ready.set()
                    previous = None
                    while not self._stop.is_set():
                        try:
                            frame = self.camera.read_frame(timeout_s=0.1)
                        except TimeoutError:
                            continue  # Long exposures are not acquisition errors.
                        if previous is not None:
                            self.frame_gaps += max(0, frame.frame_number - previous - 1)
                        previous = frame.frame_number
                        with self._lock:
                            self._latest = frame
                            self.frame_count += 1
                            if self._recorder is not None:
                                self._recorder.submit(frame)
                                if self._recorder.error is not None:
                                    raise RuntimeError("Video writer failed") from self._recorder.error
                finally:
                    self.camera.disarm()
        except Exception as exc:
            self.error = exc
        finally:
            try:
                self.stop_recording()
            except Exception as exc:
                self.error = self.error or exc
            self._ready.set()

    def save_snapshot(self, path):
        frame = self.latest
        if frame is None:
            raise RuntimeError("No live image yet. Start preview and wait for a frame.")
        return save_frame(frame, path)

    def start_recording(self, path, fps: float = 20, queue_size: int = 64):
        with self._lock:
            if not self.running or self._stop.is_set() or self.error is not None or self._latest is None:
                raise RuntimeError("Start live capture and wait for a frame before recording.")
            if self._recorder is not None:
                raise RuntimeError("Already recording.")
            self._recorder = VideoRecorder(path, self._latest, fps, queue_size)
            return self._recorder

    def stop_recording(self):
        with self._lock:
            recorder, self._recorder = self._recorder, None
            if recorder is not None:
                self.last_recording = recorder
        if recorder is not None:
            recorder.close()
        return recorder

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                raise TimeoutError("Camera SDK has not stopped. Do not close/reopen the camera yet.")
        self.stop_recording()
        if self.error is not None:
            raise RuntimeError(f"Live acquisition failed: {self.error}") from self.error

    close = stop

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

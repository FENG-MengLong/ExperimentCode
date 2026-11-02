"""Optional ipywidgets interface. SDK polling never runs in the UI loop."""

import asyncio
import html
from io import BytesIO

from .live import LiveStream
from .storage import output_path


class LiveMonitor:
    """Notebook panel borrowing an already-open Camera.

    Stop the monitor before using the camera in an experiment cell. ``close``
    releases widgets and the stream, but the caller still owns the Camera.
    """

    def __init__(self, camera, directory="./camera_data", preview_fps: float = 8):
        import ipywidgets as widgets

        if not 0 < preview_fps <= 30:
            raise ValueError("preview_fps must be between 0 and 30")
        self.stream = LiveStream(camera)
        self.preview_fps = preview_fps
        self._task = None
        self.directory = widgets.Text(value=str(directory), description="Save folder:", layout=widgets.Layout(width="650px"))
        self.prefix = widgets.Text(value="zelux", description="Prefix:")
        self.exposure = widgets.BoundedIntText(value=10000, min=1, max=100000000, description="Exposure µs:")
        self.gain = widgets.IntText(value=0, description="Gain index:")
        self.set_gain = widgets.Checkbox(value=False, description="Apply gain")
        self.camera_fps = widgets.BoundedFloatText(value=0, min=0, max=1000, description="Cam FPS:")
        self.video_fps = widgets.BoundedFloatText(value=20, min=0.1, max=1000, description="MP4 FPS:")
        self.format = widgets.Dropdown(options=[".tif", ".png", ".npy"], description="Snapshot:")
        self.image = widgets.Image(format="png")
        self.status = widgets.HTML(value="Stopped")
        self.message = widgets.HTML()
        buttons = []
        for label, action in (
            ("Start preview", self.start), ("Stop preview", self.stop),
            ("Apply settings", self.apply_settings), ("Save snapshot", self.snapshot),
            ("Record MP4", self.start_recording), ("Stop recording", self.stop_recording),
        ):
            button = widgets.Button(description=label)
            button.on_click(lambda _, action=action: self._handle(action))
            buttons.append(button)
        self.widget = widgets.VBox([
            widgets.HTML(value=f"<b>Zelux {html.escape(camera.serial)}</b> — raw grayscale preview"),
            widgets.HBox([self.exposure, self.gain, self.set_gain]),
            widgets.HBox([self.camera_fps, self.video_fps, self.format]),
            widgets.HTML(value="Cam FPS = 0: unrestricted. MP4 FPS controls playback, not acquisition."),
            self.directory, self.prefix,
            widgets.HBox(buttons[:3]), widgets.HBox(buttons[3:]),
            self.status, self.message, self.image,
        ])

    def _message(self, text):
        self.message.value = html.escape(str(text))

    def _handle(self, action):
        try:
            action()
        except Exception as exc:
            self._message(f"{type(exc).__name__}: {exc}")

    def show(self):
        from IPython.display import display
        display(self.widget)
        return self

    def start(self):
        loop = asyncio.get_running_loop()  # Jupyter/IPykernel event loop.
        if self.stream.running:
            return
        self.stream.start(
            exposure_us=self.exposure.value,
            gain=self.gain.value if self.set_gain.value else None,
            fps=self.camera_fps.value or None,
        )
        if self._task is not None:
            self._task.cancel()
        self._task = loop.create_task(self._refresh())
        self._message("Preview started. Stop preview before experiment acquisition.")

    async def _refresh(self):
        from PIL import Image

        previous = None
        try:
            while self.stream.running:
                frame = self.stream.latest
                if frame is not None and frame is not previous:
                    preview = Image.fromarray(frame.preview())
                    preview.thumbnail((900, 700))
                    with BytesIO() as buffer:
                        preview.save(buffer, format="PNG")
                        self.image.value = buffer.getvalue()
                    previous = frame
                recorder = self.stream.recorder
                recording = ""
                if recorder is not None:
                    recording = f" | MP4: {recorder.written} written, {recorder.dropped} queue drops"
                self.status.value = (
                    f"Acquired: {self.stream.frame_count} | Average: {self.stream.fps:.1f} FPS"
                    f" | Frame-number gaps: {self.stream.frame_gaps}{recording}"
                )
                await asyncio.sleep(1 / self.preview_fps)
            self.status.value = "Stopped"
            if self.stream.error is not None:
                self._message(f"Acquisition error: {self.stream.error}")
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self._message(f"Preview rendering failed: {exc}. Stop preview to release acquisition.")

    def stop(self):
        try:
            self.stream.stop()
        finally:
            if self._task is not None:
                self._task.cancel()
                self._task = None
            self.status.value = "Acquisition still stopping" if self.stream.running else "Stopped"

    def apply_settings(self):
        if self.stream.recorder is not None:
            raise RuntimeError("Stop recording before changing settings.")
        self.stop()
        self.start()

    def snapshot(self):
        path = output_path(self.directory.value, self.prefix.value, self.format.value)
        self.stream.save_snapshot(path)
        self._message(f"Saved raw image: {path}")
        return path

    def start_recording(self):
        path = output_path(self.directory.value, self.prefix.value, ".mp4")
        self.stream.start_recording(path, fps=self.video_fps.value)
        self._message(f"Recording: {path}")
        return path

    def stop_recording(self):
        recorder = self.stream.stop_recording()
        if recorder is not None:
            self._message(f"Saved {recorder.path}: {recorder.written} frames, {recorder.dropped} queue drops")

    def close(self):
        self.stop()
        self.widget.close()

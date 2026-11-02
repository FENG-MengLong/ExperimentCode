"""Raw snapshots and bounded, asynchronous 8-bit MP4 recording."""

import json
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Thread

import numpy as np

from .camera import Frame


def output_path(directory, prefix: str = "zelux", suffix: str = ".tif") -> Path:
    """Create the directory and return prefix + suffix, without extra identifiers.

    Saving to this path still refuses to overwrite images, videos, or metadata.
    """
    if not prefix or Path(prefix).name != prefix or prefix in (".", ".."):
        raise ValueError("prefix must be a filename, not a path")
    directory = Path(directory).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{prefix}{suffix}"


def save_frame(frame: Frame, path) -> Path:
    """Save raw TIFF/PNG/NPY pixels plus a JSON sidecar; never overwrite.

    Bayer sensor data remain raw Bayer data. PNG supports uint8/uint16 here.
    """
    path = Path(path).expanduser().resolve()
    suffix = path.suffix.lower()
    if suffix in (".tif", ".tiff"):
        import tifffile
        write_image = lambda file: tifffile.imwrite(file, frame.image, photometric="minisblack")
    elif suffix == ".png":
        from PIL import Image
        write_image = lambda file: Image.fromarray(frame.image).save(file, format="PNG")
    elif suffix == ".npy":
        write_image = lambda file: np.save(file, frame.image, allow_pickle=False)
    else:
        raise ValueError("Raw snapshot extension must be .tif, .tiff, .png or .npy")
    path.parent.mkdir(parents=True, exist_ok=True)
    sidecar = path.with_suffix(path.suffix + ".json")
    created = []
    try:
        with path.open("xb") as image_file:
            created.append(path)
            with sidecar.open("x", encoding="utf-8") as metadata_file:
                created.append(sidecar)
                write_image(image_file)
                json.dump(frame.metadata(), metadata_file, indent=2)
    except BaseException:
        for item in created:
            item.unlink(missing_ok=True)
        raise
    return path


class VideoRecorder:
    """A bounded raw-frame queue feeding a grayscale MP4 writer.

    Queue overflow drops NEW frames and increments ``dropped``. Per-frame
    metadata are written to JSONL; the final line records queue drops. MP4 is
    viewing output, NOT a lossless scientific data format or timing record.
    """

    def __init__(self, path, first_frame: Frame, fps: float = 20, queue_size: int = 64):
        import cv2

        if not np.isfinite(fps) or fps <= 0 or queue_size < 1:
            raise ValueError("fps and queue_size must be positive")
        self.path = Path(path).expanduser().resolve()
        if self.path.suffix.lower() != ".mp4":
            raise ValueError("Video filename must end in .mp4")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.written = 0
        self.dropped = 0
        self.error = None
        self._queue = Queue(maxsize=queue_size)
        self._stop = Event()
        self._shape = first_frame.image.shape
        # Common MP4 codecs silently truncate odd dimensions; reject them.
        if any(size % 2 for size in self._shape):
            raise ValueError("MP4 requires even image dimensions; use raw snapshots for this ROI.")
        sidecar = self.path.with_suffix(".mp4.jsonl")
        created = []
        self._writer = None
        self._metadata = None
        try:
            with self.path.open("xb"):
                created.append(self.path)
            self._metadata = sidecar.open("x", encoding="utf-8")
            created.append(sidecar)
            height, width = self._shape
            self._writer = cv2.VideoWriter(
                str(self.path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height), False
            )
            if not self._writer.isOpened():
                raise RuntimeError("OpenCV could not open the MP4 encoder. Check installed codecs.")
            self._metadata.write(json.dumps({"type": "header", "playback_fps": fps,
                                             "rendering": "8-bit raw grayscale"}) + "\n")
        except BaseException:
            if self._writer is not None:
                self._writer.release()
            if self._metadata is not None:
                self._metadata.close()
            for item in created:
                item.unlink(missing_ok=True)
            raise
        self._thread = Thread(target=self._run, name="zelux-video", daemon=True)
        self._thread.start()

    def submit(self, frame: Frame) -> None:
        """Called by one acquisition worker; never blocks camera acquisition."""
        if self._stop.is_set() or self.error is not None:
            return
        try:
            self._queue.put_nowait(frame)
        except Full:
            self.dropped += 1

    def _run(self):
        try:
            while not self._stop.is_set() or not self._queue.empty():
                try:
                    frame = self._queue.get(timeout=0.1)
                except Empty:
                    continue
                if frame.image.shape != self._shape:
                    raise RuntimeError("Image dimensions changed during recording.")
                self._writer.write(frame.preview())
                self._metadata.write(json.dumps({"type": "frame", **frame.metadata()}) + "\n")
                self.written += 1
        except Exception as exc:
            self.error = exc
        finally:
            try:
                self._writer.release()
            finally:
                try:
                    self._metadata.write(json.dumps({
                        "type": "summary", "written": self.written, "queue_dropped": self.dropped,
                        "error": str(self.error) if self.error else None,
                    }) + "\n")
                except Exception as exc:
                    self.error = self.error or exc
                finally:
                    self._metadata.close()

    def close(self) -> None:
        """Drain queued frames and finalize the video; propagate writer errors."""
        self._stop.set()
        self._thread.join()
        if self.error is not None:
            raise RuntimeError(f"Video recording failed: {self.error}") from self.error

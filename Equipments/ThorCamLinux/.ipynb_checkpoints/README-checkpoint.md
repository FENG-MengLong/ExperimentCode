# Zelux on Linux / Jupyter

The original `../ThorCam/` is preserved, unchanged. This package does not use its
Windows DLLs. The interactive test notebook is **`../../ThorCamLinux_test.ipynb`**
(project root). Nothing connects to hardware merely by importing this package.

## 1. Install and verify the Linux SDK

1. Obtain the **Thorlabs Linux Camera SDK** supporting your exact Zelux model and
   CPU architecture. Follow its release notes for supported Linux/Python versions.
   USB detection alone does not establish SDK compatibility. Windows DLLs cannot
   run natively on Linux. This wrapper requires Python 3.10+; choose a version also
   supported by the vendor SDK. Python 3.14 compatibility has not been established here.
2. Install the vendor-supplied `thorlabs_tsi_sdk` Python package into the SAME
   environment used by the notebook kernel. Its archive filename/version depends
   on the SDK release. Do not assume a similarly named PyPI package is equivalent.
3. Install the native `.so` libraries and their dependencies as directed by the
   vendor. Configure the dynamic linker before launching Jupyter. For example,
   substituting the actual native library directory:

   ```bash
   export LD_LIBRARY_PATH="/path/to/thorlabs/linux/native/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
   jupyter lab
   ```

   Changing `os.environ['LD_LIBRARY_PATH']` after the kernel has started is not a
   reliable fix for native library loading. Restart the server/kernel as needed.
   `ldd /actual/path/libthorlabs_tsi_camera_sdk.so` can identify missing native
   dependencies; use the filename supplied in your SDK release.
4. Install the vendor USB/udev rules, then reconnect the camera. The notebook user
   needs read AND write access to the device node. Prefer vendor group-based rules
   over running Jupyter as root or making every USB device world-writable.
5. Install optional UI/storage dependencies:

   ```bash
   python -m pip install -r Equipments/ThorCamLinux/requirements.txt
   ```

   Use your kernel's interpreter (`sys.executable`). If your environment already
   has another OpenCV distribution, do not install both GUI and headless OpenCV
   into it. This package needs no desktop OpenCV windows.

Run the notebook's diagnostics cell first. Camera discovery opens the SDK; stop
other camera applications and close existing camera objects before discovery.
This implementation uses one SDK/camera connection; multi-camera sessions are
not implemented.

## 2. Scripted capture

```python
from Equipments.ThorCamLinux import Camera, save_frame

with Camera("35390") as camera:  # omit serial only if exactly one camera exists
    frame = camera.capture(exposure_us=10000, timeout_s=2)
    pixels = frame.image  # owned, read-only NumPy array, original pixel dtype
    save_frame(frame, "./camera_data/image.tif")
```

The files `image.tif` and `image.tif.json` must not already exist. `output_path()`
creates unique timestamped names. Saving creates parent directories. TIFF, PNG
and NPY snapshots preserve raw pixels, rather than display-scaled data. TIFF
requires `tifffile`; PNG requires Pillow. Use `frame.image.astype(float)` before
background subtraction/optical-density processing to avoid unsigned underflow.

### External experiment triggering

```python
camera.configure(exposure_us=900, trigger="external")
camera.arm()
try:
    # Start the external pulse sequence HERE, after arming.
    frame = camera.read_frame(timeout_s=15)
finally:
    camera.disarm()
```

One frame per external trigger. Multiple triggers can be read in a loop while
armed, subject to the model's trigger/readout limits and buffer capacity. Set the
deadline longer than the expected trigger delay + exposure + transfer time.
`read_frame()` consumes the next queued frame; it does not match experiment IDs
or silently discard stale frames. Coordinate pulse count/order with frame numbers
and start a fresh disarmed/configured acquisition for each sequence when needed.
A timeout leaves the camera armed; the caller chooses whether to retry or disarm.
The code does not change trigger polarity or configure exposure-bulb mode. Verify
trigger voltage, polarity, timing, and capabilities against the camera manual.

Python/Jupyter is not a real-time trigger generator. Keep precise timing in the
BNC575/external hardware. `host_time_ns` is the wall-clock time at frame retrieval,
NOT exposure start. Optional camera timestamps are SDK-relative, not Unix time.

## 3. Notebook live monitor

```python
from Equipments.ThorCamLinux import Camera, LiveMonitor

camera = Camera("35390")
monitor = LiveMonitor(camera, directory="./camera_data").show()
# Use the panel's Start preview / Save snapshot / Record MP4 buttons.
```

The save-folder text box selects a directory on the **kernel machine**, not the
browser computer. Exposure is in microseconds; gain is in SDK index units, not
necessarily dB. Gain stays unchanged unless "Apply gain" is checked. Cam FPS = 0
disables frame-rate limiting where supported. Unsupported/out-of-range settings
produce SDK errors rather than guessed limits. Apply settings restarts acquisition;
stop recording first. Preview rendering is throttled independently of acquisition.

```python
monitor.stop()  # mandatory before experiment cells use camera
frame = camera.capture(exposure_us=900)
# Later: monitor.start()
# Final cleanup, in this order:
monitor.close()
camera.close()
```

One worker owns camera acquisition during preview. Concurrent script access fails
explicitly rather than silently consuming someone else's frames. No second camera
connection is opened by the UI. A script can also use `LiveStream(camera)` without
widgets, and call `start`, `save_snapshot`, `start_recording`, `stop_recording`, and
`stop` explicitly. A snapshot is the most recently acquired frame, not a newly
triggered exposure.

A busy/long-running notebook cell may delay browser preview refresh. Camera
acquisition and recording run in background threads, but CPU/GIL contention and
USB/disk throughput still matter; this is not a real-time or lossless guarantee.
Use Stop/close explicitly before rerunning connection cells or restarting a kernel.
Normal stop/disarm/cleanup is supported; a hard kernel kill cannot finalize MP4.

## 4. Video and color limitations

MP4 uses the `mp4v` encoder via OpenCV and full-scale **8-bit grayscale** rendering.
It is convenient viewing output, not quantitative raw data. Both monochrome and
Bayer cameras retain raw sensor pixels for snapshots; Bayer previews/videos are
raw grayscale, **not demosaiced color**. Color processing and ROI controls are not
implemented in this first version.

Video runs through a bounded queue (default 64 raw frames). If disk encoding falls
behind, NEW frames are dropped, counted and reported, not allowed to consume
unbounded memory. Size this queue with full-resolution frame size in mind. SDK
frame-number gaps are reported separately by the stream. The `.mp4.jsonl` sidecar
contains playback FPS, each written frame's metadata, and a final queue-drop
summary. Playback FPS is independently selected; it does not measure acquisition
cadence. OpenCV has no per-frame encoder acknowledgment, so validate saved video
on the target machine. Odd frame dimensions are rejected to avoid codec cropping.
Files are never overwritten. Writer errors surface in the panel and on stop.

For raw quantitative sequences, use explicitly triggered `read_frame()` plus
`save_frame()` in the experiment loop. High-rate continuous raw recording,
compression and throughput tuning are outside this first implementation.

## 5. Offline tests

From the project root, without the vendor SDK or camera:

```bash
python -B -m unittest discover -s Equipments/ThorCamLinux/tests -v
```

The tests use a fake camera/SDK and a fake video encoder. They do not verify native
SDK compatibility, physical trigger timing, actual MP4 codecs, or USB throughput.
Hardware verification is deliberately manual in `ThorCamLinux_test.ipynb`.

`Equipments/__init__.py` now loads the old ThorCam module lazily. This small change
prevents its eager Windows/OpenCV import from breaking unrelated Linux equipment
imports; existing `from Equipments import ThorCam` still requests the old driver.

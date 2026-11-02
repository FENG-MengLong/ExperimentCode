# Zelux on Linux / Jupyter

The original `../ThorCam/` is preserved, unchanged. This package does not use its
Windows DLLs. The interactive test notebook is **`../../ThorCamLinux_test.ipynb`**
(project root). Nothing connects to hardware merely by importing this package.

## Local setup on this machine

The supplied `scientific_camera_interfaces-linux-2.3-06_04_26.zip` is extracted to
`vendor/Scientific_Camera_Interfaces/`. The original ZIP is retained. Vendor files
are excluded from Git by this package's `.gitignore`.

Its Python wrapper, `thorlabs_tsi_sdk==1.2.0`, is installed in
`/home/fengxy/miniconda3/bin/python` (Python 3.14.7), without dependency upgrades.
Import and loading of the bundled x86-64 camera/Zelux libraries succeeded. This
release includes native libraries inside the installed Python package, so no
`LD_LIBRARY_PATH` change was needed. Acquisition and recording have now passed the
hardware checks below on this Python version; this is not a claim of vendor-certified
compatibility for every SDK feature.

USB permissions are configured by `linux/99-thorlabs-zelux.rules`. As requested,
it grants all local users read/write access (mode 0666), restricted to Zelux USB
product `1313:4002`. Installing or updating the system rule requires administrator
permission. From the project root, run in a terminal:

```bash
sudo install -o root -g root -m 0644 \
  Equipments/ThorCamLinux/linux/99-thorlabs-zelux.rules \
  /etc/udev/rules.d/99-thorlabs-zelux.rules
sudo udevadm control --reload-rules
```

Then unplug/reconnect the camera. Re-run `diagnostics()` and confirm
`usb_permissions[*].read_write_access` is true. USB bus/device numbers may change
on reconnect. This rule applies to all local accounts, including SSH users; it
does not allow safe simultaneous camera control by multiple programs. Do not run
Jupyter as root. On a managed machine, ask your administrator to perform these
steps if sudo is not available to you.

The UI/storage dependencies are installed in the same environment: ipywidgets
8.1.9, tifffile 2026.10.15, and opencv-python-headless 5.0.0.93.

### Hardware verification

Tested with **CS165MU1**, serial **33834**, firmware **v0.9.6**, on Python 3.14.7:

- Single capture: 1440 × 1080, 10-bit sensor data in a uint16 array.
- TIFF, PNG and NPY: saved/reloaded arrays exactly match the acquired raw pixels.
- A real IPykernel executed the live-monitor code and generated preview PNG updates.
- A five-second MP4 test requested 20 FPS and measured approximately 20.005 FPS
  from host retrieval timestamps. All 100 written frames decoded successfully;
  no SDK frame-number gaps or recorder queue drops were observed in this test.
- Exposure/gain changes, live restart, live/script exclusion, scripted capture
  after stopping the monitor, camera close/reopen, and metadata saving passed.
- All 23 offline tests passed, including TIFF tests and the FPS-order regression.

The hardware test revealed that enabling Zelux frame-rate control resets its
value. `Camera.configure()` now enables control BEFORE assigning the requested
rate. Camera exposure and frame-rate values are quantized: for example, a 900 µs
request read back as 910 µs in one test. Use the returned frame metadata for the
SDK-reported exposure; it is not a calibration of the physical exposure duration.

Test outputs, JSON reports and the executed validation notebook are under:
`camera_test_output/hardware_20261102T024655_940597Z_40c368eb/` (project root).
`notebook_hardware_report.json` records the corrected 20 FPS test; the earlier
`hardware_report.json` retains the pre-fix test for reference.

External triggering/BNC575 operation, long-duration throughput, and visual
rendering/click interaction in a browser have NOT been verified. Restart your
existing notebook kernel to load the FPS fix and newly installed packages. The
root test notebook remains unchanged, with hardware acquisition opt-in.

## 1. Install and verify the Linux SDK

1. Obtain the **Thorlabs Linux Camera SDK** supporting your exact Zelux model and
   CPU architecture. Follow its release notes for supported Linux/Python versions.
   USB detection alone does not establish SDK compatibility. Windows DLLs cannot
   run natively on Linux. This wrapper requires Python 3.10+; choose a version also
   supported by the vendor SDK. The checks above passed on Python 3.14.7, but do
   not establish compatibility with all camera models or SDK features.
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
uses only the chosen prefix and extension (for example, `shot.tif`), without a
timestamp or random ID. This also applies to the live monitor's snapshots and
MP4 recordings. Change the prefix before saving another file in the same format;
existing images, videos, and metadata are never overwritten. Saving creates
parent directories. TIFF, PNG and NPY snapshots preserve raw pixels, rather than
display-scaled data. TIFF
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

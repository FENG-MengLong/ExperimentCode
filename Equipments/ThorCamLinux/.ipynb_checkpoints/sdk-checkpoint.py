"""Lazy SDK loading and read-only Linux setup diagnostics."""

import importlib.util
import os
from pathlib import Path
import platform
import subprocess
import sys


class SDKUnavailable(RuntimeError):
    """The vendor Python wrapper or its native libraries are unavailable."""


def load_sdk():
    try:
        from thorlabs_tsi_sdk.tl_camera import TLCameraSDK, OPERATION_MODE
    except (ImportError, OSError) as exc:
        raise SDKUnavailable(
            "Install the Python wrapper supplied with the Thorlabs Linux Camera SDK "
            "in this notebook's Python environment. The Windows DLLs in ../ThorCam "
            "cannot run on Linux. See ThorCamLinux/README.md."
        ) from exc
    return TLCameraSDK, OPERATION_MODE


def open_sdk():
    factory, modes = load_sdk()
    try:
        return factory(), modes
    except (OSError, RuntimeError) as exc:
        raise SDKUnavailable(
            "The Thorlabs native SDK could not start. Install its Linux libraries "
            "and dependencies, and configure the dynamic linker BEFORE launching "
            "Jupyter (for example via LD_LIBRARY_PATH). "
            f"Vendor error: {exc}"
        ) from exc


def diagnostics() -> dict:
    """Inspect software and USB permissions without opening the camera."""
    packages = ("thorlabs_tsi_sdk", "numpy", "ipywidgets", "PIL", "tifffile", "cv2")
    result = {
        "python": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "LD_LIBRARY_PATH": os.environ.get("LD_LIBRARY_PATH", ""),
        "packages": {name: importlib.util.find_spec(name) is not None for name in packages},
    }
    try:
        usb = subprocess.run(
            ["lsusb", "-d", "1313:"], capture_output=True, text=True, timeout=5
        )
        result["thorlabs_usb"] = usb.stdout.strip() or "No Thorlabs USB device found"
        devices = []
        for line in usb.stdout.splitlines():
            parts = line.split()
            path = Path("/dev/bus/usb") / parts[1] / parts[3].rstrip(":")
            devices.append({"path": str(path), "read_write_access": os.access(path, os.R_OK | os.W_OK)})
        result["usb_permissions"] = devices
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["thorlabs_usb"] = str(exc)
    return result

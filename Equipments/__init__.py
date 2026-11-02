"""Equipment drivers; load the legacy ThorCam driver only when requested."""

from importlib import import_module


def __getattr__(name):
    if name == "ThorCam":
        driver = import_module(".ThorCam.ThorCam", __name__)
        globals()[name] = driver
        return driver
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

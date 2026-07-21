"""
Wrapper around the official `windfreak` Python package.

Install:
    pip install windfreak

Basic use:
    from windfreak_generator import Windfreak

    sg = Windfreak(
        visa_name="COM11",
        power_limit=10,
        freq_limit=6.4e9,
        channel=0
    )

    sg.use_external_reference(10e6)
    sg.set_external_trigger("rf enable")

    sg.set_frequency(1e9)
    sg.set_power(-10)
    sg.start_output()

    sg.stop_output()
    sg.close()
"""

try:
    from windfreak import SynthHD
except ImportError as exc:
    raise ImportError(
        "Cannot import `windfreak`. Install it first with:\n\n"
        "    pip install windfreak\n"
    ) from exc


class Windfreak:
    TRIGGER_MODES = (
        "disabled",
        "full frequency sweep",
        "single frequency step",
        "stop all",
        "rf enable",
        "remove interrupts",
        "reserved",
        "reserved",
        "am modulation",
        "fm modulation",
    )

    REFERENCE_MODES = (
        "external",
        "internal 27mhz",
        "internal 10mhz",
    )

    def __init__(
        self,
        visa_name,
        power_limit,
        freq_limit,
        timeout=5000,
        channel=0,
        init_device=True,
    ):
        self.set_power_limit(power_limit)
        self.set_freq_limit(freq_limit)

        if channel not in (0, 1):
            raise ValueError("channel must be 0 or 1 for SynthHD.")

        self.visa_name = visa_name
        self.port_name = visa_name
        self.timeout = timeout
        self.channel = channel

        self.inst = SynthHD(visa_name)

        self._try_set_timeout(timeout)

        if init_device:
            self.inst.init()

        self.ch = self.inst[channel]

        print(f"Opened Windfreak SynthHD on {visa_name}, channel {channel}")

    def _try_set_timeout(self, timeout_ms):
        """
        Try to set timeout if the backend exposes an internal serial object.
        Failure is ignored because this depends on the windfreak package version.
        """
        timeout_s = timeout_ms / 1000

        possible_serial_attrs = (
            "serial",
            "_serial",
            "dev",
            "_dev",
            "connection",
        )

        for attr in possible_serial_attrs:
            ser = getattr(self.inst, attr, None)
            if ser is not None and hasattr(ser, "timeout"):
                try:
                    ser.timeout = timeout_s
                    return
                except Exception:
                    pass

    # -------------------------
    # Safety limits
    # -------------------------

    def set_power_limit(self, power_limit):
        """
        Set software safety limit for output power in dBm.
        """
        if power_limit <= 20:
            self.power_limit = power_limit
        else:
            raise RuntimeError(
                "the power limit exceeds the wrapper safety limit: 20 dBm"
            )

    def set_freq_limit(self, freq_limit):
        """
        Set software safety limit for output frequency in Hz.
        """
        if freq_limit > 0:
            self.freq_limit = freq_limit
        else:
            raise RuntimeError("the freq. limit must be positive")

    # -------------------------
    # Basic RF output interface
    # -------------------------

    def start_output(self):
        """
        Enable RF output on the selected channel.
        """
        self.ch.enable = True

    def stop_output(self):
        """
        Disable RF output on the selected channel.
        """
        self.ch.enable = False

    def set_frequency(self, frequency):
        """
        Set CW frequency in Hz.

            sg.set_frequency(1e9)
        """
        if frequency <= self.freq_limit:
            self.ch.frequency = float(frequency)
        else:
            raise RuntimeError(
                f"the freq. exceeds the limit: {self.freq_limit} Hz"
            )

    def set_power(self, power):
        """
        Set output power in dBm.
        
            sg.set_power(-10)
        """
        if power <= self.power_limit:
            self.ch.power = float(power)
        else:
            raise RuntimeError(
                f"the power exceeds the limit: {self.power_limit} dBm"
            )

    def get_frequency(self):
        """
        Return current frequency in Hz.
        """
        return self.ch.frequency

    def get_power(self):
        """
        Return current power in dBm.
        """
        return self.ch.power

    # -------------------------
    # External reference
    # -------------------------

    def set_reference_mode(self, mode):
        """
        Set reference source.

        Valid modes:
            "external"
            "internal 27mhz"
            "internal 10mhz"

        Example:
            sg.set_reference_mode("external")
        """
        mode = mode.lower().strip()

        if mode not in self.REFERENCE_MODES:
            raise ValueError(
                f"Invalid reference mode: {mode}. "
                f"Valid modes are: {self.REFERENCE_MODES}"
            )

        self.inst.reference_mode = mode

    def use_external_reference(self, reference_frequency=10e6):
        """
        Use external reference.

        Parameters
        ----------
        reference_frequency : float
            External reference frequency in Hz.
            Common values: 10e6, 27e6, 100e6 depending on your lab clock.

        Example:
            sg.use_external_reference(10e6)
        """
        self.set_reference_frequency(reference_frequency)
        self.set_reference_mode("external")

    def use_internal_reference(self, reference="27mhz"):
        """
        Use internal reference.

        Parameters
        ----------
        reference : str
            "27mhz" or "10mhz"

        Example:
            sg.use_internal_reference("27mhz")
        """
        reference = reference.lower().strip()

        if reference in ("27mhz", "27 mhz", "27"):
            self.set_reference_mode("internal 27mhz")
        elif reference in ("10mhz", "10 mhz", "10"):
            self.set_reference_mode("internal 10mhz")
        else:
            raise ValueError("reference must be '27mhz' or '10mhz'")

    def set_reference_frequency(self, reference_frequency):
        """
        Set reference frequency in Hz.

        Valid range in the official wrapper is usually 10 MHz to 100 MHz.

        Example:
            sg.set_reference_frequency(10e6)
        """
        self.inst.reference_frequency = float(reference_frequency)

    def get_reference_mode(self):
        """
        Return current reference mode.
        """
        return self.inst.reference_mode

    def get_reference_frequency(self):
        """
        Return current reference frequency in Hz.
        """
        return self.inst.reference_frequency

    # -------------------------
    # External trigger
    # -------------------------

    def set_trigger_mode(self, mode):
        """
        Set trigger connector function.

        Valid modes:
            "disabled"
            "full frequency sweep"
            "single frequency step"
            "stop all"
            "rf enable"
            "remove interrupts"
            "am modulation"
            "fm modulation"

        Most common for external pulse/RF gating:
            sg.set_trigger_mode("rf enable")
        """
        mode = mode.lower().strip()

        if mode not in self.TRIGGER_MODES:
            raise ValueError(
                f"Invalid trigger mode: {mode}. "
                f"Valid modes are: {self.TRIGGER_MODES}"
            )

        if mode == "reserved":
            raise ValueError("Do not use reserved trigger modes.")

        self.inst.trigger_mode = mode

    def set_external_trigger(self, mode="rf enable"):
        """
        Convenience alias for external trigger setup.

        Default:
            "rf enable"

        This is the usual mode for external RF on/off or pulse modulation.
        """
        self.set_trigger_mode(mode)

    def disable_trigger(self):
        """
        Disable the trigger connector.
        """
        self.set_trigger_mode("disabled")

    def get_trigger_mode(self):
        """
        Return current trigger mode.
        """
        return self.inst.trigger_mode

    def close(self):
        """
        Close the device connection if the backend exposes a close method.
        """
        possible_objs = (
            self.inst,
            getattr(self.inst, "serial", None),
            getattr(self.inst, "_serial", None),
            getattr(self.inst, "dev", None),
            getattr(self.inst, "_dev", None),
            getattr(self.inst, "connection", None),
        )

        self.init.stop_output()

        for obj in possible_objs:
            if obj is None:
                continue

            close_method = getattr(obj, "close", None)
            if callable(close_method):
                try:
                    close_method()
                    return
                except Exception:
                    pass
import pyvisa
import numpy as np
import struct

class LeCroyScope:
    def __init__(self, visa_name, timeout=20000):
        rm = pyvisa.ResourceManager()
        self.inst = rm.open_resource(visa_name)
        self.inst.timeout = timeout
        # self.inst.read_termination = "\n"
        # self.inst.write_termination = "\n"
        self.inst.chunk_size = 1024 * 1024

        try:
            print("*IDN ->", self.inst.query("*IDN?"))
        except Exception as e:
            print("*IDN failed:", e)

    def setup_transfer(self):
        self.inst.write("CHDR OFF")
        self.inst.write("CFMT DEF9,WORD,BIN")
        self.inst.write("WFSU SP,1,NP,0,FP,1,SN,0")

    def _read_ieee_block_precise(self, cmd):
        # print("Sending:", cmd)

        # old_term = self.inst.read_termination
        # self.inst.read_termination = None

        # try:
        self.inst.write(cmd)

        prefix = b""
        while True:
            ch = self.inst.read_bytes(1)
            prefix += ch
            if ch == b"#":
                break

        n_digits = int(self.inst.read_bytes(1).decode())
        len_bytes = self.inst.read_bytes(n_digits)
        n_bytes = int(len_bytes.decode())

        payload = self.inst.read_bytes(n_bytes)

        try:
            self.inst.read_bytes(1, break_on_termchar=False)
        except Exception:
            pass

        # print("Prefix before #:", prefix[:-1])
        # print("Payload length:", len(payload))
        # print("Payload head:", payload[:80])

        return prefix, payload

        # finally:
        #     self.inst.read_termination = old_term

    def read_descriptor(self, channel="C1"):
        _, payload = self._read_ieee_block_precise(f"{channel}:WF? DESC")
        return payload

    def readout_raw(self, channel="C1"):
        _, payload = self._read_ieee_block_precise(f"{channel}:WF? DAT1")
        return payload

    def readout(self, channel="C1", dtype="<i2"):
        payload = self.readout_raw(channel)

        if len(payload) == 0:
            return np.array([], dtype=np.dtype(dtype))

        itemsize = np.dtype(dtype).itemsize
        if len(payload) % itemsize != 0:
            payload = payload[:len(payload) - (len(payload) % itemsize)]

        return np.frombuffer(payload, dtype=np.dtype(dtype))

    def _parse_wavedesc(self, desc):
        if len(desc) < 346:
            raise ValueError(f"Descriptor too short: {len(desc)} bytes")

        def read_int16(offset, endian="<"):
            return struct.unpack(endian + "h", desc[offset:offset+2])[0]

        def read_int32(offset, endian="<"):
            return struct.unpack(endian + "i", desc[offset:offset+4])[0]

        def read_float32(offset, endian="<"):
            return struct.unpack(endian + "f", desc[offset:offset+4])[0]

        def read_float64(offset, endian="<"):
            return struct.unpack(endian + "d", desc[offset:offset+8])[0]

        def read_string(offset, length):
            raw = desc[offset:offset+length]
            return raw.split(b"\x00", 1)[0].decode(errors="ignore").strip()

        # COMM_ORDER decides endianness of numeric fields
        # 0 = HIFIRST (big-endian), 1 = LOFIRST (little-endian)
        comm_order_le = struct.unpack("<h", desc[34:36])[0]
        if comm_order_le == 1:
            endian = "<"
        elif comm_order_le == 0:
            endian = ">"
        else:
            # fallback
            endian = "<"

        info = {}
        info["descriptor_name"]   = read_string(0, 16)
        info["template_name"]     = read_string(16, 16)
        info["comm_type"]         = read_int16(32, endian)
        info["comm_order"]        = read_int16(34, endian)
        info["wave_descriptor"]   = read_int32(36, endian)
        info["user_text"]         = read_int32(40, endian)
        info["trigtime_array"]    = read_int32(48, endian)
        info["ris_time_array"]    = read_int32(52, endian)
        info["wave_array_1"]      = read_int32(60, endian)
        info["wave_array_count"]  = read_int32(116, endian)
        info["pnts_per_screen"]   = read_int32(120, endian)
        info["first_valid_pnt"]   = read_int32(124, endian)
        info["last_valid_pnt"]    = read_int32(128, endian)
        info["first_point"]       = read_int32(132, endian)
        info["sparsing_factor"]   = read_int32(136, endian)
        info["subarray_count"]    = read_int32(144, endian)
        info["vertical_gain"]     = read_float32(156, endian)
        info["vertical_offset"]   = read_float32(160, endian)
        info["max_value"]         = read_float32(164, endian)
        info["min_value"]         = read_float32(168, endian)
        info["horizontal_interval"] = read_float32(176, endian)
        info["horizontal_offset"] = read_float64(180, endian)
        info["vertical_unit"]     = read_string(196, 48)
        info["horizontal_unit"]   = read_string(244, 48)
        info["instrument_name"]   = read_string(76, 16)
        info["trace_label"]       = read_string(96, 16)
        info["wave_source"]       = read_int16(344, endian)

        return info

    def read_waveform(self, channel="C1"):
        desc = self.read_descriptor(channel)
        info = self._parse_wavedesc(desc)

        # Determine sample dtype from descriptor COMM_TYPE
        # 0 = byte, 1 = word
        comm_type = info["comm_type"]
        comm_order = info["comm_order"]

        if comm_type == 0:
            dtype = np.int8
        elif comm_type == 1:
            if comm_order == 1:
                dtype = np.dtype("<i2")
            else:
                dtype = np.dtype(">i2")
        else:
            raise ValueError(f"Unsupported COMM_TYPE: {comm_type}")

        raw = self.readout_raw(channel)

        if len(raw) == 0:
            return np.array([]), np.array([]), info

        itemsize = np.dtype(dtype).itemsize
        if len(raw) % itemsize != 0:
            raw = raw[:len(raw) - (len(raw) % itemsize)]

        adc = np.frombuffer(raw, dtype=dtype)

        # Convert ADC codes to volts
        v = info["vertical_gain"] * adc - info["vertical_offset"]

        # Build time axis
        dt = info["horizontal_interval"]
        t0 = info["horizontal_offset"]
        t = t0 + np.arange(len(v)) * dt

        return t, v, info

    def close(self):
        self.inst.close()
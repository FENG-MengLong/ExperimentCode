import pyvisa
import time


class BNC575:
	def __init__(self, visa_name, timeout=2000):
		rm = pyvisa.ResourceManager()
		self.pyvisa = rm.open_resource(visa_name)
		self.pyvisa.timeout = timeout

		# Reset interface state
		try:
			self.pyvisa.clear()
		except pyvisa.errors.VisaIOError:
			pass

		self.pyvisa.write("*CLS")

	def clock_set(self, period, mode="CONTINUOUS", burstctr=-1):
		self.pyvisa.write(":PULS0:TRIG:MODE TRIG")
		self.pyvisa.write(f":PULS0:PER {period}")

		if mode == "CONTINUOUS":
			self.pyvisa.write(":PULS0:MODE NORM")
		elif mode == "SINGLE":
			self.pyvisa.write(":PULS0:MODE SING")
		elif mode == "BURST":
			self.pyvisa.write(":PULS0:MODE BURS")
			if burstctr > 0:
				self.pyvisa.write(f":PULS0:BCOUN {burstctr}")
			else:
				print("Burst number is invalid")
		else:
			print("Mode is invalid, use upper case: CONTINUOUS, SINGLE, BURST")

		print("-" * 60)
		print("The global clock is set to:")
		print(f"Mode: {mode}")
		print(f"Period: {float(period):.2e}s")
		print(f"Pulses number: {burstctr if mode == 'BURST' else 'N/A'}")
		print("-" * 60)

		return f"{float(period):.2e}"

	def channel_set(self, channel: str, width, delay, AMP="TTL", polarity=1, SYNC="T0", MUX="-1"):
		ch_dic = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8}
		MUX_dic = {"A": 1, "B": 2, "C": 4, "D": 8, "E": 16, "F": 32, "G": 64, "H": 128}
		polarity_dic = {1: "NORM", -1: "INV"}

		if channel not in ch_dic:
			print("Invalid channel.")
			return

		ch_num = ch_dic[channel]

		try:
			BMUX = int(MUX, 2)
		except ValueError:
			BMUX = -1

		# Automatically resolve 'TO' -> 'T0'
		sync_val = str(SYNC).upper()
		if sync_val in ["TO", "0", "TRIG"]:
			sync_val = "T0"

		# Fire unbuffered writes directly to the hardware bus at full speed
		self.pyvisa.write(f":PULS{ch_num}:STAT ON")
		self.pyvisa.write(f":PULS{ch_num}:WIDT {width}")
		self.pyvisa.write(f":PULS{ch_num}:DEL {delay}")
		self.pyvisa.write(f":PULS{ch_num}:POL {polarity_dic[polarity]}")

		if AMP == "TTL":
			self.pyvisa.write(f":PULS{ch_num}:OUTP:MODE TTL")
		elif isinstance(AMP, (int, float)) and 2 <= AMP <= 20:
			self.pyvisa.write(f":PULS{ch_num}:OUTP:MODE ADJ")
			self.pyvisa.write(f":PULS{ch_num}:OUTP:AMPL {AMP}")

		self.pyvisa.write(f":PULS{ch_num}:SYNC {sync_val}")
		self.pyvisa.write(f":PULS{ch_num}:CMOD NORM")

		if 0 < BMUX < 256:
			self.pyvisa.write(f":PULS{ch_num}:MUX {BMUX}")
			actual_mux = BMUX
		else:
			self.pyvisa.write(f":PULS{ch_num}:MUX {MUX_dic[channel]}")
			actual_mux = MUX_dic[channel]

		# Format output bitmask locally
		M = bin(actual_mux)[2:]

		print("-" * 60)
		print(f"The channel {channel} is set to:")
		print(f"Width: {float(width):.4e}s")
		print(f"Delay: {float(delay):.4e}s")
		print(f"Synchronize to: {sync_val}")
		print(f"Out: {AMP}")
		print("Output timers:\nHGFEDCBA")
		print(M.zfill(8))
		print("-" * 60)

	def expand_pulses(self, pulse_arrangement):
		expanded_pulses = []
		time_marker = 0

		for pulse in pulse_arrangement:
			if isinstance(pulse[0], list):
				temp_time_markers = []
				for sub_pulse in pulse:
					relative_delay = sub_pulse[2]
					abs_delay = time_marker + relative_delay
					expanded_pulses.append([
						sub_pulse[0],
						sub_pulse[1],
						abs_delay,
						sub_pulse[3],
						sub_pulse[4]
					])
					temp_time_markers.append(abs_delay + sub_pulse[1])
				time_marker = max(temp_time_markers)
			else:
				relative_delay = pulse[2]
				time_marker += relative_delay
				expanded_pulses.append([
					pulse[0],
					pulse[1],
					time_marker,
					pulse[3],
					pulse[4]
				])
				time_marker += pulse[1]

		return expanded_pulses

	def pulse_sequence_setup(self, pulse_sequence):
		self.disarm_all()
		self.disable_all()

		expanded_pulses = self.expand_pulses(pulse_sequence)
		print(expanded_pulses)

		for pulse in expanded_pulses:
			pulse_channel, pulse_width, delay, pulse_output, pulse_polarity = pulse
			self.channel_set(pulse_channel, pulse_width, delay, pulse_output, pulse_polarity)

		self.rearm_all()
		return expanded_pulses

	def start_pulses(self):
		self.pyvisa.write(":PULS0:STAT ON")
		self.pyvisa.write("*TRG")

	def rearm_all(self):
		self.pyvisa.write("*ARM")

	def disarm_all(self):
		self.pyvisa.write(":PULS0:STAT OFF")

	def disable_all(self):
		for i in range(8):
			self.pyvisa.write(f":PULS{i+1}:STAT OFF")
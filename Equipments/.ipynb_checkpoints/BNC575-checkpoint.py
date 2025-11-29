# import pyvisa
# import time
# class BNC575:
#     def __init__(self, visa_name, timeout = 5000):
#         rm = pyvisa.ResourceManager()
#         self.pyvisa = rm.open_resource(visa_name)
#         self.pyvisa.timeout = timeout

#     def clock_set(self, period, mode = "CONTINUOUS", burstctr = -1):
#         self.pyvisa.write(":Pulse0:Trigger:Mode Trig")
#         self.pyvisa.query("*OPC?")
#         self.pyvisa.write(f":Pulse0:Period {period}")
#         if mode == "CONTINUOUS":
#             self.pyvisa.write(":Pulse0:Mode Normal")
#             self.pyvisa.query("*OPC?")
#         elif mode == "SINGLE":
#             self.pyvisa.write(":Pulse0:Mode Single")
#             self.pyvisa.query("*OPC?")
#         elif mode == "BURST":
#             self.pyvisa.write(":Pulse0:Mode Burst")
#             self.pyvisa.query("*OPC?")
#             if burstctr > 0:
#                 self.pyvisa.write(f":Pulse0:Bcounter {burstctr}")
#                 self.pyvisa.query("*OPC?")
#             else:
#                 print("Burst number is invalid")
#         else:
#             print("Mode is invalid, the mode should be upper case. Valid Mode(CONTINuOUS; SINGLE; BURST)")
            
#         M = self.pyvisa.query(":Pulse0:Mode?")[:-2]
#         # # self.pyvisa.query("*OPC?")
#         P = float(self.pyvisa.query(":Pulse0:Period?")[:-2])
#         # self.pyvisa.query("*OPC?")
#         if M == "BURS":
#             try:
#                 N = self.pyvisa.query(":Pulse0:Bcounter?").strip()
#                 self.pyvisa.query("*OPC?")
#             except pyvisa.errors.VisaIOError:
#                 N = "Query error"
#         else:
#             N = "N/A"
            
#         print("---------------------------------------")
#         print("The global clock is set to:")
#         print(f"Mode: {M}")
#         print(f"Period: {P:.2e}s")
#         print(f"Pulses number: {N}")
#         print("---------------------------------------")

#     def channel_set(self, channel: str, width, delay, AMP = "TTL", SYNC="TO", MUX="-1"):
#         '''
#         Used to setup one channel
#         what need to do next: write a check function, if the corresponding setup fail, retry
#         '''
#         ch_dic = {"A":1, "B":2, "C":3, "D":4, "E":5, "F":6, "G":7, "H":8}
#         MUX_dic = {"A":1, "B":2, "C":4, "D":8, "E":16, "F":32, "G":64, "H":128}
#         BMUX = int(MUX,2)
#         if channel not in ch_dic:
#             print("Invalid channel.")
#             return
            
#         # set up the channel
#         ch_num = ch_dic[channel]
        
#         self.pyvisa.write(f":Pulse{ch_num}:State on")
#         self.pyvisa.query("*OPC?")
#         self.pyvisa.write(f":Pulse{ch_num}:Width {width}")
#         self.pyvisa.query("*OPC?")
#         self.pyvisa.write(f":Pulse{ch_num}:Delay {delay}")
#         self.pyvisa.query("*OPC?")

#         # set up the output mode: TTL or adjustable (for out standard BNC575 model, no difference, both are 50 ohm impedance)
#         if AMP == "TTL":
#             self.pyvisa.write(f":Pulse{ch_num}:Output:Mode TTL")
#         elif 5<=AMP<=20:   
#             self.pyvisa.write(f":Pulse{ch_num}:Output:Mode ADJ")
#             self.pyvisa.write(f":Pulse{ch_num}:Output:AMPL {AMP}")
#         self.pyvisa.query("*OPC?")
#         self.pyvisa.write(f":Pulse{ch_num}:SYNC {SYNC}")
#         self.pyvisa.query("*OPC?")
#         self.pyvisa.write(f":Pulse{ch_num}:CMode Normal")

#         # set up the output MUX
#         if 0 < BMUX < 256:
#             self.pyvisa.write(f":Pulse{ch_dic[channel]}:MUX {BMUX}")
#             self.pyvisa.query("*OPC?")
#         else:
#             self.pyvisa.write(f":Pulse{ch_dic[channel]}:MUX {MUX_dic[channel]}")
#             self.pyvisa.query("*OPC?")

#         # after set up, query the result
#         W = float(self.pyvisa.query(f":Pulse{ch_dic[channel]}:Width?")[:-2])
#         self.pyvisa.query("*OPC?")
#         D = float(self.pyvisa.query(f":Pulse{ch_dic[channel]}:Delay?")[:-2])
#         self.pyvisa.query("*OPC?")
#         OM = self.pyvisa.query(f":Pulse{ch_dic[channel]}:Output:Mode?")
#         self.pyvisa.query("*OPC?")
#         if OM == "ADJ\r\n":
#             A = self.pyvisa.query(f":Pulse{ch_dic[channel]}:Output:AMPL?")
#         else:
#             A = "TTL\r\n"
#         self.pyvisa.query("*OPC?")
#         S = self.pyvisa.query(f":Pulse{ch_dic[channel]}:SYNC?")[:-2]
#         self.pyvisa.query("*OPC?")
#         M = bin(int(self.pyvisa.query(f":Pulse{ch_dic[channel]}:MUX?")))[2:]
#         self.pyvisa.query("*OPC?")
        
#         print("---------------------------------------")
#         print(f"The channel {channel} is set to:")
#         print(f"Width: {W:.4e}s")
#         print(f"Delay: {D:.4e}s")
#         print(f"Synchronize to: {S}")
#         print(f"Out: {A}")
#         print("Output timers:\nHGFEDCBA")
#         print(M.zfill(8))
#         print("---------------------------------------")

# 	def expand_pulses(self, pulse_arrangement):
# 	    # the order of the parameters: [channel, duration, absolute delay wrt T0, output mode]
# 	    expanded_pulses = []
	    
# 	    # used to store the reference time point, since if there is a nested list, and the pulses stop at different point, the later one will be set as the reference
# 	    # The time marker is the last pulse stop point 
# 	    time_marker = 0 
	    
# 	    for pulse in pulse_arrangement:
# 	        if isinstance(pulse[0], list):
# 	            temp_time_markers = []
# 	            for sub_pulse in pulse:
# 	                relative_delay = sub_pulse[2]
# 	                temp_time_marker = time_marker + relative_delay
# 	                expanded_pulses.append([sub_pulse[0], sub_pulse[1], temp_time_marker, sub_pulse[3]])
# 	                temp_time_marker = time_marker + sub_pulse[1]
# 	                temp_time_markers.append(temp_time_marker)
# 	            time_marker = max(temp_time_markers)
	                
# 	        else:
# 	            relative_delay = pulse[2]
# 	            time_marker = time_marker + relative_delay
# 	            expanded_pulses.append([pulse[0], pulse[1], time_marker, pulse[3]])
# 	            time_marker = time_marker + pulse[1]
# 	    return expanded_pulses
	
#     def pulse_sequence_setup(self,pulse_sequence):
#         '''
#         This method is used to send the pulse sequence to the BNC 575 hardware
#         This method is based on the channel_set method
#         '''
#         self.disarm_all()
#         self.disable_all()
#         expanded_pulses = self.expand_pulses(pulse_sequence)
#         for pulse in expanded_pulses:
# 			pulse_channel, pulse_width, delay, pulse_output = pulse
#             self.channel_set(pulse_channel,pulse_width,delay,pulse_output)
#         self.rearm_all()

#     def start_pulses(self):
#         self.pyvisa.write(":Pulse0:State on")
#         self.pyvisa.write("*Trg")
        
#     def rearm_all(self):
#         self.pyvisa.write("*Arm")

#     def disarm_all(self):
#         self.pyvisa.write(":Pulse0:State off")

#     def disable_all(self):
#         for i in range(8):
#             self.pyvisa.write(f":Pulse{i+1}:State off")

import pyvisa
import time

class BNC575:
	def __init__(self, visa_name, timeout=5000):
		rm = pyvisa.ResourceManager()
		self.pyvisa = rm.open_resource(visa_name)
		self.pyvisa.timeout = timeout

	def clock_set(self, period, mode="CONTINUOUS", burstctr=-1):
		self.pyvisa.write(":Pulse0:Trigger:Mode Trig")
		self.pyvisa.query("*OPC?")
		self.pyvisa.write(f":Pulse0:Period {period}")

		if mode == "CONTINUOUS":
			self.pyvisa.write(":Pulse0:Mode Normal")
			self.pyvisa.query("*OPC?")
		elif mode == "SINGLE":
			self.pyvisa.write(":Pulse0:Mode Single")
			self.pyvisa.query("*OPC?")
		elif mode == "BURST":
			self.pyvisa.write(":Pulse0:Mode Burst")
			self.pyvisa.query("*OPC?")
			if burstctr > 0:
				self.pyvisa.write(f":Pulse0:Bcounter {burstctr}")
				self.pyvisa.query("*OPC?")
			else:
				print("Burst number is invalid")
		else:
			print("Mode is invalid, use upper case: CONTINUOUS, SINGLE, BURST")

		M = self.pyvisa.query(":Pulse0:Mode?")[:-2]
		P = float(self.pyvisa.query(":Pulse0:Period?")[:-2])

		if M == "BURS":
			try:
				N = self.pyvisa.query(":Pulse0:Bcounter?").strip()
				self.pyvisa.query("*OPC?")
			except pyvisa.errors.VisaIOError:
				N = "Query error"
		else:
			N = "N/A"

		print("---------------------------------------")
		print("The global clock is set to:")
		print(f"Mode: {M}")
		print(f"Period: {P:.2e}s")
		print(f"Pulses number: {N}")
		print("---------------------------------------")

	def channel_set(self, channel: str, width, delay, AMP="TTL", SYNC="TO", MUX="-1"):
		ch_dic = {"A":1, "B":2, "C":3, "D":4, "E":5, "F":6, "G":7, "H":8}
		MUX_dic = {"A":1, "B":2, "C":4, "D":8, "E":16, "F":32, "G":64, "H":128}
		BMUX = int(MUX, 2)

		if channel not in ch_dic:
			print("Invalid channel.")
			return

		ch_num = ch_dic[channel]

		self.pyvisa.write(f":Pulse{ch_num}:State on")
		self.pyvisa.query("*OPC?")
		self.pyvisa.write(f":Pulse{ch_num}:Width {width}")
		self.pyvisa.query("*OPC?")
		self.pyvisa.write(f":Pulse{ch_num}:Delay {delay}")
		self.pyvisa.query("*OPC?")

		if AMP == "TTL":
			self.pyvisa.write(f":Pulse{ch_num}:Output:Mode TTL")
		elif 5 <= AMP <= 20:
			self.pyvisa.write(f":Pulse{ch_num}:Output:Mode ADJ")
			self.pyvisa.write(f":Pulse{ch_num}:Output:AMPL {AMP}")
		self.pyvisa.query("*OPC?")

		self.pyvisa.write(f":Pulse{ch_num}:SYNC {SYNC}")
		self.pyvisa.query("*OPC?")
		self.pyvisa.write(f":Pulse{ch_num}:CMode Normal")

		if 0 < BMUX < 256:
			self.pyvisa.write(f":Pulse{ch_num}:MUX {BMUX}")
		else:
			self.pyvisa.write(f":Pulse{ch_num}:MUX {MUX_dic[channel]}")
		self.pyvisa.query("*OPC?")

		W = float(self.pyvisa.query(f":Pulse{ch_num}:Width?")[:-2])
		self.pyvisa.query("*OPC?")
		D = float(self.pyvisa.query(f":Pulse{ch_num}:Delay?")[:-2])
		self.pyvisa.query("*OPC?")
		OM = self.pyvisa.query(f":Pulse{ch_num}:Output:Mode?")
		self.pyvisa.query("*OPC?")

		if OM == "ADJ\r\n":
			A = self.pyvisa.query(f":Pulse{ch_num}:Output:AMPL?")
		else:
			A = "TTL\r\n"
		self.pyvisa.query("*OPC?")

		S = self.pyvisa.query(f":Pulse{ch_num}:SYNC?")[:-2]
		self.pyvisa.query("*OPC?")
		M = bin(int(self.pyvisa.query(f":Pulse{ch_num}:MUX?")))[2:]
		self.pyvisa.query("*OPC?")

		print("---------------------------------------")
		print(f"The channel {channel} is set to:")
		print(f"Width: {W:.4e}s")
		print(f"Delay: {D:.4e}s")
		print(f"Synchronize to: {S}")
		print(f"Out: {A}")
		print("Output timers:\nHGFEDCBA")
		print(M.zfill(8))
		print("---------------------------------------")

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
						sub_pulse[3]
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
					pulse[3]
				])
				time_marker += pulse[1]

		return expanded_pulses

	def pulse_sequence_setup(self, pulse_sequence):
		self.disarm_all()
		self.disable_all()

		expanded_pulses = self.expand_pulses(pulse_sequence)
		print(expanded_pulses)

		for pulse in expanded_pulses:
			pulse_channel, pulse_width, delay, pulse_output = pulse
			self.channel_set(pulse_channel, pulse_width, delay, pulse_output)

		self.rearm_all()

	def start_pulses(self):
		self.pyvisa.write(":Pulse0:State on")
		self.pyvisa.write("*Trg")

	def rearm_all(self):
		self.pyvisa.write("*Arm")

	def disarm_all(self):
		self.pyvisa.write(":Pulse0:State off")

	def disable_all(self):
		for i in range(8):
			self.pyvisa.write(f":Pulse{i+1}:State off")

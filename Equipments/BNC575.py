import pyvisa
import time
class BNC575:
    def __init__(self, visa_name, timeout = 5000):
        rm = pyvisa.ResourceManager()
        self.pyvisa = rm.open_resource(visa_name)
        self.pyvisa.timeout = timeout

    def clock_set(self, period, mode = "CONTINUOUS", burstctr = -1):
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
            print("Mode is invalid, the mode should be upper case. Valid Mode(CONTINuOUS; SINGLE; BURST)")
            
        M = self.pyvisa.query(":Pulse0:Mode?")[:-2]
        # # self.pyvisa.query("*OPC?")
        P = float(self.pyvisa.query(":Pulse0:Period?")[:-2])
        # self.pyvisa.query("*OPC?")
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

    def channel_set(self, channel: str, width, delay, SYNC="TO", MUX="-1"):
        ch_dic = {"A":1, "B":2, "C":3, "D":4, "E":5, "F":6, "G":7, "H":8}
        MUX_dic = {"A":1, "B":2, "C":4, "D":8, "E":16, "F":32, "G":64, "H":128}
        BMUX = int(MUX,2)
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
        self.pyvisa.write(f":Pulse{ch_num}:Output:Mode TTL")
        self.pyvisa.query("*OPC?")
		# self.pyvisa.write(f":Pulse{ch_num}:Output:AMP {AMP}")
        self.pyvisa.write(f":Pulse{ch_num}:SYNC {SYNC}")
        self.pyvisa.query("*OPC?")
        self.pyvisa.write(f":Pulse{ch_num}:CMode Normal")
        if 0 < BMUX < 256:
            self.pyvisa.write(f":Pulse{ch_dic[channel]}:MUX {BMUX}")
            self.pyvisa.query("*OPC?")
        else:
            self.pyvisa.write(f":Pulse{ch_dic[channel]}:MUX {MUX_dic[channel]}")
            self.pyvisa.query("*OPC?")
        	
        W = float(self.pyvisa.query(f":Pulse{ch_dic[channel]}:Width?")[:-2])
        self.pyvisa.query("*OPC?")
        D = float(self.pyvisa.query(f":Pulse{ch_dic[channel]}:Delay?")[:-2])
        self.pyvisa.query("*OPC?")
        # A = self.pyvisa.query(f":Pulse{ch_dic[channel]}:Output:AMP?")
        S = self.pyvisa.query(f":Pulse{ch_dic[channel]}:SYNC?")[:-2]
        self.pyvisa.query("*OPC?")
        M = bin(int(self.pyvisa.query(f":Pulse{ch_dic[channel]}:MUX?")))[2:]
        self.pyvisa.query("*OPC?")
        
        print("---------------------------------------")
        print(f"The channel {channel} is set to:")
        print(f"Width: {W:.4e}s")
        print(f"Delay: {D:.4e}s")
        print(f"Synchronize to: {S}")
        print("Output timers:\nHGFEDCBA")
        print(M.zfill(8))
        print("---------------------------------------")

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
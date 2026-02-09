import pyvisa
import time

class Agilent:
    def __init__(self, visa_name, power_limit, freq_limit, timeout = 5000):
        self.set_power_limit(power_limit)
        self.set_freq_limit(freq_limit)
        
        rm = pyvisa.ResourceManager()
        self.inst = rm.open_resource(visa_name)
        self.inst.timeout = timeout
        print(self.inst.query("*IDN?"))
        
        

    def set_power_limit(self, power_limit):
        if power_limit<=15:
            self.power_limit = power_limit
        else:
            raise RuntimeError("the power limit exceeds the limit: 15dBm")

    def set_freq_limit(self, freq_limit):
        if 100e3<=freq_limit<= 40e9:
            self.freq_limit = freq_limit
        else:
            raise RuntimeError("the freq. limit is out of range: [100KHz, 40GHz]")

    def start_output(self):
        self.inst.write(":OUTP on")

    def stop_output(self):
        self.inst.write(":OUTP off")

    def close(self):
        self.inst.close()

    def set_frequency(self, frequency):
        if frequency<=self.freq_limit:
            self.inst.write(":FREQ:CW " + str(frequency))
        else:
            raise RuntimeError(f"the freq. exceeds the limit: {self.freq_limit}Hz")

    def set_power(self, power):
        if power<=self.power_limit:
            self.inst.write(":POW:LEV " + str(power) + "DBM")
        else:
            raise RuntimeError(f"the power exceeds the limit: {self.power_limit}dBm")
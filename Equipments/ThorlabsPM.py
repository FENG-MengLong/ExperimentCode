import pyvisa

class ThorlabsPM:
    def __init__(self, visa_name, timeout = 5000):
        
        rm = pyvisa.ResourceManager()
        self.inst = rm.open_resource(visa_name)
        self.inst.timeout = timeout
        print(self.inst.query("*IDN?"))

    def readout(self, wavelength, unit = "W", average = 1000,):
        self.inst.write("SENS:RANGE:AUTO ON")
        self.inst.write("SENS:POW:UNIT W")
        self.inst.write("SENS:AVER:"+str(average))
        self.inst.write("SENS:CORR:WAV " + str(wavelength))
        power = float(self.inst.query("MEAS:POW?"))
        return power

    def close(self):
        self.inst.close()
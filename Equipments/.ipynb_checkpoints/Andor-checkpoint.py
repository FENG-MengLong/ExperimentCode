from pyAndorSDK2 import atmcd
import numpy as np

class Andor:
    """
    There are several internal parameters stored in the instance. This can save a lot when calling these current state instead of using get method.
    These parameters are stored during the set function and acquired through get method to ensure the accuracy.
    """
    def __init__(self, temperature):

        self.sdk = atmcd("")
        ret = self.sdk.Initialize("")
        self.set_temperature(temperature)
        self.set_shutter(0)
        
        self.width                = self.sdk.GetDetector()[1]
        self.height               = self.sdk.GetDetector()[2]
        self.setting_tem_point    = None
        self.EMGain               = None
        self.EMGain_range         = self.get_EMGain_range()
        self.exposure             = None
        self.read_mode            = None
        self.acquisition_mode     = None
        self.hbin                 = 1
        self.vbin                 = 1
        self.hstart      = 1
        self.hend        = self.width
        self.vstart      = 1
        self.vend        = self.height
        self.if_set_the_region = False
        self.cooler      = None
        self.fan_mode = None


    def shutdown(self):
        result = self.sdk.ShutDown()
        if result == 20002:
            print("camera is successfully shutdown")

    def stop(self):
        result = self.sdk.AbortAcquisition()
        if result == 20002:
            print("the acquisition is successfully aborted")
    
    ### Temperature control
    def set_fan_mode(self, mode):
        dic = {"full":0,"low":0,"off":2}
        """
        0: full
        1: low
        2: off
        """
        self.sdk.SetFanMode(dic[mode])
        self.fan_mode = mode
    
    def set_cooler(self, on=True):
        """Set the cooler on or off"""
        if on:
            self.sdk.CoolerON()
            self.cooler = True
        else:
            self.sdk.CoolerOFF()
            self.cooler = False
        return self.get_cooler_status()

    def get_cooler_status(self):
        """Check if the cooler is on"""
        return bool(self.sdk.IsCoolerOn())

    def get_temperature_status(self):
        """
        Get temperature status.
        """
        state = self.sdk.GetTemperatureF()[0]
        
        return ERROR_CODE[state]

    def get_temperature(self):
        """Get the current camera temperature (in C)"""
        return self.sdk.GetTemperatureF()[1]
        
    def set_temperature(self, temperature, enable_cooler=True):
        """
        Change the temperature setpoint (in C).

        If ``enable_cooler==True``, turn the cooler on automatically if present.
        """
        self.sdk.SetTemperature(temperature)
        self.setting_tem_point = temperature
        if enable_cooler:
            self.set_cooler(True)
        return temperature

    def get_temperature_range(self):
        """Return the available range of temperatures (in C)"""
        return self.sdk.GetTemperatureRange()[1:]
    
    
    ### Gain control
    def set_EMGain(self, Gain):
        """
        when EMGain = 0, means the gain is off
        """
        if self.EMGain_range[0]-1 <= Gain <= self.EMGain_range[1]:
            self.sdk.SetEMCCDGain(Gain)
            self.EMGain = self.get_EMGain() # use get function to avoid truncate error by the equipment
        else:
            print("Gain is out of range")
        
    def get_EMGain(self):
        return self.sdk.GetEMCCDGain()[1]

    def get_EMGain_range(self):
        """
        1 - a number
        """
        return self.sdk.GetEMGainRange()[1:]

    ### Acquisition parameters
    def set_exposure_time(self, time):
        self.sdk.SetExposureTime(time)
        self.exposure = self.get_exposure_time()

    def get_exposure_time(self):
        """Get current exposure"""
        return self.sdk.GetAcquisitionTimings()[1]

    def set_shutter(self, mode, ttl_mode=1, open_time = 0, close_time = 0):
        """
        mode:
        0:Fully Auto 
        1: Permanently Open 
        2: Permanently Closed 
        4: Open for FVB series
        5: Open for any series

        ttl_mode:
        0: Output TTL low signal to open shutter
        1: Output TTL high signal to open shutter

        close_time: Time shutter takes to close (milliseconds) 
        open_time: Time shutter takes to open (milliseconds) 
        """
        self.sdk.SetShutter(ttl_mode,mode,close_time,open_time)

    
    ### Acqusition mode
    def set_trigger_mode(self, mode):
        """
        0  Internal  
        1  External
        6  External Start
        7  External Exposure (Bulb)
        9  External FVB EM (only valid for EM Newton models in FVB mode)
        10 Software Trigger
        12 External Charge Shifting
        """
        self.sdk.SetTriggerMode(mode)
    
    def start_acquisition(self):
        self.sdk.PrepareAcquisition()
        self.sdk.StartAcquisition()
        self.sdk.WaitForAcquisition()

    def set_acquisition_region(self,hbin,vbin,hstart,hend,vstart,vend):
        """
        set the readout region. In this mode, the ROI is set based on software, the unwanted data is discarded
        """
        self.sdk.SetImage(hbin,vbin,hstart,hend,vstart,vend)
        self.hbin = hbin
        self.vbin = vbin
        self.hstart = hstart
        self.hend = hend
        self.vstart = vstart
        self.vend = vend
        self.if_set_the_region = True

    def set_acquisition_region_high_speed(self,hbin,vbin,hend,vend):
        """
        the crop mode can only handle the corner region. The ROI is set hardwarely
        """
        self.sdk.SetIsolatedCropMode(1,vend,hend,vbin,hbin)
        self.hbin = hbin
        self.vbin = vbin
        self.hend = hend
        self.vend = vend
        self.if_set_the_region = True
    
    def set_single_acquisition(self,exposure_time, EMGain = 0, trigger_mode = 0, read_mode = 4):
        if self.if_set_the_region:
            self.sdk.SetAcquisitionMode(1)
            self.acquisition_mode = 1
            self.set_trigger_mode(trigger_mode)
            self.set_read_mode(read_mode)
            self.set_exposure_time(exposure_time)
            self.set_EMGain(EMGain)
        else:
            raise RuntimeError("Please set up the acquisition region by set_acquisition_region()")

    ### Read acquisition result
    def set_read_mode(self, mode):
        """
        0: Full vertical binning
        1: multi track
        2: random track
        3: single track
        4: image
        """
        self.sdk.SetReadMode(mode)
        self.read_mode = mode

    def get_acquired_data(self):
        if (self.read_mode == 4):
            if (self.acquisition_mode == 1):
                dim = self.width * self.height / self.hbin / self.vbin
            elif (self.acquisition_mode==3):
                dim = self.width * self.height / self.hbin / self.vbin * self.scans
        elif (self.ReadMode==3 or self.ReadMode==0):
            if (self.AcquisitionMode==1):
                dim = self.width
            elif (self.AcquisitionMode==3):
                dim = self.width * self.scans

        ret,arr,validfirst,validlast = self.sdk.GetImages(1, 1, int(dim))

        return arr
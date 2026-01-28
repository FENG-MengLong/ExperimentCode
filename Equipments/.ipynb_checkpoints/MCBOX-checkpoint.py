from mcculw import ul
from mcculw.enums import ULRange, BoardInfo, InfoType, InterfaceType, DigitalPortType, ChannelType, ScanOptions
import numpy as np
class MCBOX():
    # device discovery, board number assignment, ignore voltages ranges from Instacal
    def __init__(self, find_device: str, use_device_detection = True):
        try:
            board_index = 0
            if use_device_detection:
                self.board_num = -1
                ul.ignore_instacal()
                dev_list = ul.get_daq_device_inventory(InterfaceType.USB)
                if len(dev_list) > 0:
                    # print(dev_list)
                    for device in dev_list:
                        if str(device) == find_device:
                            print(f'{find_device} found.')
                            self.board_num = board_index
                            print(f'Board number: {self.board_num}')
                            ul.create_daq_device(self.board_num, device)
                        board_index += 1
                    if self.board_num == -1:
                        print(f'{find_device} not found.')
                else:
                    print('No devices detected.')
        except Exception as e:
            print(f'The following error occurred: {e}')

    # configure voltage ranges on the MC box (overrides Instacal ranges)
    # unipolar voltage range (0 to +10 V) is the default unless otherwise specified
    def configure(self, channels: int, bipolar = False):
        try:
            if bipolar:
                for channel in channels:
                    ul.set_config(InfoType.BOARDINFO, self.board_num, channel, BoardInfo.DACRANGE, ULRange.BIP10VOLTS)
                    print(f'Channel {channel} has been set to the bipolar voltage range.') # optional
            else:
                for channel in channels:
                    ul.set_config(InfoType.BOARDINFO, self.board_num, channel, BoardInfo.DACRANGE, ULRange.UNI10VOLTS)
                    print(f'Channel {channel} has been set to the unipolar voltage range.') # optional
            return print('Voltage ranges set.')
        except Exception as e:
            print(f'The following error occurred: {e}')

    # converts desired voltage to a DAC integer code based on the voltage range
    def volt_to_DAC(self, voltage: float, bipolar = False):
        N = 16              # DAC codes range from 0 to 2^N - 1 = 65535
        V_out = voltage

        try:
            # bipolar voltage range
            if bipolar:
                V_out += 10.0        # done so that -10 V maps to DAC code 0
                V_ref = 20.0         # V_ref = V_max - V_min
                DAC = int((V_out/V_ref)*(2**N - 1))
            # unipolar voltage range
            else:
                if V_out < 0:
                    return print('Negative voltages are not allowed for the unipolar voltage range.')
                else:
                    V_ref = 10.0
                    DAC = int((V_out/V_ref)*(2**N - 1))
            return DAC
        except Exception as e:
            print(f'The following error occurred: {e}')

    # used to output a single voltage value to one channel
    def set_voltage_1chan(self, channel: int, voltage: float, bipolar = False, display = True):
        try:
            if bipolar:
                ao_range = ULRange.BIP10VOLTS
                ul.set_config(InfoType.BOARDINFO, self.board_num, channel, BoardInfo.DACRANGE, ULRange.BIP10VOLTS)
                V_out = self.volt_to_DAC(voltage, bipolar) # do I need to assert here again that bipolar = TRUE? CHECK THIS.
                #print(f'DAC code (bipolar): {V_out}')
            else:
                ao_range = ULRange.UNI10VOLTS
                ul.set_config(InfoType.BOARDINFO, self.board_num, channel, BoardInfo.DACRANGE, ULRange.UNI10VOLTS)
                V_out = self.volt_to_DAC(voltage, bipolar) # do I need to assert here again that bipolar = FALSE? CHECK THIS.
                #print(f'DAC code (unipolar): {V_out}')
                
            ul.a_out(self.board_num, channel, ao_range, V_out)  # the board doesn't like ul.v_out() even though it should do the same thing; all voltages except 0 get mapped to 10 V
            if display:
	            print(f'Channel {channel} has been set to {voltage} V.')
            # return 
        except Exception as e:
            print(f'The following error occurred: {e}')

    # used to output a single voltage value each to a set of channels
    def set_voltage_Nchan(self, channels: int, voltages: float, bipolar = False):
        try:
            for i in range(len(channels)):
                channel = channels[i]
                voltage = voltages[i]
                if bipolar:
                    ao_range = ULRange.BIP10VOLTS
                    ul.set_config(InfoType.BOARDINFO, self.board_num, channel, BoardInfo.DACRANGE, ULRange.BIP10VOLTS)
                    V_out = self.volt_to_DAC(voltage, bipolar)
                else:
                    ao_range = ULRange.UNI10VOLTS
                    ul.set_config(InfoType.BOARDINFO, self.board_num, channel, BoardInfo.DACRANGE, ULRange.UNI10VOLTS)
                    V_out = self.volt_to_DAC(voltage, bipolar)
                ul.a_out(self.board_num, channel, ao_range, V_out)
                print(f'Channel {channel} has been set to {voltage} V.')
            return print('Voltages successfully set.')
        except Exception as e:
            print(f'The following error occurred: {e}')

#     # used to scan over the voltage of one or more channels
#     # use ChannelType.ANALOG for channel_type arg.
#     # use ScanOptions.?? for options arg.
#     # can't use daq_out_scan() with this board. that's unfortunate...it was pretty much the kind of function I was looking for.
    
#     def scan_voltages_daq(self, board_num: int, channels: int, channel_type: int, rate: int, count: int, bipolar = False):
#         try:
#             chan_type_list = np.full(np.shape(channels), fill_value = channel_type)
            
#             if bipolar:
#                 ao_range = ULRange.BIP10VOLTS
#             else:
#                 ao_range = ULRange.UNI10VOLTS
                
#             gain_list = np.full(np.shape(channels), fill_value = ao_range)
#             chan_count = len(channels)
#             memhandle = ul.win_buf_alloc(65536)
            
#             print('Beginning voltage scans.')
#             ul.daq_out_scan(board_num, channels, chan_type_list, gain_list, chan_count, rate, count, memhandle, options = ScanOptions.ADCCLOCK)
#             return print('Voltage scans complete.')
#         except Exception as e:
#             print(f'The following error occurred: {e}')

#     def scan_voltages(self, board_num: int, low_chan: int, high_chan: int, num_points: int, rate: int, bipolar = False):
#         try:
#             if bipolar:
#                 ao_range = ULRange.BIP10VOLTS
#             else:
#                 ao_range = ULRange.UNI10VOLTS
#             memhandle = ul.win_buf_alloc(65536)
#             options = ScanOptions.SIMULTANEOUS # separate multiple options with a "|"
#             print('Beginning voltage scans.')
#             ul.a_out_scan(board_num, low_chan, high_chan, num_points, rate, ao_range, memhandle, options)
#             return print('Voltage scans complete.')
#         except Exception as e:
#             print(f'The following error occurred: {e}')



def generate_test_voltages(voltages):
    '''
    this method is used to generate the valid voltage based on the input voltage while remaining the center and size
    '''
    # set range for allowed voltages from MC box
    vmin, vmax = -10.0, 10.0

	# check if endpoints lie outside MC box voltage range
    if voltages[0] < vmin:
        voltages[0] = vmin
    elif voltages[0] > vmax:
        voltages[0] = vmax

    if voltages[-1] < vmin:
        voltages[-1] = vmin
    elif voltages[-1] > vmax:
        voltages[-1] = vmax

	# recover the voltage setpoint 
    if len(voltages) % 2 == 1:
        setpoint = voltages[len(voltages) // 2]
    elif len(voltages) % 2 == 0:
        setpoint = (voltages[len(voltages)//2] + voltages[len(voltages)//2 + 1])/2

	# calculate difference between the endpoints and the setpoint, keep the smaller of the two numbers
    diff_max = abs(setpoint - voltages[-1])
    diff_min = abs(setpoint - voltages[0])
    diff = min(diff_min, diff_max)

	# return a new voltage array centered around the setpoint with a range of 2*diff
    new_voltages = np.linspace(setpoint-diff, setpoint+diff, len(voltages))
    
    return new_voltages
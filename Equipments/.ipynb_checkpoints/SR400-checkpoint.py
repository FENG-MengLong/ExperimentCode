"""
SR400 Photon Counter Control Class
Author: Xinyu Feng
Created: 12/23/2025

This module provides a Python interface for controlling the Stanford Research Systems
SR400 Gated Photon Counter via VISA (Virtual Instrument Software Architecture) communication.

The SR400 is a dual-channel photon counter with gated counting capabilities, commonly used
in quantum optics experiments, single-photon detection, and time-resolved measurements.

Main Features:
    - Dual-channel counting (Channels A and B) with independent or correlated modes
    - Gated counting with configurable delay and width
    - Multiple counting modes: Independent, Difference, Sum, and Mutual
    - Discriminator level control for signal thresholding
    - Time-resolved measurements with preset counting periods
    - Scan mode support for parameter sweeps

Common Usage:
    The most frequently used methods are:
    - counter_set(): Configure all counting parameters at once
    - read_count(): Read count values from specified channels
    - disc_level(): Set discriminator threshold levels

Example:
    >>> counter = SR400("GPIB0::12::INSTR")
    >>> counter.counter_set(
    ...     count_mode="INDEPENDENT",
    ...     count_preset=1.0,
    ...     count_period_num=10,
    ...     dwell=0.1,
    ...     sourceA="INPUT1",
    ...     sourceB="INPUT2",
    ...     gate_A_mode="FIXED",
    ...     gate_B_mode="FIXED",
    ...     gate_A_delay=0.0,
    ...     gate_A_width=1e-3,
    ...     gate_B_delay=0.0,
    ...     gate_B_width=1e-3
    ... )
    >>> counter.count_start()
    >>> count_a = counter.read_count("A")
    >>> count_b = counter.read_count("B")

Note:
    There is no integrated function for scanning timing parameters. To perform scans:
    1. Write a loop in your experiment code to scan parameters within the loop
    2. Use the SR400's built-in scan commands (not implemented in this version)
"""
import pyvisa
import time

class SR400:

    def __init__(self, visa_name , timeout = 5000):
        """
        Initialize connection to the SR400 photon counter.
        
        Parameters:
        -----------
        visa_name : str
            VISA resource name (e.g., "GPIB0::12::INSTR" or "USB0::0x0957::0x0407::INSTR")
        timeout : int, optional
            Communication timeout in milliseconds (default: 5000)
        """
        rm = pyvisa.ResourceManager()
        self.pyvisa = rm.open_resource(visa_name)
        #print(self.pyvisa.query("*IDN?"))  # Carlos: It doesn't seem to like this line, so I commented it out.
        self.pyvisa.timeout = timeout
        self.gate_counter_dic = {"A":0, "B":1}
        self.gate_counter_dic_r = {"0\r\n":"A", "1\r\n":"B"}
        self.counter_dic = {"A":0, "B":1, "T":2}
        self.counter_dic_r = {"0\r\n":"A", "1\r\n":"B", "2\r\n":"T"}
        
    ### below are the methods to set gate parameters

    def gate_mode(self, counter = "A", mode = "CW", query = False):
        """
        Set or query the gate operating mode.
        
        Parameters:
        -----------
        counter : str, optional
            Counter channel: "A" or "B" (default: "A")
        mode : str, optional
            Gate mode: "CW" (continuous wave), "FIXED" (fixed timing), or "SCAN" (scan mode) (default: "CW")
        query : bool, optional
            If True, query current mode instead of setting (default: False)
        
        Returns:
        --------
        str or None
            Current gate mode if query=True, otherwise None
        """
        mode_dic = {"CW":"0", "FIXED":"1", "SCAN":"2"}
        mode_dic_r = {"0\r\n":"CW", "1\r\n":"FIXED", "2\r\n":"SCAN"}
        #
        if query:
            return mode_dic_r[self.pyvisa.query("GM " + str(self.gate_counter_dic[counter]))]
        else:
            try:
                self.pyvisa.write("GM " + str(self.gate_counter_dic[counter]) + "," +  mode_dic[mode])
            except:
                print("Illegal keywords from gate_mode")

    def gate_delay(self, counter = "A", delay = 0.0, query = False):
        """
        Set or query the gate delay time.
        
        Parameters:
        -----------
        counter : str, optional
            Counter channel: "A" or "B" (default: "A")
        delay : float, optional
            Gate delay in seconds, range: 0 to 999.2e-3 (default: 0.0)
        query : bool, optional
            If True, query current delay instead of setting (default: False)
        
        Returns:
        --------
        str or None
            Current gate delay if query=True, otherwise None
        """
        if query:
            return self.pyvisa.query("GD " + str(self.gate_counter_dic[counter]))
        elif 0 <= delay <= 999.2e-3:
            try:
                self.pyvisa.write("GD " + str(self.gate_counter_dic[counter]) + "," + str(delay))
            except:
                print("illegal keywords from gate_delay")
        else:
            print("gate_delay delay exceeds the range")

    def gate_width(self, counter = "A", width = 1e-3, query = False):
        """
        Set or query the gate width duration.
        
        Parameters:
        -----------
        counter : str, optional
            Counter channel: "A" or "B" (default: "A")
        width : float, optional
            Gate width in seconds, range: 0.005e-6 to 999.2e-3 (default: 1e-3)
        query : bool, optional
            If True, query current width instead of setting (default: False)
        
        Returns:
        --------
        str or None
            Current gate width if query=True, otherwise None
        """
        if query:
            return self.pyvisa.query("GW " + str(self.gate_counter_dic[counter]))
        elif 0.005e-6 <= width <= 999.2e-3:
            try:
                self.pyvisa.write("GW " + str(self.gate_counter_dic[counter]) + "," + str(width))
            except:
                print("illegal keywords from the gate_width")
        else:
            print("gate width exceeds the range")

    ### below are the methods to set the counting
    
    def count_mode(self, mode = "INDEPENDENT", query = False):
        """
        Set or query the counting mode.
        
        Parameters:
        -----------
        mode : str, optional
            Counting mode: "INDEPENDENT", "DIFFERENCE", "SUM", or "MUTUAL" (default: "INDEPENDENT")
        query : bool, optional
            If True, query current mode instead of setting (default: False)
        
        Returns:
        --------
        str or None
            Current counting mode if query=True, otherwise None
        """
        mode_dic = {"INDEPENDENT":"0", "DIFFERENCE":"1", "SUM":"2", "MUTUAL":"3"}
        mode_dic_r = {"0\r\n":"INDEPENDENT", "1\r\n":"DIFFERENCE", "2\r\n":"SUM", "3\r\n":"MUTUAL"}
        if query:
            return mode_dic_r[self.pyvisa.query("CM")]
        else:
            try:
                self.pyvisa.write("CM " + mode_dic[mode])
            except:
                print("incorrect mode from the count mode")

    def count_input(self, counter = "A", source = "INPUT1", query = False):
        """
        Set or query the input source for a counter.
        
        Parameters:
        -----------
        counter : str, optional
            Counter channel: "A", "B", or "T" (default: "A")
        source : str, optional
            Input source: "10MHz", "INPUT1", "INPUT2", or "TRIG" (default: "INPUT1")
            Note: Available sources depend on counter:
                - Counter A: "10MHz" or "INPUT1"
                - Counter B: "INPUT1" or "INPUT2"
                - Counter T: "10MHz", "INPUT2", or "TRIG" (not "INPUT1")
        query : bool, optional
            If True, query current source instead of setting (default: False)
        
        Returns:
        --------
        str or None
            Current input source if query=True, otherwise None
        """
        source_dic = {"10MHz":0, "INPUT1":1, "INPUT2":2, "TRIG":3}
        source_dic_r = {"0\r\n":"10MHz", "1\r\n":"INPUT1", "2\r\n":"INPUT2", "3\r\n":"TRIG"}
        if query:
            return source_dic_r[self.pyvisa.query("CI " + str(self.counter_dic[counter]))]
        elif (counter == "A") and (source_dic[source] <= 1):
            self.pyvisa.write("CI 0," + str(source_dic[source]))
        elif (counter == "B") and (1 <= source_dic[source] <= 2):
            self.pyvisa.write("CI 1," + str(source_dic[source]))
        elif (counter == "T") and (source_dic[source] != 1):
            self.pyvisa.write("CI 2," + str(source_dic[source]))
        else:
            print("wrong mapping from the count_input")    

    def count_period_number(self, number = 1e1, query = False):
        """
        Set or query the number of counting periods.
        
        Parameters:
        -----------
        number : float, optional
            Number of counting periods (default: 1e1)
        query : bool, optional
            If True, query current period number instead of setting (default: False)
        
        Returns:
        --------
        str or None
            Current period number if query=True, otherwise None
        """
        if query:
            return self.pyvisa.query("NP")
        else:
            self.pyvisa.write("NP " + str(number))

    def count_preset(self, counter = "T", number = 1e0, query = False):
        """
        Set or query the preset count value or time.
        
        Parameters:
        -----------
        counter : str, optional
            Counter channel: "B" or "T" (not "A") (default: "T")
        number : float, optional
            Preset value:
                - For counter T: time in seconds (>= 1e-7) if T input is "10MHz", 
                  or count value otherwise
                - For counter B: count value (1.0 to 9e11) (default: 1e0)
        query : bool, optional
            If True, query current preset instead of setting (default: False)
        
        Returns:
        --------
        str or None
            Current preset value if query=True, otherwise None
        """
        TI = self.pyvisa.query("CI 2")
        # print(TI)
        if counter == "A":
            print("wrong counter")
        elif query:
            result = self.pyvisa.query("CP " + ("2" if counter == "T" else "1"))
            if TI == "0\r\n":
                result = str(float(result[:-2])/10e6) + "s\r\n"
            return result
        elif counter == "T":
            if TI == "0\r\n":
                if number >= 1e-7:
                    self.pyvisa.write("CP 2," + str(number * 1e7))
                else:
                    print("invalid preset number")
            else:
                self.pyvisa.write("CP 2," + str(number))
        elif counter =="B" and 1.0 <= number < 9e11:
            self.pyvisa.write("CP 1," + (str(number)))
        else:
            print("invalid number from the count_preset")
        # elif 1.0 <= number < 9e11:
        #     if counter == "T":
        #         self.pyvisa.write("CP 2," + (str(number * 1e7) if TI == "0\r\n" else str(number)))
        #     elif counter == "B":
        #         self.pyvisa.write("CP 1," + (str(number)))
        #     else:
        #         print("invalid counter from the count_preset")
        # else:
        #     print("invalid number from the count_preset")

    def dwell_time(self, time = 0.0, query = False):
        """
        Set or query the dwell time between measurements.
        
        Parameters:
        -----------
        time : float, optional
            Dwell time in seconds. Use 0.0 for external trigger mode.
            Range: 2e-3 to 6e1, or 0.0 for external (default: 0.0)
        query : bool, optional
            If True, query current dwell time instead of setting (default: False)
        
        Returns:
        --------
        str or None
            Current dwell time if query=True, otherwise None
        """
        if query:
            return self.pyvisa.query("DT")
        elif time == 0:
            self.pyvisa.write("DT 0")
        elif 2e-3 <= time <= 6e1:
            self.pyvisa.write("DT " + str(time))
        else:
            print("invalid input from the dwell_time")

    ### below are the method for the start and end
    
    def count_restart(self):
        """
        Reset counters and start counting.
        
        This is equivalent to pressing RESET followed by START on the front panel.
        """
        self.pyvisa.write("CR") # CR command resets the counters
        self.pyvisa.write("CS") # CS command same as START key

    def count_reset(self):
        """
        Reset the counters.
        
        This is equivalent to pressing RESET on the front panel.
        """
        self.pyvisa.write("CR") # CR command resets the counters

    def count_stop(self):
        """
        Stop counting.
        
        This is equivalent to pressing STOP on the front panel.
        """
        self.pyvisa.write("CH") # same effect as pressing the STOP key

    def count_start(self):
        """
        Start counting.
        
        This is equivalent to pressing START on the front panel.
        """
        self.pyvisa.write("CS") # same effect as pressing the START key

    ### below are methods for the panel bottoms

    def front_button(self, botton = "STOP"):
        """
        Simulate pressing a front panel button.
        
        Parameters:
        -----------
        botton : str, optional
            Button name: "DOWN", "RIGHT", "LEVEL", "SETUP", "COM", "STOP", 
            "LOCAL", "RESET", "LEFT", "UP", "MODE", "AGATE", "BGATE", or "START" (default: "STOP")
        """
        keydic = {"DOWN": "0", "RIGHT": "1", "LEVEL": "2", "SETUP": "3",\
                    "COM": "4", "STOP": "5", "LOCAL": "6", "RESET": "7",\
                    "LEFT": "8", "UP": "9", "MODE": "10", "AGATE": "11",\
                    "BGATE": "12", "START": "13"}
        self.pyvisa.write("CK " + keydic[botton])

    def message_display(self, message = ""):
        """
        Display a message on the instrument screen.
        
        Parameters:
        -----------
        message : str, optional
            Message to display on the SR400 screen (default: "")
        """
        self.pyvisa.write("MS" + message)

    ### below are method for readout

    def read_count(self, counter, position = -1):
        """
        Read count value from specified counter and position.
        
        Parameters:
        -----------
        counter : str
            Counter channel: "A" or "B"
        position : int, optional
            Position in scan array. Use -1 for current/last position (default: -1)
            Must be > 0 if specified
        
        Returns:
        --------
        int
            Count value, or -1 if invalid parameters, or -2 if communication error
        """
        try:
            if position == -1 or position > 0:
                if counter == "A":
                    count = int(self.pyvisa.query("QA") if position == -1 else self.pyvisa.query("QA " + str(position)))
                elif counter == "B":
                    count = int(self.pyvisa.query("QB") if position == -1 else self.pyvisa.query("QB " + str(position)))
                else:
                    count = -1
                    print("wrong counter from the read_count")
                return count
            else:
                print("invalid position from the read_count")
                return -1
        except Exception as e:
            # print(f"[Error] read_count failed: {e}")
            self.flush_stale_response()
            return -2

    def read_entire_counts(self, counter, length, max_retries=10, retry_delay=0.05):
        """
        Read all counts from a scan measurement with retry logic.
        
        This method first verifies the scan is complete by reading the last point,
        then reads all counts from position 1 to length.
        
        Parameters:
        -----------
        counter : str
            Counter channel: "A" or "B"
        length : int
            Number of scan points to read (positions 1 to length)
        max_retries : int, optional
            Maximum number of retry attempts for each read (default: 10)
        retry_delay : float, optional
            Delay in seconds between retry attempts (default: 0.05)
        
        Returns:
        --------
        list of int
            List of count values. Failed reads are represented as -2.
        
        Raises:
        -------
        TimeoutError
            If the final scan point cannot be read after max_retries attempts
        """
        # Try to read the last point (to make sure the scan is finished)
        retries = 0
        last_count = -1
        while retries < max_retries:
            try:
                last_count = self.read_count(counter=counter, position=length)
                if last_count > -1:
                    break  # success
                if last_count == -2:
                    # print("Warning: exception on final point read")
                    retries += 1
            except Exception as e:
                # print(f"Warning: exception on final point read: {e}")
                time.sleep(retry_delay)
                retries += 1
            time.sleep(0.05)
			
        # if retries != 0:
        #     print(f"But get the final point successfully at the {retries+1} retry")

        if last_count == -1:
            raise TimeoutError(f"Failed to read final scan point (position {length}) after {max_retries} retries.")

        # print(f"One entire measurement is done, the last count is {last_count}")

        # Proceed to read the full array
        counts = []
        for i in range(1, length + 1):
            retries = 0
            read_success = False
            while retries < max_retries:
                try:
                    count = self.read_count(counter=counter, position=i)
                    if count >= 0:
                        counts.append(count)
                        read_success = True
                        break
                    else:
                        print("Warning: exception on the result read")
                        retries += 1
                except Exception as e:
                    print(f"Warning: exception on the result read: {e}")
                    time.sleep(retry_delay)
                    retries += 1

            if retries != 0:
                print(f"But get the result successfully at the {retries+1} retry")

            if read_success == False:
                counts.append(-2)

        # print(counts)
        return counts
        
    ### below are the methods for discriminators

    def disc_level(self, counter, level, slope = True):
        """
        Set discriminator threshold level and slope.
        
        Parameters:
        -----------
        counter : str
            Counter channel: "A" or "B"
        level : float
            Discriminator threshold level in volts, range: -0.3 to 0.3
        slope : bool, optional
            If True, trigger on positive slope; if False, trigger on negative slope (default: True)
        """
        if -0.3<=level<=0.3:
            self.pyvisa.write("DS " + str(self.gate_counter_dic[counter]) + "," + ("0" if slope else "1"))
            self.pyvisa.write("DL " + str(self.gate_counter_dic[counter]) + "," + str(level))
        else:
            print("disc_level exceeds level range")

    ### below are some integrated method

    def counter_set(self, count_mode, count_preset, count_period_num, dwell, sourceA, sourceB, gate_A_mode, gate_B_mode, gate_A_delay = -1, gate_A_width = -1,
                     gate_B_delay = -1, gate_B_width = -1):
        """
        Configure all counting parameters in one integrated call.
        
        This is a convenience method that sets multiple parameters at once and
        displays the current configuration. It is one of the most commonly used methods.
        
        Parameters:
        -----------
        count_mode : str
            Counting mode: "INDEPENDENT", "DIFFERENCE", "SUM", or "MUTUAL"
        count_preset : float
            Preset count value or time for counter T
        count_period_num : float
            Number of counting periods
        dwell : float
            Dwell time in seconds (0.0 for external trigger)
        sourceA : str
            Input source for counter A: "10MHz" or "INPUT1"
        sourceB : str
            Input source for counter B: "INPUT1" or "INPUT2"
        gate_A_mode : str
            Gate A mode: "CW", "FIXED", or "SCAN" (SCAN not supported in this function)
        gate_B_mode : str
            Gate B mode: "CW", "FIXED", or "SCAN" (SCAN not supported in this function)
        gate_A_delay : float, optional
            Gate A delay in seconds (required if gate_A_mode="FIXED", default: -1)
        gate_A_width : float, optional
            Gate A width in seconds (required if gate_A_mode="FIXED", default: -1)
        gate_B_delay : float, optional
            Gate B delay in seconds (required if gate_B_mode="FIXED", default: -1)
        gate_B_width : float, optional
            Gate B width in seconds (required if gate_B_mode="FIXED", default: -1)
        
        Note:
        -----
        If gate mode is "FIXED", the corresponding delay and width must be provided.
        SCAN mode is not supported in this integrated function.
        """
        self.count_mode(mode = count_mode)
        current_mode = self.count_mode(query=True)

        
        self.dwell_time(dwell)
        current_dwell = self.dwell_time(query=True)
        if current_dwell == "0\r\n":
            current_dwell = "External\r\n"
            self.count_input(counter="T",source="10MHz")
        else:
            self.count_input(counter="T",source="TRIG")
        current_TI = self.count_input(counter="T",query=True)
        self.count_preset(counter = "T", number = count_preset)
        current_preset = self.count_preset(query=True)
        
        self.count_period_number(number = count_period_num)
        current_period_number = self.count_period_number(query=True)
        
        self.count_input(counter="A",source=sourceA)
        current_AI = self.count_input(counter="A",query=True)
        self.count_input(counter="B",source=sourceB)
        current_BI = self.count_input(counter="B",query=True)
        print("-"*60)
        print("The photon counter is now set to:\n\n" + 
              "Counting Mode: " + current_mode +
             "\nT Input: " + current_TI + 
              "\nT Preset: " + current_preset +
             "Period number: " + current_period_number + 
              "Dwell time: " + current_dwell +
             "Counter A source: " + current_AI + 
              "\nCounter B source: " + current_BI)

        self.gate_mode(counter="A",mode=gate_A_mode)
        if gate_A_mode == "FIXED":
            self.gate_delay(counter="A",delay = gate_A_delay)
            self.gate_width(counter="A",width = gate_A_width)
            print("\nThe gate A is set to:\n\n" + 
                  "Delay: " + self.gate_delay(counter="A", query=True) +
                  "Width: " + self.gate_width(counter="A",query=True))
        elif gate_A_mode == "SCAN":
            print("Invaid gate A mode in this function")
        else:
            print("\nThe gate A is set to: CW")

        self.gate_mode(counter="B",mode=gate_B_mode)
        if gate_B_mode == "FIXED":
            self.gate_delay(counter="B",delay = gate_B_delay)
            self.gate_width(counter="B",width = gate_B_width)
            print("\nThe gate B is set to:\n\n" + 
                  "Delay: " + self.gate_delay(counter="B", query=True)+
                 "Width: " + self.gate_width(counter="B",query=True))
        elif gate_B_mode == "SCAN":
            print("Invaid gate B mode in this function")
        else:
            print("\nThe gate B is set to: CW")
        print("-"*60)

    def flush_stale_response(self):
        """Flush unread garbage from the VISA buffer without resetting the device."""
        # junk = self.pyvisa.read()
        # print(f"[Flush] Flushed: {repr(junk)}")
        try:
            while True:
                junk = self.pyvisa.read()
                # print(f"[Flush] Flushed: {repr(junk)}")
        except:
            pass  # Ends when buffer is empty or times out
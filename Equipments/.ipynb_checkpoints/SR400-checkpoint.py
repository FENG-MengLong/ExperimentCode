'''
4/25/2025
The class below is used to drive the photon counter SR400, the most common used functions are: counter_set, read_count and disc_level. 
They are setting the counting timing parameters, reading out the counting results and setting the discriminator levels

There is no integrated funciton for scanning the timing parameters. 
If needed, there are two ways to realize:
1. write a loop in your experiment code to scan the parameters within the loop
2. use the commands of scanning for SR400 to realize, which I didn't write at this version
'''
import pyvisa
import time
class SR400:    
    def __init__(self, visa_name , timeout = 5000):
        rm = pyvisa.ResourceManager()
        self.pyvisa = rm.open_resource(visa_name)
        self.pyvisa.timeout = timeout
        self.gate_counter_dic = {"A":0, "B":1}
        self.gate_counter_dic_r = {"0\r\n":"A", "1\r\n":"B"}
        self.counter_dic = {"A":0, "B":1, "T":2}
        self.counter_dic_r = {"0\r\n":"A", "1\r\n":"B", "2\r\n":"T"}
        
    ### below are the methods to set gate parameters

    def gate_mode(self, counter = "A", mode = "CW", query = False):
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
        if query:
            return self.pyvisa.query("NP")
        else:
            self.pyvisa.write("NP " + str(number))

    def count_preset(self, counter = "T", number = 1e0, query = False):
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
        self.pyvisa.write("CR") # CR command resets the counters
        self.pyvisa.write("CS") # CS command same as START key

    def count_reset(self):
        self.pyvisa.write("CR") # CR command resets the counters

    def count_stop(self):
        self.pyvisa.write("CH") # same effect as pressing the STOP key

    def count_start(self):
        self.pyvisa.write("CS") # same effect as pressing the START key

    ### below are methods for the panel bottoms

    def front_button(self, botton = "STOP"):
        keydic = {"DOWN": "0", "RIGHT": "1", "LEVEL": "2", "SETUP": "3",\
                    "COM": "4", "STOP": "5", "LOCAL": "6", "RESET": "7",\
                    "LEFT": "8", "UP": "9", "MODE": "10", "AGATE": "11",\
                    "BGATE": "12", "START": "13"}
        self.pyvisa.write("CK " + keydic[botton])

    def message_display(self, message = ""):
        self.pyvisa.write("MS" + message)

    ### below are method for readout

    def read_count(self, counter, position = -1):
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
            print(f"[Error] read_count failed: {e}")
            self.flush_stale_response()
            return -2

    def read_entire_counts(self, counter, length, max_retries=10, retry_delay=0.05):
        # Try to read the last point (to make sure the scan is finished)
        retries = 0
        last_count = -1
        while retries < max_retries:
            try:
                last_count = self.read_count(counter=counter, position=length)
                if last_count > -1:
                    break  # success
                if last_count == -2:
                    print("Warning: exception on final point read")
                    retries += 1
            except Exception as e:
                print(f"Warning: exception on final point read: {e}")
                time.sleep(retry_delay)
                retries += 1
            time.sleep(0.05)
			
        if retries != 0:
            print(f"But get the final point successfully at the {retries+1} retry")

        if last_count == -1:
            raise TimeoutError(f"Failed to read final scan point (position {length}) after {max_retries} retries.")

        print(f"One entire measurement is done, the last count is {last_count}")

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
        if -0.3<=level<=0.3:
            self.pyvisa.write("DS " + str(self.gate_counter_dic[counter]) + "," + ("0" if slope else "1"))
            self.pyvisa.write("DL " + str(self.gate_counter_dic[counter]) + "," + str(level))
        else:
            print("disc_level exceeds level range")

    ### below are some integrated method

    def counter_set(self, count_mode, count_preset, count_period_num, dwell, sourceA, sourceB, gate_A_mode, gate_B_mode, gate_A_delay = -1, gate_A_width = -1,
                     gate_B_delay = -1, gate_B_width = -1):
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
        print("---------------------------------------")
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
        print("---------------------------------------")

    def flush_stale_response(self):
        """Flush unread garbage from the VISA buffer without resetting the device."""
        # junk = self.pyvisa.read()
        # print(f"[Flush] Flushed: {repr(junk)}")
        try:
            while True:
                junk = self.pyvisa.read()
                print(f"[Flush] Flushed: {repr(junk)}")
        except:
            pass  # Ends when buffer is empty or times out
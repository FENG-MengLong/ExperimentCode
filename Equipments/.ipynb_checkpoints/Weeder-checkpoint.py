"""
04/25/25

This class is used to communincate with the WeederTech WTMCD-M which controls the stepper motor. 

Commands sent to this device have the following structure:
(1) Header character (this is typically just "A"; header characters are listed in Table 1 of the WeederTech manual, pg. 64)
(2) Command character (this tells the device which command your trying to execute; command characters are listed in Table 2 of the WeederTech manual, pg. 65)
(3) Variable characters (optional, these tell the device how to execute the command; eg. M1000 tells the device to move to position 1000)
(4) Carriage return ('\r', indicates the end of a command)

There are also two special characters (call these "diagonostic characters") that can isolate problems the device has with understanding a command string: 
("?") will be returned after an invalid command or variable
("!") will be returned after a power-on reset or brown-out

Before every command in this class is an explanation of what it does. More information can be found in the WeederTech manual.

"""

import pyvisa
import time

class Weeder:
	# defines and discovers stepper motor
	def __init__(self, visa_name, timeout = 5000):
		rm = pyvisa.ResourceManager()
		self.pyvisa = rm.open_resource(visa_name, baud_rate = 9600, data_bits = 8, 
									   parity = pyvisa.constants.Parity.none, 
									   stop_bits = pyvisa.constants.StopBits.one)
		self.pyvisa.timeout = 5000

	# writes motor settings to txt files
	# motor position will always be saved, but optionally one can save other parameters as well
	def save(self, header: str, query = True, more = False):
		# query motor settings
		current_position = self.position(header = "A", query = True)[1:]
		current_position = self.position(header = "A", query = True)[1:]
		current_position = self.position(header = "A", query = True)[1:]
		
		velocity = self.velocity(header = "A", query = True)[2:]
		velocity = self.velocity(header = "A", query = True)[2:]
		velocity = self.velocity(header = "A", query = True)[2:]
		
		ramp_rate = self.ramp_rate(header = "A", query = True)[2:]
		ramp_rate = self.ramp_rate(header = "A", query = True)[2:]
		ramp_rate = self.ramp_rate(header = "A", query = True)[2:]
		
		excitation_mode = self.excite(header = "A", query = True)[2:]
		excitation_mode = self.excite(header = "A", query = True)[2:]
		excitation_mode = self.excite(header = "A", query = True)[2:]
		
		drive_current = self.current(header = "A", query = True)[2:]
		drive_current = self.current(header = "A", query = True)[2:]
		drive_current = self.current(header = "A", query = True)[2:]
		
		idle_current = self.idle(header = "A", query = True)[2:]
		idle_current = self.idle(header = "A", query = True)[2:]
		idle_current = self.idle(header = "A", query = True)[2:]

		# save the motor position to file
		with open(r"X:\migratedData\Data\motor.txt",'w') as file:
			file.write(str(current_position))

		# used if you want to save other motor settings
		if more:
			with open(r"X:\migratedData\Data\motor-params.txt", 'w') as file:
				file.write("Velocity: " + str(velocity) + '\n')
				file.write("Ramp rate: " + str(ramp_rate) + '\n')
				file.write("Excitation mode: " + str(excitation_mode) + '\n')
				file.write("Drive current: " + str(drive_current) + '\n')
				file.write("Idle current: " + str(idle_current) + '\n')
		return "saving complete."

	# reads out motor settings from txt file 
	def read(self, file_path: str):
		try:
			with open(file_path, 'r') as file:
				lines = file.readlines()
				for line in lines:
					print(line.strip())
		except FileNotFoundError:
			print(f'Error: File not found at path: {file_path}')
			return None
		except Exception as e:
			print(f'An error occurred: {e}')
			return None
			
	###### below are the device commands we'll use on a regular basis ######

	# modifies the motor position counter
    # position = 0 to 16,777,215 (if omitted, will read out current position)
	def position(self, header: str, position = 0, query = False):
		if query:
			self.pyvisa.write(header + "P\r")
			return self.pyvisa.read("\r")
		else:
			self.pyvisa.write(header + "P" + str(position) + "\r")

	# moves stepper motor to a specific position 
    # position = 0 to 2^24 - 1 = 16,777,215
	# def move(self, header: str, position: int):
	# 	step_min = 1000
	# 	step_max = 5000

	# 	if position > step_max:
	# 		return print("The desired position exceeds the maximum allowed position.")
	# 	elif position < step_min:
	# 		return print("The desired position falls below the minimum allowed position.")
	# 	else:	
	# 		# check current position
	# 		current_position = self.position(header, query = True)[1:]
	# 		current_position = self.position(header, query = True)[1:]
	# 		current_position = self.position(header, query = True)[1:]
	# 		#print(current_position)
			
	# 		# modify stepper motor position
	# 		self.pyvisa.write(header + "M" + str(position) + "\r")
	
	# 		# check that the change went through
	# 		new_position = self.position(header, query = True)[1:]
	# 		new_position = self.position(header, query = True)[1:]
	# 		new_position = self.position(header, query = True)[1:]
	# 		#print(new_position)
			
	# 		return current_position, new_position

	def sleep(self, step_change):
		slope = 0.02 # 20 ms/step
		return slope*step_change
		
		
	def move(self, header: str, position: int):
		step_min = 1000
		step_max = 20000

		if position > step_max:
			raise RuntimeError("The desired position exceeds the maximum allowed position. Set the motor position below {}.".format(step_max))
		elif position < step_min:
			raise RuntimeError("The desired position falls below the minimum allowed position. Set the motor position above {}.".format(step_min))
		else:
			# check current position
			current_position = self.position(header, query = True)[1:]
			current_position = self.position(header, query = True)[1:]
			current_position = self.position(header, query = True)[1:]
			#print("Current position: {}".format(current_position))

			step_change = abs(int(current_position) - position)
			
			# modify stepper motor position
			self.pyvisa.write(header + "M" + str(position) + "\r")

			time_to_wait = self.sleep(step_change)

			time.sleep(time_to_wait)
			
			# check that the change went through
			new_position = self.position(header, query = True)[1:]
			new_position = self.position(header, query = True)[1:]
			new_position = self.position(header, query = True)[1:]
			#print("New position: {}".format(new_position))

			return print("Old position: {}\nNew position: {}".format(current_position, new_position))

	# only used within the scan loop and after checking the moving range manually
	def move_direct(self, header: str, position: int):
			
		self.pyvisa.write(header + "M" + str(position) + "\r")
		# self.position(header, query = True)
		# self.position(header, query = True)
		# self.position(header, query = True)

	def advance(self, header: str, num_step: int):
		step_min = 1000
		step_max = 20000
		
		# check the current position
		current_position = self.position(header, query = True)[1:]
		current_position = self.position(header, query = True)[1:]
		current_position = self.position(header, query = True)[1:]
		current_position = int(current_position)
		#print("Current position: {}".format(current_position))

		step_change = abs(num_step)

		new_position = current_position + num_step

		if new_position > step_max:
			raise RuntimeError("The desired position exceeds the maximum allowed position. Set the motor position below {}.".format(step_max))
		elif new_position < step_min:
			raise RuntimeError("The desired position falls below the minimum allowed position. Set the motor position above {}.".format(step_min))
		else:
			# move stepper motor by num_step number of steps
			self.pyvisa.write(header + "M" + str(current_position + num_step) + "\r")
			time_to_wait = self.sleep(step_change)
			time.sleep(time_to_wait)
			
			# check that the change went through
			# new_position = self.position(header, query = True)[1:]
			# new_position = self.position(header, query = True)[1:]
			# new_position = self.position(header, query = True)[1:]
			#print("New position: {}".format(new_position))
	
			#return print("Old position: {}\nNew position: {}".format(current_position, new_position))
			
	# moves stepper motor one step in a specific direction
    # direction = + or -
	def step (self, header: str, direction: str):
		self.pyvisa.write(header + "S" + direction + "\r")
		return self.pyvisa.read("\r")

	###### below are commands will we use occasionally, and mostly just to ask the device for the current value of a given parameter ######

	# sets the pulse-per-second (pps) rate for move, home, and drive functions
    # velocity = 1 to 200 (will be multiplied by 50 pps; if omitted, will return current setting)
	def velocity(self, header: str, velocity = 1, query = False):
		if query:
			self.pyvisa.write(header + "V\r")
			return self.pyvisa.read("\r")
		else:
			self.pyvisa.write(header + "V" + str(velocity) + "\r")

	# sets the ramp rate used in the acceleration and deceleration curves
    # rate = 1 to 255 (default = 50; if omitted, will return current value)
	def ramp_rate(self, header: str, rate = 50, query = False):
		if query:
			self.pyvisa.write(header + "R\r")
			return self.pyvisa.read("\r")
		else:
			self.pyvisa.write(header + "R" + str(rate) + "\r")

	# sets the excitation mode to determine the number of microsteps per step
    # microsteps = 1, 2, 4, 8, 16, 32, or 64 (default = 1; if omitted, will return current setting)
	def excite(self, header: str, microsteps = 1, query = False):
		if query:
			self.pyvisa.write(header + "E\r")
			return self.pyvisa.read("\r") 
		else:
			self.pyvisa.write(header + "E" + str(microsteps) + "\r")

	# sets the drive current, used when the motor is rotating
    # current = 1 to 20 (will be multiplied by 0.1 A; default = 5; if omitted, will return present value)
	def current(self, header: str, current = 5, query = False):
		if query:
			self.pyvisa.write(header + "C\r")
			return self.pyvisa.read("\r")
		else:
			self.pyvisa.write(header + "C" + str(current) + "\r")
        
    # sets the idle reduction current, used when the motor is at rest
    # idle = 1 to 10 (will be multipled by 10 and read as % of drive current; default = 2)
    # if idle is omitted, will return the present value
	def idle(self, header: str, idle = 2, query = False):
		if query:
			self.pyvisa.write(header + "I\r")
			return self.pyvisa.read("\r")
		else:
			self.pyvisa.write(header + "I" + str(idle) + "\r")
        
    # displays the current state of the limit switch indicated by direction (+ or -) 
    # returns "direction C" for closed and "direction O" for open
	def limit(self, header: str, direction: str):
		self.pyvisa.write(header + "L" + direction + "\r")
		return self.pyvisa.read("\r")

	###### below are functions that we should avoid using if possible since they can lead to the motor moving without end, which could damage the cavity bellow ######

	# moves stepper motor in a specific direction until runoff counter is triggered
    # direction = + or -
    # runoff = 0 to 255 (if omitted, defaults to zero)
	def home(self, header: str, direction: str, runoff = 0):
		self.pyvisa.write(header + "H" + direction + str(runoff) + "\r")
		return self.pyvisa.read("\r")

	# moves stepper motor in a continuous rotation in a specific direction 
    # velocity can be changed during motor rotation
    # direction = + or - (if omitted, rotation is halted)
	def drive(self, header: str, direction = "+"):
		self.pyvisa.write(header + "D" + direction + "\r")
		return self.pyvisa.read("\r")
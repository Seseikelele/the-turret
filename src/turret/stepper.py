# 21 dir
# 20 step

# Motor 1
# 5 RESET biały
# 6 SLEEP szary
# 13 STEP
# 19 DIR
# Motor 2
# 12 RESET biały
# 16 SLEEP szary
# 20 STEP
# 21 DIR

import json
import socket
from threading import Thread

from gpiozero import DigitalOutputDevice


def create_mapping_function(input_min: int, input_max: int, output_min: int, output_max: int):
	input_span = input_max - input_min
	output_span = output_max - output_min
	scale = output_span / input_span

	def mapper(value):
		if not input_min <= value <= input_max:
			raise ValueError(f"Value must fit between {input_min} and {input_max}")
		return output_min + (value - input_min) * scale

	return mapper

percent_to_on_time = create_mapping_function(0, 100, -0.05, -0.0018)


class Stepper():
	def __init__(self, reset_pin, sleep_pin, step_pin, dir_pin):
		self._reset = DigitalOutputDevice(reset_pin)
		self._reset.on()
		self._sleep = DigitalOutputDevice(sleep_pin)
		self._sleep.on()
		self._step = DigitalOutputDevice(step_pin)
		self._step.off()
		self._dir = DigitalOutputDevice(dir_pin)
		self._dir.off()

	def sleep(self):
		self._sleep.off()

	def wake(self):
		self._sleep.on()

	def steps(self, dir, count):
		self.wake()
		self._dir.value = dir
		self._step.blink(0.0001, 0.0005, count)

	def set(self, dir, speed):
		if not 0 <= speed <= 100:
			print("Received invalid speed value", speed)
			return
		if speed == 0:
			self.stop()
			return
		on_time = abs(percent_to_on_time(speed))
		self.wake()
		self._dir.value = dir
		self._step.blink(on_time, 0.0002)
		print(on_time)

	def stop(self):
		self.wake()
		self._dir.value = 0
		self._step.value = 0

motor_1 = Stepper(5, 6, 13, 19)

class ImageStreamingThread(Thread):
	def __init__(self) -> None:
		super().__init__(name="Image Streaming Thread")
		self.zmq

	def join(self) -> None:
		return super().join()

serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
serversocket.bind(("0.0.0.0", 42000))
serversocket.listen()
print('listening')

min = -32768
max = 32767
mmm = max-min
speed = 0
direction = 0

prev_up = 0
prev_down = 0
prev_cross = 0

while True:
	print('waiting for connection')
	(client, addr) = serversocket.accept()
	print('got connection')
	while payload := client.recv(1024):
		payload = json.loads(payload.decode())

		h_dir = payload['horizontal'] < 0
		h_spd = abs(payload['horizontal'])

		motor_1.set(h_dir, h_spd)

		# if up and up != prev_up:
		# 	speed += 0.005
		# 	print(speed)
		# if down and down != prev_down:
		# 	speed -= 0.005
		# 	if speed < 0:
		# 		speed = 0
		# 	print(speed)
		# if cross and cross != prev_cross:
		# 	direction = not direction
		# 	print("dir:", direction)
		# motor_1.set(direction, speed)

		# prev_up = up
		# prev_down = down
		# prev_cross = cross
	motor_1.sleep()

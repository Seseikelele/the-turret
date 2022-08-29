#!/usr/bin/env python3
import logging
import traceback
import zmq
import gpiozero

ZMQ_INTERFACE = 'tcp://0.0.0.0:42001'
TOKEN = 'dupa'

logging.basicConfig(
	format='[%(asctime)s] %(levelname)s-> %(message)s',
	datefmt='%T',
	level=logging.INFO
)
logger = logging.getLogger(__name__)

def create_mapping_function(input_min: int, input_max: int, output_min: int, output_max: int):
	input_span = input_max - input_min
	output_span = output_max - output_min
	scale = output_span / input_span

	def mapper(value):
		if not input_min <= value <= input_max:
			raise ValueError(f"Value must fit between {input_min} and {input_max}")
		return output_min + (value - input_min) * scale

	return mapper

percent_to_on_time = create_mapping_function(0, 100, -0.1, -0.02)

class StepperMotor():
	def __init__(self, reset_pin, sleep_pin, step_pin, dir_pin):
		self._reset = gpiozero.DigitalOutputDevice(reset_pin)
		self._reset.on()
		self._sleep = gpiozero.DigitalOutputDevice(sleep_pin)
		self._sleep.on()
		self._step = gpiozero.DigitalOutputDevice(step_pin)
		self._step.on()
		self._dir = gpiozero.DigitalOutputDevice(dir_pin)
		self._dir.on()
		self._speed = 0

	def sleep(self):
		self._sleep.off()
		self._reset.off()

	def wake(self):
		self._sleep.on()
		self._reset.on()

	def steps(self, dir, count):
		self.wake()
		self._dir.value = dir
		self._step.blink(0.005, 0.005, count)

	def speed(self, dir, speed):
		if speed == self._speed:
			return
		if not 0 <= speed <= 100:
			logger.warning('Invalid speed value: %d', speed)
			return
		self.wake()
		if 0 <= speed <= 1:
			#avoid floating
			self._dir.value = 0
			self._step.value = 0
			return
		on_time = abs(percent_to_on_time(speed))
		logger.info('ON TIME: %s', on_time)
		self._dir.value = dir
		self._step.blink(on_time, 0.0002)
		self._speed = speed

def main():
	try:
		#horizontal
		motor_yaw = StepperMotor(12, 16, 20, 21)
		motor_yaw.sleep()
		#vertical
		motor_pitch = StepperMotor(5, 6, 13, 19)
		motor_pitch.sleep()
		listen_for_requests(motor_yaw, motor_pitch)
	except:
		logger.error(traceback.format_exc())
	finally:
		motor_yaw.sleep()
		motor_pitch.sleep()

def listen_for_requests(motor_yaw: StepperMotor, motor_pitch: StepperMotor):
	zmq_context = zmq.Context()
	zmq_socket:zmq.Socket = zmq_context.socket(zmq.REP)
	zmq_socket.bind(ZMQ_INTERFACE)
	try:
		process_requests(zmq_socket, motor_yaw, motor_pitch)
	except:
		logger.error('Something went wrong when processing requests: %s', traceback.format_exc())
	zmq_socket.close()
	zmq_context.destroy()

def process_requests(zmq_socket: zmq.Socket, motor_yaw: StepperMotor, motor_pitch: StepperMotor):
	while True:
		request = zmq_socket.recv_json()
		logger.debug(request)
		if not request_is_valid(request):
			zmq_socket.send_string('BAD TOKEN')
			continue
		yaw = request.get('yaw')
		pitch = request.get('pitch')
		sleep = request.get('sleep')
		if sleep:
			motor_yaw.sleep()
			motor_pitch.sleep()
			zmq_socket.send_string('OK')
			continue
		if yaw is not None:
			update_motor(motor_yaw, yaw)
		if pitch is not None:
			update_motor(motor_pitch, pitch)
		zmq_socket.send_string('OK')

def request_is_valid(request: dict):
	token = request.get('token')
	if token != TOKEN:
		logger.warning('Invalid token: ', token)
		return False
	return True

def update_motor(motor: StepperMotor, command):
	if isinstance(command, int):
		motor.speed(0 if command >= 0 else 1, abs(command))
		return
	try:
		steps = int(command)
		motor.steps(0 if steps >= 0 else 1, abs(steps))
	except ValueError:
		logger.warning('Invalid command: %s', command)
		return

if __name__ == '__main__':
	main()

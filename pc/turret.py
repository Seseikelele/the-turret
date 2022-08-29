#!/usr/bin/env python3
import logging
import struct
import time
from copy import copy
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Thread

import cv2
import numpy as np
import zmq

logging.basicConfig(
	format='[%(asctime)s] %(levelname)s-> %(message)s',
	datefmt='%T',
	level=logging.INFO
)
logger = logging.getLogger(__name__)
zmq_context = zmq.Context()

CV_WINDOW_NAME = 'the-turret'
CV_FRAME_WIDTH = 1280
CV_FRAME_HEIGHT = 720
CV_BLUE = (255, 0, 0)
CV_GREEN = (0, 255, 0)
CV_RED = (0, 0, 255)
CV_PINK = (255, 0, 255)
ZMQ_INTERFACE_FRAMES = 'tcp://192.168.42.199:42000'
ZMQ_INTERFACE_STEERING = 'tcp://192.168.42.199:42001'
EVENT_TYPE_BUTTON = 1
EVENT_TYPE_AXIS = 2
BUTTON_CODE = {
	0: "btn_cross",
	1: "btn_circle",
	2: "btn_triangle",
	3: "btn_square",
	4: "btn_L1",
	5: "btn_R1",
	6: "btn_L2",
	7: "btn_R2",
	8: "btn_select",
	9: "btn_start",
	10: "btn_ps",
	11: "btn_analog_left",
	12: "btn_analog_right",
	13: "btn_dpad_up",
	14: "btn_dpad_down",
	15: "btn_dpad_left",
	16: "btn_dpad_right"
}
AXIS_CODE = {
	0: "left_x",
	1: "left_y",
	2: "left_trigger",
	3: "right_x",
	4: "right_y",
	5: "right_trigger"
}

@dataclass()
class Controller():
	last_update:int = 0

	# axes
	left_x:int = 0				# 0
	left_y:int = 0				# 1
	left_trigger:int = 0		# 2

	right_x:int = 0				# 3
	right_y:int = 0				# 4
	right_trigger:int = 0		# 5

	# buttons
	btn_cross:int = 0
	btn_circle:int = 0
	btn_triangle:int = 0
	btn_square:int = 0
	btn_L1:int = 0
	btn_R1:int = 0
	btn_L2:int = 0
	btn_R2:int = 0
	btn_select:int = 0
	btn_start:int = 0
	btn_ps:int = 0
	btn_analog_left:int = 0
	btn_analog_right:int = 0
	btn_dpad_up:int = 0
	btn_dpad_down:int = 0
	btn_dpad_left:int = 0
	btn_dpad_right:int = 0

	def push(self, timestamp, type_, code, value):
		self.last_update = timestamp
		if type_ == 1:
			setattr(self, BUTTON_CODE[code], value)
		elif type_ == 2:
			setattr(self, AXIS_CODE[code], value)

@dataclass()
class Payload():
	yaw: int = 0 # int for setting speed, str for step count
	pitch: int = 0 # as above
	sleep: bool = 0 # emergency shutdown

class ControllerThread(Thread):
	INPUTS = Path('/dev/input/')
	EVENT_STRUCT = 'IhBB'
	EVENT_STRUCT_SIZE = struct.calcsize(EVENT_STRUCT)

	def __init__(self):
		super().__init__(name="Controller Thread")
		self.keep_running = True
		self.state = Controller()

	def run(self) -> None:
		try:
			self._run()
		except KeyboardInterrupt:
			return

	def _run(self) -> None:
		while self.keep_running:
			joystick = None
			try:
				joystick = next(self.INPUTS.glob("js*"))
			except StopIteration:
				time.sleep(1)
				continue
			with open(joystick, 'rb') as file:
				try:
					event = file.read(self.EVENT_STRUCT_SIZE)
					while event and self.keep_running:
						timestamp, value, type_, code = struct.unpack(self.EVENT_STRUCT, event)
						type_ &= 0xF # ignore EVENT_INIT bit
						self.state.push(timestamp, type_, code, value)
						time.sleep(0.01)
						event = file.read(self.EVENT_STRUCT_SIZE)
				except OSError as e:
					if e.errno != 19:
						raise
					print("DISCONNECTED")
					continue

	def quit(self) -> None:
		self.keep_running = False

class TrackingThread(Thread):
	class TRACKER_STATE(Enum):
		WAITING = 0
		INITIALIZING = 1
		TRACKING = 2

	def __init__(self, controller_state: Controller):
		super().__init__(name="Tracking Thread")
		self.keep_running = True
		self.controller_state = controller_state
		self.delta_x = 0
		self.delta_y = 0

	def run(self) -> None:
		try:
			self._run()
		except KeyboardInterrupt:
			return

	def _run(self) -> None:
		zmq_socket:zmq.Socket = zmq_context.socket(zmq.REQ)
		zmq_socket.connect(ZMQ_INTERFACE_FRAMES)

		cv2.namedWindow(CV_WINDOW_NAME)
		cv2.setWindowProperty(CV_WINDOW_NAME, cv2.WND_PROP_AUTOSIZE, cv2.WINDOW_AUTOSIZE)
		tracker = cv2.TrackerCSRT_create()
		tracker_state = self.TRACKER_STATE.WAITING
		xhair = (100, 100)
		while self.keep_running:
			if self.controller_state.btn_cross:
				tracker_state = self.TRACKER_STATE.INITIALIZING
				self.delta_x = 0
				self.delta_y = 0
				continue
			if self.controller_state.btn_square:
				tracker_state = self.TRACKER_STATE.WAITING
				self.delta_x = 0
				self.delta_y = 0
				continue
			# - GET A FRAME TO WORK ON
			zmq_socket.send_json(dict(
				token='dupa',
				request_string='send me a frame, please'
			))
			frame = self._recv_frame(zmq_socket)
			frame = cv2.resize(frame, (CV_FRAME_WIDTH, CV_FRAME_HEIGHT))
			# - CROSSHAIR WHERE?
			xhair_top_left, xhair_bottom_right = self._get_xhair_rect(xhair)

			# - UPDATE TRACKING
			if tracker_state == self.TRACKER_STATE.TRACKING:
				ret, bbox = tracker.update(frame)
				if not ret:
					logger.info('Target lost')
					tracker_state = self.TRACKER_STATE.WAITING
					self.delta_x = 0
					self.delta_y = 0
					continue
				target_top_left = bbox[:2]
				target_bottom_right = (bbox[0] + bbox[2], bbox[1] + bbox[3])
				cv2.rectangle(frame, target_top_left, target_bottom_right, CV_RED, 2)

				vec_x_0 = CV_FRAME_WIDTH // 2
				vec_y_0 = CV_FRAME_HEIGHT // 2
				vec_x_1 = bbox[0] + bbox[2] // 2
				vec_y_1 = bbox[1] + bbox[3] // 2
				self.delta_x = vec_x_0 - vec_x_1
				if abs(self.delta_x) < 0.01*CV_FRAME_WIDTH:
					self.delta_x = 0
				self.delta_y = vec_y_0 - vec_y_1
				if abs(self.delta_y) < 0.05*CV_FRAME_HEIGHT:
					self.delta_y = 0
				cv2.arrowedLine(frame, (vec_x_0, vec_y_0), (vec_x_1, vec_y_0), CV_PINK, 1)
				cv2.arrowedLine(frame, (vec_x_0, vec_y_0), (vec_x_0, vec_y_1), CV_PINK, 1)
			elif tracker_state == self.TRACKER_STATE.INITIALIZING:
				tracker.init(frame, (*xhair_top_left, *xhair))
				tracker_state = self.TRACKER_STATE.TRACKING

			# - DRAW CROSSHAIR
			cv2.rectangle(frame, xhair_top_left, xhair_bottom_right, CV_PINK, 2)
			# - DISPLAY FRAME
			cv2.imshow(CV_WINDOW_NAME, frame)
			cv2.waitKey(1)
		cv2.destroyAllWindows()

	def _recv_frame(self, zmq_socket:zmq.Socket) -> np.ndarray:
		metadata = zmq_socket.recv_json()
		message = zmq_socket.recv(0, copy=True, track=False)
		buffer = memoryview(message)
		np_array = np.frombuffer(buffer, dtype=metadata['dtype'])
		return np_array.reshape(metadata['shape'])

	def _get_xhair_rect(self, xhair) -> tuple:
		return (
			(
				(CV_FRAME_WIDTH - xhair[0]) // 2,
				(CV_FRAME_HEIGHT - xhair[1]) // 2
			),
			(
				(CV_FRAME_WIDTH + xhair[0]) // 2,
				(CV_FRAME_HEIGHT + xhair[1]) // 2
			)
		)

	def quit(self) -> None:
		self.keep_running = False

def create_mapping_function(input_min: int, input_max: int, output_min: int, output_max: int):
	input_span = input_max - input_min
	output_span = output_max - output_min
	scale = output_span / input_span

	def mapper(value):
		if value < input_min:
			value = input_min
		elif input_max < value:
			value = input_max
		return output_min + (value - input_min) * scale

	return mapper

analog_to_percentage = create_mapping_function(-32768, 32767, -100, 100)
delta_y_to_percentage = create_mapping_function(-CV_FRAME_HEIGHT//2, CV_FRAME_HEIGHT//2, -100, 100)
delta_x_to_percentage = create_mapping_function(-CV_FRAME_WIDTH//2, CV_FRAME_WIDTH//2, -100, 100)

def main():
	try:
		controller = ControllerThread()
		controller.start()
		tracking = TrackingThread(controller.state)
		tracking.start()

		zmq_socket:zmq.Socket = zmq_context.socket(zmq.REQ)
		zmq_socket.connect(ZMQ_INTERFACE_STEERING)

		controller_state = controller.state
		sleep = 0
		last_controller_state = None
		while sleep == 0:
			if last_controller_state and not last_controller_state.btn_circle and controller_state.btn_circle:
				sleep = 0 if sleep else 1

			horizontal = round(delta_x_to_percentage(tracking.delta_x*4))
			if controller_state.left_x:
				horizontal = round(analog_to_percentage(controller_state.left_x))

			vertical = round(delta_y_to_percentage(-tracking.delta_y))
			if controller_state.left_y:
				vertical = round(analog_to_percentage(controller_state.left_y))
			payload = dict(
				token='dupa',
				yaw=horizontal,
				pitch=vertical,
				sleep=sleep
			)
			print(payload)
			last_controller_state = copy(controller_state)
			zmq_socket.send_json(payload)
			print(zmq_socket.recv_string())
			time.sleep(0.01)
	except KeyboardInterrupt:
		pass
	finally:
		print("Quitting.")
		controller.quit()
		controller.join()

if __name__ == "__main__":
	main()

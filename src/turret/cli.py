import logging
import traceback
from enum import Enum

import click
import cv2
import numpy as np
import zmq
from PIL import Image, ImageDraw, ImageFont
from ulid import ULID

from turret.common import Controls
from turret.communication import TurretClient, TurretServer
from turret.config import CROSSHAIR_RESIZE_STEP, WINDOW_NAME, Button
from turret.exceptions import VideoCaptureError

logging.basicConfig(
	format='[%(asctime)s] %(levelname)s-> %(message)s',
	datefmt='%T'#'%H:%M:%S:',
)
logger = logging.getLogger()



class TRACKER_STATE(Enum):
	WAITING = 0
	INITIALIZING = 1
	TRACKING = 2


class VideoCapture():
	def __init__(self, device_id: int=0) -> None:
		self.cap = cv2.VideoCapture(device_id)
		# self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
		# self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
		# self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
		# self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
		self.cap.set(cv2.CAP_PROP_FPS, 30)
		self.fps = self.cap.get(cv2.CAP_PROP_FPS)
		self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
		self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
		logger.debug('Initiated capture device %dx%d@%dfps', self.width, self.height, self.fps)

	def is_valid(self):
		return self.cap.isOpened()

	def get_frame_dimensions(self):
		return (self.width, self.height)

	def read(self):
		return self.cap.read()

	def close(self):
		self.cap.release()

class Turret():
	def __init__(self, comm: TurretClient, debug: bool=False) -> None:
		logger.info('Initiating turret%s', ' in debug mode' if debug else '')
		self.debug = debug
		self.running = True
		self.comm = comm
		self.tracker = cv2.TrackerCSRT_create()
		self.tracker_state = TRACKER_STATE.WAITING
		self.xhair_width = 100
		self.xhair_height = 100

	def run(self):
		try:
			cv2.namedWindow(WINDOW_NAME)
			cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_AUTOSIZE, cv2.WINDOW_AUTOSIZE)
			while self.running:
				controls = self._process_keys()
				self.comm.send_input(controls)
				frame = self.comm.recv_frame()
				self._process_frame(frame)
				frame = cv2.resize(frame, (1280, 720))
				font = ImageFont.truetype("resources/fonts/roboto.ttf", 16)
				image = Image.fromarray(frame)
				draw = ImageDraw.Draw(image)
				draw.text((10, 10), "This is just a test", (255, 0, 0), font)
				frame = np.array(image)
				cv2.imshow(WINDOW_NAME, frame)
				if controls.screenshot:
					filename = f'{ULID()}.jpg'
					cv2.imwrite(filename, frame)
					logger.info('Saved screenshot as %s', filename)
		except KeyboardInterrupt:
			logger.info('Stopping Turret')
		finally:
			pass
			cv2.destroyAllWindows()

	def _process_frame(self, frame):
		top_left = ((self.comm.dimensions[0] - self.xhair_width) // 2, (self.comm.dimensions[1] - self.xhair_height) // 2)
		bottom_right = ((self.comm.dimensions[0] + self.xhair_width) // 2, (self.comm.dimensions[1] + self.xhair_height) // 2)
		cv2.rectangle(frame, top_left, bottom_right, (255, 0, 255), 2)

		if self.tracker_state == TRACKER_STATE.TRACKING:
			ret, bbox = self.tracker.update(frame)
			if not ret:
				logger.debug('Target lost')
				self.tracker_state = TRACKER_STATE.WAITING
				return
			tl = bbox[:2]
			br = (bbox[0] + bbox[2], bbox[1] + bbox[3])
			cv2.rectangle(frame, tl, br, (255, 0, 0), 2)

			vector_x_0 = self.comm.dimensions[0] // 2
			vector_y_0 = self.comm.dimensions[1] // 2
			cap_center = (vector_x_0, vector_y_0)
			vector_x_1 = bbox[0] + bbox[2] // 2
			vector_y_1 = bbox[1] + bbox[3] // 2
			track_center = (vector_x_1, vector_y_1)
			logger.debug('X: %d   Y: %d', vector_x_0 - vector_x_1, vector_y_0 - vector_y_1)
			cv2.arrowedLine(frame, cap_center, track_center, (255, 0, 0), 2)

		elif self.tracker_state == TRACKER_STATE.INITIALIZING:
			self.tracker.init(frame, (*top_left, self.xhair_width, self.xhair_height))
			self.tracker_state = TRACKER_STATE.TRACKING

	def _process_keys(self):
		controls = get_input()
		self.running = controls.client_running
		if controls.init_tracker:
			self.tracker_state = TRACKER_STATE.INITIALIZING
		elif controls.init_tracker is not None:
			self.tracker_state = TRACKER_STATE.WAITING
		self.xhair_height += controls.dy
		self.xhair_width += controls.dx
		return controls


def get_input() -> Controls:
	controls = Controls()
	key = cv2.waitKeyEx(1)
	if key != -1:
		logger.debug('Key pressed (code=%d), (repr=%s)', key, chr(key))
	if key == ord('q'):
		controls.client_running = False
	elif key == ord('x'):
		controls.client_running = False
		controls.server_running = False
	elif key == ord('e'):
		controls.init_tracker = True
	elif key == ord('r'):
		controls.init_tracker = False
	elif key == ord(' '):
		controls.screenshot = True
	elif key in [ord('w'), Button.ARROW_UP]:
		controls.dy += CROSSHAIR_RESIZE_STEP
	elif key in [ord('s'), Button.ARROW_DOWN]:
		controls.dy -= CROSSHAIR_RESIZE_STEP
	elif key in [ord('a'), Button.ARROW_LEFT]:
		controls.dx -= CROSSHAIR_RESIZE_STEP
	elif key in [ord('d'), Button.ARROW_RIGHT]:
		controls.dx += CROSSHAIR_RESIZE_STEP
	if controls != Controls():
		logger.debug('Got input %s', controls)
	return controls


@click.group()
def cli():
	pass

@cli.command()
@click.option('--debug', is_flag=True)
@click.option('-h', '--host', type=str, default='0.0.0.0')
@click.option('-p', '--port', type=int, default=42999)
@click.option('-d', '--device', type=int, default=0)
def server(debug: bool, host: str, port: int, device: int):
	if debug:
		logger.setLevel(logging.DEBUG)
		logger.debug('Debug logging enabled')

	try:
		cap = VideoCapture(device)

		context = zmq.Context()
		socket = context.socket(zmq.REP)
		interface = f'tcp://{host}:{port}'
		socket.bind(interface)
		logger.info('Server bound to interface %s', interface)
		server = TurretServer(socket)
		running = True
		while running:
			msg = server.recv_input()
			running = msg.server_running

			ret, frame = cap.read()
			if not ret:
				raise VideoCaptureError('Failed to read a frame of video')
			server.send_frame(frame)
	except KeyboardInterrupt:
		logger.info('Stopping server')
	except Exception:
		logger.error('Unknown error occured')
		logger.error(traceback.format_exc())
	finally:
		socket.close()
		logger.info('Socket closed')
		context.destroy()
		logger.info('0MQ context destroyed')

@cli.command()
@click.argument('server_address')
@click.argument('server_port')
def client(server_address: str, server_port: int):
	logger.setLevel(logging.DEBUG)
	logger.info('Creating 0MQ context')
	context = zmq.Context()
	logger.info('Constructing socket')
	socket = context.socket(zmq.REQ)
	socket.connect(f'tcp://{server_address}:{server_port}')
	client = TurretClient(socket)

	logger.info('CLIENT')
	try:
		turret = Turret(client)
		turret.run()
	except Exception:
		logger.error('Unknown error occured')
		logger.error(traceback.format_exc())
	finally:
		socket.close()
		logger.info('Socket closed')
		context.destroy()
		logger.info('0MQ context destroyed')
		cv2.destroyAllWindows()
		logger.info('CV2 windows destroyed')



if __name__ == '__main__':
	cli()

import logging
from enum import Enum

import click
import cv2

from turret.config import WINDOW_NAME, Button
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
		super().__init__()
		self.cap = cv2.VideoCapture(device_id)
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
	CROSSHAIR_RESIZE_STEP = 10

	def __init__(self, frame_source: VideoCapture, debug: bool=False) -> None:
		logger.info('Initiating turret%s', ' in debug mode' if debug else '')
		self.debug = debug
		self.running = True
		self.cap = frame_source
		self.tracker = cv2.TrackerCSRT_create()
		self.tracker_state = TRACKER_STATE.WAITING
		self.xhair_width = 100
		self.xhair_height = 100

	def run(self):
		self._setup()
		while self.running:
			if self.debug:
				self._process_keys()
			ret, frame = self.cap.read()
			if not ret:
				raise VideoCaptureError('Failed to read a frame of video')
			self._process_frame(frame)
		self._teardown()


	def _setup(self):
		if self.debug:
			cv2.namedWindow(WINDOW_NAME)
			cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_AUTOSIZE, cv2.WINDOW_AUTOSIZE)
		if not self.cap.is_valid(): # wrap with a class
			raise VideoCaptureError('OpenCV could not open video capture')

	def _process_frame(self, frame):
		if self.debug:
			self._process_keys()

		top_left = ((self.cap.width - self.xhair_width) // 2, (self.cap.height - self.xhair_height) // 2)
		bottom_right = ((self.cap.width + self.xhair_width) // 2, (self.cap.height + self.xhair_height) // 2)
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

			vector_x_0 = self.cap.width // 2
			vector_y_0 = self.cap.height // 2
			cap_center = (vector_x_0, vector_y_0)
			vector_x_1 = bbox[0] + bbox[2] // 2
			vector_y_1 = bbox[1] + bbox[3] // 2
			track_center = (vector_x_1, vector_y_1)
			logger.debug('X: %d   Y: %d', vector_x_0 - vector_x_1, vector_y_0 - vector_y_1)
			cv2.arrowedLine(frame, cap_center, track_center, (255, 0, 0), 2)

		elif self.tracker_state == TRACKER_STATE.INITIALIZING:
			self.tracker.init(frame, (*top_left, self.xhair_width, self.xhair_height))
			self.tracker_state = TRACKER_STATE.TRACKING

		cv2.imshow(WINDOW_NAME, frame)

	def _teardown(self):
		if self.debug:
			cv2.destroyAllWindows()
		self.cap.close()

	def _process_keys(self):
		key = cv2.waitKeyEx(1)
		if key != -1:
			logger.debug('Key pressed (code=%d)', key)

		if key == ord('q'):
			self.running = False
		elif key == ord('e'):
			self.tracker_state = TRACKER_STATE.INITIALIZING
		elif key == Button.ARROW_UP:
			self.xhair_height += self.CROSSHAIR_RESIZE_STEP
		elif key == Button.ARROW_DOWN:
			self.xhair_height -= self.CROSSHAIR_RESIZE_STEP
		elif key == Button.ARROW_LEFT:
			self.xhair_width -= self.CROSSHAIR_RESIZE_STEP
		elif key == Button.ARROW_RIGHT:
			self.xhair_width += self.CROSSHAIR_RESIZE_STEP


@click.command()
@click.option('--debug', is_flag=True)
def cli(debug: bool):
	if debug:
		logger.setLevel(logging.DEBUG)
		logger.debug('Debug logging enabled')

	cap = VideoCapture()
	turret = Turret(cap, debug)
	turret.run()


if __name__ == '__main__':
	cli()

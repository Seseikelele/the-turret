#!/usr/bin/env python3
import logging
import traceback

import cv2
import zmq

ZMQ_INTERFACE = 'tcp://0.0.0.0:42000'
TOKEN = 'dupa'
MAGIC_WORD = 'send me a frame, please'

logging.basicConfig(
	format='[%(asctime)s] %(levelname)s-> %(message)s',
	datefmt='%T',
	level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
	try:
		listen_for_requests()
	except Exception as e:
		logger.error(e)

def listen_for_requests():
	zmq_context = zmq.Context()
	zmq_socket:zmq.Socket = zmq_context.socket(zmq.REP)
	zmq_socket.bind(ZMQ_INTERFACE)
	cv2_capture = cv2.VideoCapture(0)
	cv2_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
	cv2_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
	cv2_capture.set(cv2.CAP_PROP_FPS, 60)
	print_capture_info(cv2_capture)
	try:
		process_requests(zmq_socket, cv2_capture)
	except:
		logger.error('Something went wrong when processing requests: %s', traceback.format_exc())
	cv2_capture.release()
	zmq_socket.close()
	zmq_context.destroy()

def print_capture_info(capture: cv2.VideoCapture):
	fps = capture.get(cv2.CAP_PROP_FPS)
	width = capture.get(cv2.CAP_PROP_FRAME_WIDTH)
	height = capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
	logger.info('Capture device initialized: %dx%d@%dfps', width, height, fps)

def process_requests(zmq_socket: zmq.Socket, cv2_capture: cv2.VideoCapture):
	while True:
		request = zmq_socket.recv_json()
		if not request_is_valid(request):
			continue
		ret, frame = cv2_capture.read()
		if not ret:
			raise Exception('Failed to read frame of video')
		metadata = dict(
			dtype=str(frame.dtype),
			shape=frame.shape
		)
		zmq_socket.send_json(metadata, flags=zmq.SNDMORE)
		zmq_socket.send(frame, flags=0, copy=True, track=False)

def request_is_valid(request: dict):
	token = request.get('token')
	if token != TOKEN:
		logger.warning('Invalid token: ', token)
		return False
	request_string = request.get('request_string')
	if request_string != MAGIC_WORD:
		logger.warning('Invalid request: ', request_string)
		return False
	return True

if __name__ == '__main__':
	main()

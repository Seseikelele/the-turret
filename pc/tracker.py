#!/usr/bin/env python3
import cv2
import numpy as np
import zmq

WINDOW_NAME = 'the-turret'
ZMQ_INTERFACE = 'tcp://192.168.42.199:42999'

def recv_frame(socket: zmq.Socket, flags = 0, copy=True, track=False):
	metadata = socket.recv_json(flags)
	payload = socket.recv(flags, copy, track)
	buffer = memoryview(payload)
	np_array = np.frombuffer(buffer, dtype=metadata['dtype'])
	return np_array.reshape(metadata['shape'])

def main():
	context = zmq.Context()
	socket = context.socket(zmq.REQ)
	socket.connect(ZMQ_INTERFACE)

	cv2.namedWindow(WINDOW_NAME)
	cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_AUTOSIZE, cv2.WINDOW_AUTOSIZE)
	while True:
		socket.send_json({})


if __name__ == '__main__':
	main()
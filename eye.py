#!/usr/bin/env python3
import io
import struct

import cv2
import zmq

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://0.0.0.0:42000")

cv2.namedWindow('SRV')
cv2.setWindowProperty('SRV', cv2.WND_PROP_AUTOSIZE, cv2.WINDOW_AUTOSIZE)
try:
	while True:
		message = socket.recv_pyobj()
		socket.send_string('OK')
		print(type(message), message.ndim, message.shape)
		cv2.imshow('SRV', message)
		cv2.waitKey(1)
		cv2.imwrite('test.jpg', message)
finally:
	socket.close()
	cv2.destroyAllWindows()

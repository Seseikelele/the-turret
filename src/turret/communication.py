from dataclasses import asdict

import numpy as np
import zmq

from turret.common import Controls

# https://pyzmq.readthedocs.io/en/latest/howto/serialization.html

class TurretServer():
	def __init__(self, zmq_socket: zmq.Socket) -> None:
		self.socket = zmq_socket

	def send_frame(self, np_array: np.ndarray, flags=0, copy=True, track=False):
		metadata = dict(
			dtype=str(np_array.dtype),
			shape=np_array.shape
		)
		self.socket.send_json(metadata, flags | zmq.SNDMORE)
		return self.socket.send(np_array, flags, copy, track)

	def recv_input(self) -> Controls:
		return Controls(**self.socket.recv_json())

class TurretClient():
	def __init__(self, zmq_socket: zmq.Socket) -> None:
		self.socket = zmq_socket
		self.dimensions = None

	def recv_frame(self, flags=0, copy=True, track=False):
		metadata = self.socket.recv_json(flags)
		if not self.dimensions: # Let's assume it's const
			h, w, _ = metadata['shape']
			self.dimensions = (w, h)
		message = self.socket.recv(flags, copy, track)
		buffer = memoryview(message)
		np_array = np.frombuffer(buffer, dtype=metadata['dtype'])
		return np_array.reshape(metadata['shape'])

	def send_input(self, controls: Controls) -> None:
		self.socket.send_json(asdict(controls))

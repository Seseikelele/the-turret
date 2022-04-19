import numpy as np
import zmq

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
		# - Option 1: send as np array and process np_array->pillow_image->np_array
		# - Option 2: send as pickled pillow image cause time and why not
		return self.socket.send(np_array, flags, copy, track)

	def send_image(self):
		pass # TODO implement Option 2

	def recv_input(self):
		return self.socket.recv_json()

class TurretClient():
	def __init__(self, zmq_socket: zmq.Socket) -> None:
		self.socket = zmq_socket

	def recv_frame(self, np_array: np.ndarray, flags=0, copy=True, track=False):
		metadata = self.socket.recv_json(flags)
		message = self.socket.recv(flags, copy, track)
		buffer = memoryview(message)
		np_array = np.frombuffer(buffer, dtype=metadata['dtype'])
		return np_array.reshape(metadata['shape'])

	def recv_image(self):
		pass # TODO Option 2

	def send_input(self, data: dict):
		return self.socket.send_json(data)

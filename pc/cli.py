#!/usr/bin/env python3
from traceback import print_exc

import zmq

ZMQ_INTERFACE = 'tcp://192.168.42.199:42001'
COMMANDS = ['steps', 'speed', 'sleep']
MOTORS = ['yaw', 'pitch']

def main():
	try:
		zmq_context = zmq.Context()
		zmq_socket:zmq.Socket = zmq_context.socket(zmq.REQ)
		zmq_socket.connect(ZMQ_INTERFACE)
		while True:
			try:
				handle_input(zmq_socket)
			except Exception as e:
				if isinstance(e, KeyboardInterrupt):
					raise
				print_exc()
	except KeyboardInterrupt:
		return

def handle_input(zmq_socket: zmq.Socket):
	command = input()
	command, *args = command.split()
	if command not in COMMANDS:
		print('Allowed commands:', ','.join(COMMANDS))
		return
	motor = None
	value = None
	try:
		motor = args.pop(0)
		if motor not in MOTORS:
			print('Allowed motors:', ','.join(MOTORS))
			return
		value = int(args.pop(0))
		if command == 'steps':
			value = str(value)
	except IndexError:
		pass
	payload = {
		'token': 'dupa',
		'yaw': value if motor == 'yaw' else 0,
		'pitch': value if motor == 'pitch' else 0,
		'sleep': 1 if command == 'sleep' else 0
	}
	print(payload)
	zmq_socket.send_json(payload)
	print(zmq_socket.recv_string())


if __name__ == '__main__':
	main()
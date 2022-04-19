from dataclasses import dataclass
from typing import Optional


@dataclass()
class Controls():
	client_running: bool=True
	server_running: bool=True
	init_tracker: Optional[bool]=None
	dy: int=0
	dx: int=0
	screenshot: bool=False
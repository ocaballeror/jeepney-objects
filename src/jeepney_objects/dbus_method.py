from typing import Callable
from dataclasses import dataclass


@dataclass
class DBusMethod:
    name: str
    method: Callable

from dataclasses import dataclass


@dataclass
class DBusProperty:
    name: str
    signature: str
    value: tuple
    access: str = 'readwrite'

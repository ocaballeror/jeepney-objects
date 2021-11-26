import inspect
from xml.etree import ElementTree as ET
from typing import Callable
from dataclasses import dataclass


@dataclass
class DBusMethod:
    name: str
    method: Callable

    def to_xml(self):
        root = ET.Element('method', {'name': self.name})
        root.set('name', self.name)

        for arg in inspect.signature(self.method).parameters:
            ET.SubElement(root, 'arg', {'name': arg, 'type': 'v', 'direction': 'in'})
        ET.SubElement(root, 'arg', {'name': 'value', 'type': 'v', 'direction': 'out'})

        return root

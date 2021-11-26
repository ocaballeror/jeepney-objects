from dataclasses import dataclass
from xml.etree import ElementTree as ET


@dataclass
class DBusProperty:
    name: str
    signature: str
    value: tuple
    access: str = 'readwrite'

    def to_xml(self):
        elem = ET.Element('property', {'name': self.name, 'type': self.signature, 'access': self.access})
        return elem

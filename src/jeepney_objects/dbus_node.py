from dataclasses import dataclass, field
from typing import List
from jeepney_objects.dbus_interface import DBusInterface


def introspectable_interface():
    name = "org.freedestkop.DBus.Introspectable"
    methods = {"Instrospect": DBusInterface.introspect}
    properties = {}
    return DBusInterface(name=name, methods=methods, properties=properties)


@dataclass
class DBusNode:
    name: str
    interfaces: List[DBusInterface] = field(default_factory=lambda: [])
    children: List["DBusNode"] = field(default_factory=lambda: [])

    def __post_init__(self):
        self.interfaces.append(introspectable_interface())

    def introspect(self):
        header = """
        <!DOCTYPE node PUBLIC
        "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
        "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
        """

        msg = f"{header}\n<node>"
        for ifa in self.interfaces:
            msg += ifa.introspect() + '\n'

        for child in self.children:
            msg += f'<node name="{child.name}"/>'

        msg += "<node/>"
        return msg

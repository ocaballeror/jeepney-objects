import logging
from dataclasses import dataclass, field
from typing import Dict, List
from xml.etree import ElementTree as ET
from jeepney_objects.dbus_interface import DBusInterface


@dataclass
class DBusNode:
    name: str
    interfaces: Dict[str, DBusInterface] = field(default_factory=lambda: {})
    children: List["DBusNode"] = field(default_factory=lambda: [])

    def __post_init__(self):
        self.interfaces = self.default_interfaces()

    def get_path(self, path, ensure=False):
        """
        Recursively find the child node that corresponds to the given path.

        Arguments:
            path: DBus path, e.g.: /org/freedesktop/DBusInterface
            ensure: Whether to create the node if it doesn't exist.

        Raises:
            KeyError: When the path doesn't exist and ensure is False.
        """
        path = path.strip('/')
        root, _, rest = path.partition('/')
        if not root:
            return self

        for child in self.children:
            if child.name == root:
                return child.get_path(rest, ensure)

        if ensure:
            logging.debug("Creating path %s", root)
            new = DBusNode(root)
            self.children.append(new)
            return new.get_path(rest, ensure)

        raise KeyError("Path doesn't exist")

    def introspectable_interface(self):
        """
        Create a generic DBus introspectable interface that can be attached to
        any path of any object.
        """
        name = "org.freedesktop.DBus.Introspectable"
        interface = DBusInterface(name=name, properties={})
        interface.set_handler("Introspect", self.introspect)

        return interface

    def properties_interface(self):
        name = "org.freedesktop.DBus.Properties"
        interface = DBusInterface(name=name, properties={})
        interface.set_handler("Get", interface.get_property)
        interface.set_handler("GetAll", interface.get_all_properties)
        interface.set_handler("Set", interface.set_property)

        return interface

    def default_interfaces(self):
        ifaces = {}
        for method in [
            self.introspectable_interface,
            self.properties_interface,
        ]:
            interface = method()
            ifaces[interface.name] = interface

        return ifaces

    def has_custom_interfaces(self) -> bool:
        """
        Determine whether this node has any new interfaces apart from the
        default ones required by the DBus protocol.
        """
        default = [
            "org.freedesktop.Application",
            "org.freedesktop.DBus.Introspectable",
            "org.freedesktop.DBus.Peer",
            "org.freedesktop.DBus.Properties",
        ]
        return not set(default).issuperset(self.interfaces)

    def to_xml(self):
        node = ET.Element('node')

        if not self.children or self.has_custom_interfaces():
            for iface in self.interfaces.values():
                node.append(iface.to_xml())

        for child in self.children:
            node.append(ET.Element('node', {'name': child.name}))

        return node

    def introspect(self):
        header = """
        <!DOCTYPE node PUBLIC
        "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
        "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
        """
        msg = header + ET.tostring(self.to_xml()).decode()

        logging.debug("Introspect: %s", msg)
        return 's', (msg,)

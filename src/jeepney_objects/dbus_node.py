from dataclasses import dataclass, field
from typing import Dict, List
from jeepney_objects.dbus_interface import DBusInterface


def introspectable_interface():
    name = "org.freedesktop.DBus.Introspectable"
    methods = {"Introspect": DBusInterface.introspect}
    properties = {}
    return DBusInterface(name=name, methods=methods, properties=properties)


@dataclass
class DBusNode:
    name: str
    interfaces: Dict[str, DBusInterface] = field(default_factory=lambda: {})
    children: List["DBusNode"] = field(default_factory=lambda: [])

    def __post_init__(self):
        intro = introspectable_interface()
        self.interfaces[intro.name] = intro
        self.interfaces[None] = DBusInterface(name=None)

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
            new = DBusNode(path)
            self.children.append(new)
            return new

        raise KeyError("Path doesn't exist")

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

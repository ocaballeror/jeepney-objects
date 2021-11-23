from dataclasses import dataclass
from jeepney_objects.dbus_node import Node


@dataclass
class PathAccessor:
    """
    Helper class to access nested nodes using [] notation.
    """
    root_node: Node

    def __getitem__(self, item):
        return self.get_node(item)

    def get_node(self, path):
        node = self.root_node

        if path == '/':
            return node

        for part in path.lstrip("/").split("/"):
            for child in node.children:
                if child.name == part:
                    node = child
                    break
            else:
                raise KeyError(f"Path {path} not found?")

        return node

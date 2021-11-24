import inspect
import logging
from typing import Callable, Dict, Optional, Tuple
from dataclasses import dataclass, field

from jeepney_objects.dbus_property import DBusProperty


@dataclass
class DBusInterface:
    """
    Represents a DBus interface as a list of methods and properties.
    """
    name: Optional[str]
    methods: Dict[str, Callable] = field(default_factory=lambda: {})
    properties: Dict[Tuple[str, str], DBusProperty] = \
        field(default_factory=lambda: {})

    def introspect(self):
        msg = ""

        for prop in self.properties:
            msg += f'<property name="{prop.name}" type="{prop.signature}" acces="{prop.access}"/>\n'

        for name, impl in self.methods.items():
            msg += f'<method name="{name}">\n'
            for arg in inspect.signature(impl).parameters:
                msg += f'<arg name="{arg}" type="v" direction="in"/>\n'
            msg += '<arg name="value" type="v" direction="out"/>\n'
            msg += '<method/>'

        return msg + '\n'

    def set_handler(self, method_name, handler):
        """
        Create a new method and set a handler for it.
        """
        logging.debug('set_handler name=%s', method_name)
        self.methods[method_name] = handler

    def get_handler(self, method_name):
        """
        Retrieve the handler for a specific method.
        """
        logging.debug('get_handler name=%s', method_name)
        if method_name in self.methods:
            return self.methods[method_name]
        raise KeyError(f"Unregistered method: '{method_name}'")

    def set_property(self, prop_name, signature, value):
        """
        Set the value of an existing property, or create a new one if it
        doesn't already exist.
        """
        logging.debug(
            'set_property name=%s, signature=%s, value=%s',
            prop_name, signature, value
        )
        if prop_name in self.properties:
            prop = self.properties[prop_name]
            if prop.access == 'read':
                raise PermissionError(f"{prop_name}: Property not settable")
            prop.signature = signature
            prop.value = value
        else:
            newprop = DBusProperty(prop_name, signature, value)
            self.properties[prop_name] = newprop

    def get_property(self, prop_name):
        """
        Get the value of a property. Raises a KeyError if it doesn't exist.
        """
        logging.debug('get_property name=%s', prop_name)
        if prop_name not in self.properties:
            err = f"Property '{prop_name}' not registered on this interface"
            raise KeyError(err)

        prop = self.properties[prop_name]
        return prop.signature, prop.value

    def get_all_properties(self):
        """
        Get all properties in this interface.
        """
        logging.debug('get_all_properties')
        props = self.properties
        items = [(k, (v.signature, v.value)) for k, v in props.items()]
        return (items,)

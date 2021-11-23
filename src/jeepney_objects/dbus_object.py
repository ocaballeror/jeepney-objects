"""
Functions to test dbus-related functionality.
"""
import inspect
import logging
from dataclasses import dataclass, field
from multiprocessing import Process
from typing import List, Tuple, Dict, Callable

from jeepney.low_level import HeaderFields
from jeepney.low_level import Message, MessageType
from jeepney.io.blocking import open_dbus_connection
from jeepney.bus_messages import DBus
from jeepney.wrappers import new_error
from jeepney.wrappers import new_method_return


@dataclass
class DBusProperty:
    name: str
    signature: str
    value: Tuple
    access: str = 'readwrite'


@dataclass
class DBusInterface:
    """
    Represents a DBus interface as a list of methods and properties.
    """
    name: str
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
        logging.warning('set_handler name=%s', method_name)
        self.methods[method_name] = handler

    def get_handler(self, method_name):
        """
        Retrieve the handler for a specific method.
        """
        logging.warning('get_handler name=%s', method_name)
        if method_name in self.methods:
            return self.methods[method_name]
        raise KeyError(f"Unregistered method: '{method_name}'")

    def set_property(self, prop_name, signature, value):
        """
        Set the value of an existing property, or create a new one if it
        doesn't already exist.
        """
        logging.warning(
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
        logging.warning('get_property name=%s', prop_name)
        if prop_name not in self.properties:
            err = f"Property '{prop_name}' not registered on this interface"
            raise KeyError(err)

        prop = self.properties[prop_name]
        return prop.signature, prop.value

    def get_all_properties(self):
        """
        Get all properties in this interface.
        """
        logging.warning('get_all_properties')
        props = self.properties
        items = [(k, (v.signature, v.value)) for k, v in props.items()]
        return (items,)


def introspectable_interface():
    name = "org.freedestkop.DBus.Introspectable"
    methods = {"Instrospect": DBusInterface.introspect}
    properties = {}
    return DBusInterface(name=name, methods=methods, properties=properties)


@dataclass
class Node:
    name: str
    interfaces: List[DBusInterface] = field(default_factory=lambda: [])
    children: List["Node"] = field(default_factory=lambda: [])

    def __post_init__(self):
        self.interfaces.append(introspectable_interface())

    def introspect(self):
        header = """
            <!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN" "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
        """

        msg = f"{header}\n<node>"
        for ifa in self.interfaces:
            msg += ifa.introspect() + '\n'

        for child in self.children:
            msg += f'<node name="{child.name}"/>'

        msg += "<node/>"
        return msg


@dataclass
class PathAccessor:
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


class DBusObject:
    """
    Main DBusObject class. Contains a list of DBusInterfaces, which in turn
    have all the methods and properties.

    Also includes the necessary functions to publish the object on the system
    bus, listen for incoming messages and handle property access and method
    calls.
    """

    def __init__(self):
        self.name = None
        self.paths = PathAccessor(Node(''))
        self.listen_process = None
        self.conn = open_dbus_connection(bus='SESSION')
        # unwrap replies by default. this means that we get only get the
        # reply's body from send_and_get_reply instead of the full object
        # including headers. also ensures that a DBusErrorResponse is raised
        # automatically if the response is an error type
        self.conn._unwrap_reply = True

    def new_error(self, parent, body=None, signature=None, error_name='err'):
        """
        Wrapper around jeepney's new_error that sets a valid error name and
        some sensible defaults.

        Body can be an exception class or a simple string instead of a tuple,
        and the signature defaults to 's'.

        >>> msg = self.new_error(reply_to, KeyError('Element not found'))
        >>> msg.header.fields[HeaderFields.error_name]
        'com.example.object.exceptions.TypeError'
        >>> msg.header.fields[HeaderFields.signature]
        's'
        >>> msg.body
        ('response() takes 0 positional arguments but 1 was given',))
        """
        if isinstance(body, Exception):
            error_name = type(body).__name__
            body = body.args[0]
        if '.' not in error_name:
            error_name = f'{self.name}.exceptions.{error_name}'

        if isinstance(body, str):
            body = (body,)
            signature = 's'
        elif body is None:
            body = ()
            signature = None
        return new_error(parent, error_name, signature, body)

    def request_name(self, name):
        """
        Reserve a name on the system bus. Raises a RuntimeError if the name is
        already in use.
        """
        dbus = DBus()
        logging.info('Requesting name %s', name)
        reply = self.conn.send_and_get_reply(dbus.RequestName(name))
        if reply != (1,):
            raise RuntimeError("Couldn't get requested name")
        self.name = name

    def release_name(self):
        """
        Release the reserved name for this object.
        """
        logging.info('Releasing name %s', self.name)
        try:
            self.conn.send_message(DBus().ReleaseName(self.name))
        except OSError:
            # This probably means the name has already been released
            self.name = None
        except Exception as e:
            logging.exception('Error releasing name %s', e)
            raise
        self.name = None

    def _listen(self):
        """
        Continuously listen for new messages to this object.
        """
        logging.info('Starting service %s', self.name)
        while True:
            try:
                msg = self.conn.receive()
                self.handle_msg(msg)
            except Exception as err:
                logging.exception('Error receiving messages %s', err)
                pass

    def listen(self):
        """
        Start the service and make the DBus object available and listening for
        messages.
        """
        self.listen_process = Process(target=self._listen)
        self.listen_process.start()

    def stop(self):
        """
        Stop the service. Release the name for this object and stop listening
        for new messages.
        """
        logging.info('Stopping service %s', self.name)
        if self.name:
            try:
                self.release_name()
            except Exception:
                pass
        if self.listen_process and self.listen_process.is_alive():
            self.listen_process.terminate()

    def set_property(self, path, interface, prop_name, signature, value):
        node = self.paths[path]
        if interface not in node.interfaces:
            logging.warning('New interface at %s', interface)
            node.interfaces[interface] = DBusInterface(interface)
        node.interfaces[interface].set_property(prop_name, signature, value)

    def set_handler(self, path, interface, method_name, method):
        node = self.paths[path]
        if interface not in node.interfaces:
            logging.warning('New interface at %s', interface)
            node.interfaces[interface] = DBusInterface(interface)
        node.interfaces[interface].set_handler(method_name, method)

    def _handle_property_msg(self, msg):
        """
        Handle a property get/set call. Returns a response message if
        applicable.
        """
        hdr = msg.header
        path = hdr.fields[HeaderFields.path]
        method = hdr.fields[HeaderFields.member]
        body = list(msg.body)
        iface_name = body.pop(0)
        iface = self[path].interfaces[iface_name]
        if method == 'Get':
            prop_name = body[0]
            signature, value = iface.get_property(prop_name)
            return new_method_return(msg, signature, value)
        elif method == 'Set':
            prop_name, (signature, value) = body
            iface.set_property(prop_name, signature, value)
        elif method == 'GetAll':
            properties = iface.get_all_properties()
            return new_method_return(msg, 'a{sv}', properties)

    def _handle_method_call(self, msg):
        """
        Handle a method call. Returns the response as a new message.
        """
        hdr = msg.header
        path = hdr.fields[HeaderFields.path]
        method_name = hdr.fields[HeaderFields.member]
        iface_name = hdr.fields.get(HeaderFields.interface, None)

        iface = self[path].interfaces[iface_name]
        method = iface.get_handler(method_name)

        signature, body = method(*msg.body)
        return new_method_return(msg, signature, body)

    def handle_msg(self, msg):
        """
        Main message handler. This function is called whenever the listening
        socket receives a new message.

        It invokes other methods to perform the necessary action and sends a
        response message if applicable.
        """
        logging.warning('Received message %s', msg)
        hdr = msg.header
        if not hdr.message_type == MessageType.method_call:
            return

        try:
            iface = hdr.fields.get(HeaderFields.interface, None)
            if iface == 'org.freedesktop.DBus.Properties':
                response = self._handle_property_msg(msg)
            else:
                response = self._handle_method_call(msg)
        except Exception as error:
            response = self.new_error(msg, error)

        if isinstance(response, Message):
            msg_type = response.header.message_type
            if msg_type in (MessageType.method_return, MessageType.error):
                sender = msg.header.fields[HeaderFields.sender]
                response.header.fields[HeaderFields.destination] = sender
                response.header.fields[HeaderFields.sender] = self.name
                logging.warning('Sending response %s', response)
                self.conn.send_message(response)

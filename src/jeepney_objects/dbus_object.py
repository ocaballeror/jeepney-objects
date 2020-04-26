"""
Functions to test dbus-related functionality.
"""
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from multiprocessing import Process
from typing import Tuple, Dict, Callable

from jeepney.low_level import HeaderFields
from jeepney.low_level import Message, MessageType
from jeepney.integrate.blocking import connect_and_authenticate
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
        self.interfaces = {}
        self.conn = connect_and_authenticate(bus='SESSION')
        self.conn.router.on_unhandled = self.handle_msg
        self.listen_process = None

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
            print('Error releasing name', type(e), e)
            raise
        self.name = None

    def _listen(self):
        """
        Continuously listen for new messages to this object.
        """
        logging.info('Starting service %s', self.name)
        while True:
            try:
                self.conn.recv_messages()
            except Exception:
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
        key = (path, interface)
        if key not in self.interfaces:
            logging.debug('New interface at %s', key)
            self.interfaces[key] = DBusInterface(interface)
        self.interfaces[key].set_property(prop_name, signature, value)

    def set_handler(self, path, interface, method_name, method):
        key = (path, interface)
        if key not in self.interfaces:
            logging.debug('New interface at %s', key)
            self.interfaces[key] = DBusInterface(interface)
        self.interfaces[key].set_handler(method_name, method)

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
        iface = self.interfaces[(path, iface_name)]
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
        iface = hdr.fields.get(HeaderFields.interface, None)

        if iface is not None:
            method = self.interfaces[(path, iface)].get_handler(method_name)
        else:
            for (it_path, iface_name), iface in self.interfaces.items():
                if it_path == path and method_name in iface.methods:
                    method = iface.methods[method_name]
                    break
            else:
                raise KeyError(f"Unregistered method: '{method_name}'")

        args = msg.body
        signature, body = method(*args)
        return new_method_return(msg, signature, body)

    def handle_msg(self, msg):
        """
        Main message handler. This function is called whenever the listening
        socket receives a new message.

        It invokes other methods to perform the necessary action and sends a
        response message if applicable.
        """
        logging.debug('Received message %s', msg)
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
                logging.debug('Sending response %s', response)
                self.conn.send_message(response)

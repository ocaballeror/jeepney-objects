from functools import partial

import pytest
from pytest_cov.embed import cleanup_on_sigterm
from jeepney import DBusAddress
from jeepney.bus_messages import DBus
from jeepney.wrappers import new_method_call
from jeepney.wrappers import Properties
from jeepney.wrappers import DBusErrorResponse
from jeepney.io.blocking import open_dbus_connection

from jeepney_objects import DBusObject
from jeepney_objects import DBusInterface
from jeepney_objects import DBusProperty


@pytest.fixture
def dbus_service():
    cleanup_on_sigterm()
    name = 'com.example.object'
    service = DBusObject()
    try:
        service.request_name(name)
    except RuntimeError:
        pytest.skip("Can't get the requested name")

    try:
        yield service
    finally:
        service.stop()


def connect_and_authenticate():
    conn = open_dbus_connection()
    conn._unwrap_reply = True
    return conn


def test_basic_init(dbus_service):
    """
    Check that we can successfully initialize and register an object.
    """
    assert dbus_service

    conn = connect_and_authenticate()
    msg = DBus().NameHasOwner(dbus_service.name)
    response = conn.send_and_get_reply(msg)
    assert response == (1,)


def test_object_method_call(dbus_service):
    """
    Register and call methods on a dbus object.
    """
    def str_response(body=''):
        return 's', (body, )

    interface = 'com.example.interface1'
    add0 = DBusAddress('/path', dbus_service.name, interface)
    add1 = DBusAddress('/path/subpath', dbus_service.name, interface)

    hello0 = partial(str_response, body='Hello0')
    hello1 = partial(str_response, body='Hello1')

    dbus_service.set_handler(add0.object_path, interface, 'hello0', hello0)
    dbus_service.set_handler(add1.object_path, interface, 'hello1', hello1)

    dbus_service.listen()
    conn = connect_and_authenticate()

    response = conn.send_and_get_reply(new_method_call(add0, 'hello0'))
    assert response == ('Hello0', )
    response = conn.send_and_get_reply(new_method_call(add1, 'hello1'))
    assert response == ('Hello1', )


def test_object_method_call_args(dbus_service):
    """
    Set a method handler that can take arguments and verify that we can call
    it.
    """
    def mirror(arg):
        return ('s', (arg,))

    path = '/path'
    iface = 'inter.face'
    dbus_service.set_handler(path, iface, 'ping', mirror)
    dbus_service.listen()

    addr = DBusAddress(path, dbus_service.name)
    conn = connect_and_authenticate()
    response = conn.send_and_get_reply(
        new_method_call(addr, 'ping', 's', ('Repeat after me',))
    )
    assert response == ('Repeat after me',)


def test_object_wrong_method_call(dbus_service):
    """
    Try to call an inexistent method and verify that an error is returned.
    """
    addr = DBusAddress('/path', dbus_service.name)

    dbus_service.listen()
    conn = connect_and_authenticate()
    with pytest.raises(DBusErrorResponse) as err:
        conn.send_and_get_reply(new_method_call(addr, 'some_method'))
    assert err.value.name == 'com.example.object.exceptions.KeyError'
    assert err.value.data == ("Unregistered method: 'some_method'",)


def test_object_get_property(dbus_service):
    """
    Set and get properties from a dbus object.
    """
    interface = 'com.example.interface1'
    add0 = DBusAddress('/path', dbus_service.name, interface=interface)
    add1 = DBusAddress('/path/subpath', dbus_service.name, interface=interface)

    dbus_service.set_property(add0.object_path, add0.interface,
                              'prop0', 's', ('hello0',))
    dbus_service.set_property(add1.object_path, add1.interface,
                              'prop1', 's', ('hello1',))

    dbus_service.listen()
    conn = connect_and_authenticate()

    response = conn.send_and_get_reply(Properties(add0).get('prop0'))
    assert response == ('hello0', )
    response = conn.send_and_get_reply(Properties(add1).get('prop1'))
    assert response == ('hello1', )


def test_object_get_all_properties(dbus_service):
    """
    Get all properties from a dbus object.
    """
    interface = 'com.example.interface1'
    addr = DBusAddress('/path', dbus_service.name, interface=interface)

    dbus_service.set_property(addr.object_path, addr.interface,
                              'prop0', 's', 'hello0')
    dbus_service.set_property(addr.object_path, addr.interface,
                              'prop1', 's', 'hello1')
    dbus_service.set_property(addr.object_path, addr.interface,
                              'prop2', 's', 'hello2')

    dbus_service.listen()
    conn = connect_and_authenticate()

    response = conn.send_and_get_reply(Properties(addr).get_all())
    assert response == ({'prop0': ('s', 'hello0'),
                         'prop1': ('s', 'hello1'),
                         'prop2': ('s', 'hello2')}, )

def test_object_wrong_property(dbus_service):
    """
    Try to get an inexistent property and verify that an error is returned.
    """
    interface = 'com.example.interface1'
    addr = DBusAddress('/path', dbus_service.name, interface=interface)

    dbus_service.listen()
    conn = connect_and_authenticate()
    with pytest.raises(DBusErrorResponse):
        conn.send_and_get_reply(Properties(addr).get('prop'))


def test_object_set_readonly_property(dbus_service):
    """
    Try to set the value for a readonly property and check that a permissions
    error is returned.
    """
    name = 'someprop'
    value = ('somevalue',)
    path = '/'
    prop = DBusProperty(name, 's', value, access='read')
    interface = DBusInterface('some.interface', properties={name: prop})
    dbus_service.interfaces[(path, interface.name)] = interface
    dbus_service.listen()

    conn = connect_and_authenticate()
    addr = DBusAddress(path, dbus_service.name, interface.name)
    msg = Properties(addr).set(name, 's', 'anothervalue')

    with pytest.raises(DBusErrorResponse) as err:
        conn.send_and_get_reply(msg)
    assert err.value.name == 'com.example.object.exceptions.PermissionError'
    assert err.value.data == (f'{name}: Property not settable',)
    # check that the original property hasn't changed
    assert prop.value == value

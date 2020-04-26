[![Build Status](https://travis-ci.org/ocaballeror/jeepney-objects.svg?branch=master)](https://travis-ci.org/ocaballeror/jeepney-objects)

# Jeepney Objects

Create and publish DBus objects using the
[jeepney](https://gitlab.com/takluyver/jeepney) pure python DBus
implementation.

You don't need to install system development libraries for DBus like
`libdbus-dev`, the only requirement is to have a running DBus daemon.

## Installation
You can install this package using pip

```
pip install jeepney_objects
```

## Usage

This is the "Hello world" of registering a DBus object

```python
from jeepney import DBusAddress
from jeepney_objects import DBusObject

dbobject = DBusObject()
# the name can be anything you want. just make sure it's not being used already
busname = 'com.example.object'
dbobject.request_name(busname)

# create a handler for incoming messages
def response():
    # jeepney messages need explicit types ('s' for string)
    return ('s', ('hello world',))

# create a new method and attach the handler to it
path = '/path/subpath'
dbobject.set_handler(path, method_name='greetme', handler=response)

# start the service
dbobject.listen()

# call the method using jeepney
from jeepney.integrate.blocking import connect_and_authenticate
from jeepney.wrappers import new_method_call
conn = connect_and_authenticate()
msg = new_method_call(DBusAddress(path, busname), 'greetme')
response = conn.send_and_get_reply(msg)
print(response)  # prints: ('hello world',)

# stop the service and release the name
dbobject.stop()
```

The [tests](tests/test_dbusobject.py) are simple enough that you can check them for more examples.

## Contributing
Please do. :D

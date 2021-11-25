import pytest

from jeepney_objects.dbus_node import DBusNode


@pytest.mark.parametrize(
    "path, name",
    [
        ('/', ''),
        ('/com', 'com'),
        ('/com/example', 'example'),
        ('/com/other', 'other'),
    ],
)
def test_get_path(path, name):
    root = DBusNode(
        '',
        children=[
            DBusNode('com', children=[DBusNode('example'), DBusNode('other')]),
            DBusNode('org', children=[DBusNode('example'), DBusNode('other')]),
        ],
    )
    assert root.get_path(path).name == name


def test_ensure_path():
    root = DBusNode('')

    with pytest.raises(KeyError):
        root.get_path('/asdf')

    node = root.get_path('/asdf', ensure=True)
    assert node.name == 'asdf'
    assert root.children == [node]


def test_ensure_nested_path():
    root = DBusNode('')

    node = root.get_path('/nested/path', ensure=True)
    assert node.name == 'path'

    assert len(root.children) == 1
    assert root.children[0].name == 'nested'

    assert len(root.children[0].children) == 1
    assert root.children[0].children[0] == node

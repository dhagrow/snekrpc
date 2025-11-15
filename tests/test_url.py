import pytest

from snekrpc.utils.url import DEFAULT_HOST, DEFAULT_PORT, Url

TEST_HOST = 'testhost'
TEST_PORT = 32123


def test_copy():
    url = 'tcp://{}:{}'.format(TEST_HOST, TEST_PORT)

    u1 = Url(url)
    u2 = Url(u1)

    assert u1 == u2 == url


def test_tcp():
    u = Url('tcp://{}:{}'.format(TEST_HOST, TEST_PORT))

    assert u.scheme == 'tcp'
    assert u.host == TEST_HOST
    assert u.port == TEST_PORT
    assert u.path is None
    assert u.address == (TEST_HOST, TEST_PORT)
    assert u.netloc == '{}:{}'.format(TEST_HOST, TEST_PORT)


def test_http():
    u = Url('http://{}:{}'.format(TEST_HOST, TEST_PORT))

    assert u.scheme == 'http'
    assert u.host == TEST_HOST
    assert u.port == TEST_PORT
    assert u.path is None
    assert u.address == (TEST_HOST, TEST_PORT)
    assert u.netloc == '{}:{}'.format(TEST_HOST, TEST_PORT)


def test_unix_relative():
    path = 'local/path/socket'
    u = Url('unix://{}'.format(path))

    assert u.scheme == 'unix'
    assert u.host is None
    assert u.port is None
    assert u.path == path
    assert u.address == path
    assert u.netloc == path


def test_unix_absolute():
    path = '/root/path/socket'
    u = Url('unix://{}'.format(path))

    assert u.scheme == 'unix'
    assert u.host is None
    assert u.port is None
    assert u.path == path
    assert u.address == path
    assert u.netloc == path


def test_unix_host_only():
    path = 'local'
    u = Url('unix://{}'.format(path))

    assert u.scheme == 'unix'
    assert u.host is None
    assert u.port is None
    assert u.path == path
    assert u.address == path
    assert u.netloc == path


def test_host_only():
    u = Url(TEST_HOST)

    assert u.scheme == 'tcp'
    assert u.host == TEST_HOST
    assert u.port == DEFAULT_PORT
    assert u.path is None
    assert u.address == (TEST_HOST, DEFAULT_PORT)
    assert u.netloc == '{}:{}'.format(TEST_HOST, DEFAULT_PORT)


def test_netloc_only():
    u = Url('{}:{}'.format(TEST_HOST, TEST_PORT))

    assert u.scheme == 'tcp'
    assert u.host == TEST_HOST
    assert u.port == TEST_PORT
    assert u.path is None
    assert u.address == (TEST_HOST, TEST_PORT)
    assert u.netloc == '{}:{}'.format(TEST_HOST, TEST_PORT)


def test_port_only():
    u = Url(':32123')

    assert u.scheme == 'tcp'
    assert u.host == DEFAULT_HOST
    assert u.port == TEST_PORT
    assert u.path is None
    assert u.address == (DEFAULT_HOST, TEST_PORT)
    assert u.netloc == '{}:{}'.format(DEFAULT_HOST, TEST_PORT)


def test_asterisk_only():
    u = Url('*')

    assert u.scheme == 'tcp'
    assert u.host == '0.0.0.0'
    assert u.port == DEFAULT_PORT
    assert u.path is None
    assert u.address == ('0.0.0.0', DEFAULT_PORT)
    assert u.netloc == '{}:{}'.format('0.0.0.0', DEFAULT_PORT)


def test_asterisk():
    u = Url('tcp://*:{}'.format(TEST_PORT))

    assert u.scheme == 'tcp'
    assert u.host == '0.0.0.0'
    assert u.port == TEST_PORT
    assert u.path is None
    assert u.address == ('0.0.0.0', TEST_PORT)
    assert u.netloc == '{}:{}'.format('0.0.0.0', TEST_PORT)


def test_trailing_slash():
    u = Url('{}:{}/'.format(TEST_HOST, TEST_PORT))

    assert u.scheme == 'tcp'
    assert u.host == TEST_HOST
    assert u.port == TEST_PORT
    assert u.path is None
    assert u.address == (TEST_HOST, TEST_PORT)
    assert u.netloc == '{}:{}'.format(TEST_HOST, TEST_PORT)


def test_to_str():
    url = 'tcp://{}:{}'.format(TEST_HOST, TEST_PORT)
    u = Url(url)
    assert url == str(u)

    url = 'unix://local/path/socket'
    u = Url(url)
    assert url == str(u)

    url = 'unix:///root/path/socket'
    u = Url(url)
    assert url == str(u)


def test_invalid():
    with pytest.raises(ValueError):
        Url('xxx:/asdf')
    with pytest.raises(ValueError):
        Url('tcp://asdf/asdf')

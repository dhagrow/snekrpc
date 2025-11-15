import os
import socket
import subprocess
import threading

import pytest

import snekrpc
from snekrpc import utils

SERVICE_NAME = 'test'

PYTHON2 = utils.path.base_path('.venv2/bin/python')
PYTHON3 = utils.path.base_path('.venv3/bin/python')

TRANSPORT_URLS = [
    'tcp://127.0.0.1:7357',
    'unix:///tmp/snekrpc-test.sock',
    'http://127.0.0.1:7357',
]

if os.environ.get('SNEKRPC_TEST_HTTP2'):
    TRANSPORT_URLS.append('http2://127.0.0.1:7357')


class Session(object):
    def __init__(self, interpreter, url, codec):
        self.interpreter = interpreter
        self.url = url
        self.codec = codec
        self.proc: subprocess.Popen[bytes] | None = None

    def get_client(self):
        return snekrpc.Client(self.url, retry_count=2)

    def start_server(self):
        cmd = [
            self.interpreter,
            '-m',
            'snekrpc',
            '-S',
            '-u',
            self.url,
            '-i',
            'tests.service',
            '-s',
            'test',
            '-s',
            'file',
            '-vv',
        ]
        self.proc = subprocess.Popen(cmd)

    def stop_server(self):
        if self.proc:
            self.proc.terminate()


def start_thread(func, *args, **kwargs):
    t = threading.Thread(target=func, args=args, kwargs=kwargs)
    t.daemon = True
    t.start()
    return t


@pytest.fixture(scope='session', autouse=True)
def socket_timeout():
    socket.setdefaulttimeout(5)


@pytest.fixture(scope='session', params=TRANSPORT_URLS)
def url(request):
    return request.param


@pytest.fixture(scope='session', params=['json', 'msgpack'])
def codec(request):
    return request.param


@pytest.fixture(scope='session', params=[PYTHON2, PYTHON3])
def session(request, url, codec):
    s = Session(request.param, url, codec)
    s.start_server()
    yield s
    s.stop_server()


@pytest.fixture
def service(session):
    return session.get_client().service(SERVICE_NAME)

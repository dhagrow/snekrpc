# Client

## API

A server is created by setting a URL to define the transport to use, as well as the host and port to connect to (default: `tcp://127.0.0.1:12321`).

```python
client = snekrpc.Client('tcp://127.0.0.1:12321')
svc = client.service('echo')
print(svc.echo('hello'))
```

By default, the client will initiate a handshake with the server in order to determine which codec to use. This can be skipped by setting the codec directly.

The client will connect on the first attempt to interact with the server. In this case, that is the call to `service()`. `service()` returns a proxy object which can be used to call service methods directly.

As a convenience, services are also accessible as attributes on the `Client` instance, however the `service()` method is required when service names conflict with `Client` method names.

```python
print(client.echo.echo('hello'))
```

Retry behavior:

```python
client = snekrpc.Client(retry_count=3, retry_interval=0.5)
```

## CLI

The `snekrpc` CLI can connect to any server with a supported transport and codec.

```bash
$ snekrpc --url http://127.0.0.1:8000 --codec json echo echo hello
# use default transport and codec
$ snekrpc health ping --count 3
```

Arguments will be defined for every service command argument. Command-line help will also be fully populated.

```sh
$ snekrpc health ping -h
usage: snekrpc health ping [-h] [-c <int>] [-i <float>]

Respond at regular intervals.

options:
  -h, --help            show this help message and exit
  -c, --count <int>     (default: 1)
  -i, --interval <float>
                        (default: 1.0)
```

### Streaming

When a command expects a stream, the CLI accepts a file path or `-` for stdin.

```bash
$ snekrpc file upload ./local.bin remote.bin
$ snekrpc file upload - remote.bin < ./local.bin
```

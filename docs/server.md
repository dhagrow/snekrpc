# Server

## API

A `snekrpc` server hosts a number of services. A service is defined by subclassing `Service` and marking some methods with `command()`. The class argument `name` is optional, but recommended in order to register a definitive name with the `snekrpc` system.

```python
import snekrpc

class EchoService(snekrpc.Service, name='echo'):
    @snekrpc.command()
    def echo(self, value: str) -> str:
        return value
```

A server is created by setting a URL to define the transport to use, as well as the interface and port to bind to (default: `tcp://127.0.0.1:12321`). A codec can also be set for encoding/decoding to/from bytes for transfer over the transport (default: `msgpack`).

Once a `Server` instance has been created, you can add services with the `add_service()` method, which will expose the service using the name set in the class definition.

```python
server = snekrpc.Server('tcp://0.0.0.0:12321', codec='json')
server.add_service(EchoService())
server.serve()
```

Notes:

- The server registers a hidden `_meta` service automatically to provide metadata to clients.
- `add_service()` accepts an `name` argument if you want the service exposed under a different name.
- `Server(remote_tracebacks=True)` will include tracebacks in error responses.

## Command metadata

The clients rely on command metadata to fill in front-end details. Use `param()`
for parameter docs or to hide parameters from display in help output.

```python
class EchoService(snekrpc.Service, name='echo'):
    @snekrpc.command()
    def echo(self, value: str) -> str:
        return value
```

## Streaming

If a command returns a generator, the values yielde d will be streamed to clients. If the first argument (and only the first argument) passed into a command is a generator, values will stream in from the client.

```python
class StreamService(snekrpc.Service, name='stream'):
    @snekrpc.command()
    def echo(self, values: Iterable[str]) -> Iterable[str]:
        yield from values
```

## CLI

A server can also be started directly with the `snekrpc` CLI using the `-S,--server` flag. Services are added using `-s,--service`.

```sh
# bind with the default: tcp://127.0.0.1:12321
$ snekrpc --server --service health --service file
$ snekrpc --server --url unix:///tmp/snekrpc.sock --service health
```

Only `Service` classes which have been registered will be available. There are a few built-in services (use `snekrpc --list services` to see them). Others can be added by module path and optionally given a different name by appending `:<name>`:

```sh
$ snekrpc --server --service echo_service.EchoService:echo
```

You can also import a module directly, in which case the service can be referenced by it's registered name:

```sh
$ snekrpc --server --import echo_service --service echo
```

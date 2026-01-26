# snekrpc

`snekrpc` is a lightweight Python RPC toolkit focused on fast prototyping for microservices and distributed systems. It ships a small core, with pluggable transports and codecs. A client-side Python library and CLI are generated at runtime based on metadata from services.

[🕮 Documentation](https://dhagrow.github.io/snekrpc)

## Features

- Simple service model with metadata and runtime introspection
- Bi-directional streaming
- Built-in transports: TCP, Unix domain sockets, and HTTP (not REST)
- Built-in codecs: JSON and [MessagePack](https://msgpack.org/) (based on [msgspec](https://github.com/jcrist/msgspec))
- Built-in services: `health`, `file`, and `remote` (service pivoting/forwarding)
- Runtime generated client API
- Runtime generated client CLI
- Pre-generated typed client API

## Requirements

- Python 3.11+.

## Installation

```bash
$ pip install snekrpc
```

For development:

```bash
$ git clone https://github.com/dhagrow/snekrpc.git
$ cd snekrpc
$ uv sync
```

## Quick start

### Define a service and start a server

```python
import snekrpc

class EchoService(snekrpc.Service, name='echo'):
    @snekrpc.command()
    def echo(self, value: str) -> str:
        return value

server = snekrpc.Server()
server.add_service(EchoService())
server.serve()
```

The server will bind to `tcp://127.0.0.1:12321`, by default. The client API and CLI will also connect to this, by default.

You can pass in a different address in the same URL format, where the scheme determines the transport to use (e.g. `http://localhost:5000`).

### Call with a client API

```python
import snekrpc

client = snekrpc.Client()
echo_svc = client.service('echo')
print(echo_svc.echo('hello'))
```

### Call with a client CLI

List available services and call a command:

```bash
$ snekrpc
usage: snekrpc [-h] ...
    {echo} ...
# snekrpc <service-name> <command-name> <command-argument>
$ snekrpc echo echo hello
hello
```

## Streaming

If a command accepts or returns an iterable/generator, it is streamed over the transport. Note that streaming to the server is only supported in the first argument of a command.

```python
class FileService(snekrpc.Service, name='file'):
    @snekrpc.command()
    def download(self, path: str) -> Iterable[bytes]:
        with open(path, 'rb') as fp:
            for chunk in iter(lambda: fp.read(8192), b''):
                yield chunk

    @snekrpc.command()
    def upload(self, data: Iterable[bytes], path: str) -> None:
        with open(path, 'wb') as fp:
            for chunk in data:
                fp.write(chunk)
```

On the CLI, streaming arguments accept a file path or `-` for stdin.

## What about `asyncio`?

There is not currently any support provided for `asyncio`. This is primarily due to the fact that I don't personally use `asyncio` in either my personal or professional work. Where I need asynchronous IO, I first reach for [gevent](https://www.gevent.org). However I have found fewer and fewer appropriate use-cases for it over the years.

I'm not opposed to making changes that simplify the integration of `snekrpc` with a project that uses `asyncio`, and will consider any PR to that end. However, I'm not willing to take on the maintenance burden of a feature I don't need or use. Besides, I'd rather be working on the projects this library enables.

See also:
- https://charlesleifer.com/blog/asyncio/

## AI disclosure

I used AI to support some of the documentation for this project. I reviewed all of it and rewrote much of it. I have not yet used AI to write any of the code, though I do have branches I may experiment with.

## Contributing

Issues and pull requests are welcome. Please include tests for behavioral changes and keep the public API backwards compatible where possible.

Source code is available at https://github.com/dhagrow/snekrpc.

## License

MIT

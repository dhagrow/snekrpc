# Services

Services group related RPC commands. A server holds a registry of service instances and
exposes them by name. Commands are normal Python callables decorated with
`@snekrpc.command()`.

## Defining a service

```python
import snekrpc

class MathService(snekrpc.Service, name='math'):
    @snekrpc.command()
    def add(self, a: int, b: int) -> int:
        return a + b

server = snekrpc.Server()
server.add_service(MathService())
server.serve()
```

## Built-in services

### Metadata (`meta` / `_meta`)

The metadata service is automatically registered by the server under the alias `_meta`.
It reports codec/transport information and provides command metadata used by the
client and CLI.

Commands include:

- `status()`
- `service_names()`
- `services()`
- `service(name)`

### Health (`health`)

The health service provides a `ping` generator that yields regularly to keep a
connection alive.

### File (`file`)

The file service exposes basic filesystem operations including `paths`, `upload`, and
`download`. By default, it uses `safe_root=True` to prevent path traversal beyond the
configured `root_path`.

### Remote (`remote`)

The remote service forwards calls to another endpoint by creating a nested client and
exposing it under a new service name.

## Loading services from the CLI

You can add services by name or by import path.

```bash
$ snekrpc --server --service health --service file
$ snekrpc --server --service mypkg.services.CustomService:alias
```

from typing import Any

import snekrpc


class Cache(snekrpc.Service, name='cache'):
    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}

    @snekrpc.command()
    def get(self, key: str) -> Any:
        return self._cache[key]

    @snekrpc.command()
    def put(self, key: str, value: Any) -> None:
        self._cache[key] = value

    @snekrpc.command()
    def clear(self) -> None:
        self._cache.clear()

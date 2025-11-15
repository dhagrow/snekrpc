from typing import Any, Callable, TypeVar
import threading

DEFAULT_URL: str
encoding: Any
format: Any
function: Any
path: Any
retry: Any
url: Any

Func = TypeVar("Func", bound=Callable[..., Any])

def start_thread(func: Func, *args: Any, **kwargs: Any) -> threading.Thread: ...

__all__: list[str]


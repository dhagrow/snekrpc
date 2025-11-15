from __future__ import annotations

import copy
import inspect
import keyword
import re
import tokenize
from collections import OrderedDict
from inspect import Parameter as Param
from inspect import signature
from typing import Any, Callable, cast

from .. import errors
from .encoding import to_unicode

_rx_ident = re.compile(rf'^{tokenize.Name}$')


def is_identifier(value: str) -> bool:
    return bool(_rx_ident.match(value)) and value.isidentifier() and not keyword.iskeyword(value)


def command(**hints: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        cmd_meta: dict[str, Any] = func.__dict__.setdefault('_meta', {})
        params: dict[str, dict[str, Any]] = cmd_meta.setdefault('params', {})
        for name, hint in hints.items():
            hintstr = _hint_to_str(hint)
            if hintstr == 'stream':
                if 'stream' in cmd_meta:
                    raise errors.ParameterError(f'only one stream param is possible: {name}')
                cmd_meta['stream'] = name
            params.setdefault(name, {})['hint'] = hintstr
        return func

    return decorator


def param(
    name: str,
    hint: Any | None = None,
    doc: str | None = None,
    hide: bool = False,
    **metadata: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        cmd_meta: dict[str, Any] = func.__dict__.setdefault('_meta', {})
        params: dict[str, dict[str, Any]] = cmd_meta.setdefault('params', {})
        param_meta = params.setdefault(name, {})

        if hint:
            hintstr = _hint_to_str(hint)
            if hintstr == 'stream':
                if 'stream' in cmd_meta:
                    raise errors.ParameterError(f'only one stream param is possible: {name}')
                cmd_meta['stream'] = name
            param_meta['hint'] = hintstr

        if doc:
            param_meta['doc'] = doc
        if hide:
            param_meta['hide'] = hide
        param_meta.update(metadata)
        return func

    return decorator


def _hint_to_str(hint: Any | None) -> str:
    if hint is None:
        name = 'str'
    elif isinstance(hint, (str, bytes)):
        name = hint
    else:
        name = hint.__name__
        if name == 'unicode':
            name = 'str'
    return to_unicode(name)


def func_to_dict(func: Callable[..., Any], remove_self: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {'name': func.__name__, 'doc': func.__doc__}
    cmd_meta = cast(dict[str, Any], copy.deepcopy(getattr(func, '_meta', {})))
    cmd_params = cmd_meta.pop('params', {})

    sig = signature(func)
    if remove_self:
        parameters = list(sig.parameters.values())[1:]
        sig = sig.replace(parameters=parameters)

    params = data['params'] = []
    for param in sig.parameters.values():
        entry: dict[str, Any] = {'name': param.name, 'kind': int(param.kind)}

        hint = entry.get('hint')
        if param.default is not Param.empty:
            entry['default'] = param.default
            if not hint and param.default is not None:
                entry['hint'] = type(param.default).__name__

        entry.update(cmd_params.pop(param.name, {}))
        params.append(entry)

    for name, meta in cmd_params.items():
        meta['name'] = name
        meta.setdefault('kind', int(Param.KEYWORD_ONLY))
        params.append(meta)

    stream_name = cmd_meta.get('stream')
    if stream_name is not None:
        data['stream'] = stream_name
        del cmd_meta['stream']

    if inspect.isgeneratorfunction(func):
        data['isgen'] = True

    if cmd_meta:
        data['meta'] = cmd_meta
    return data


def dict_to_func(data: dict[str, Any], callback: Callable[..., Any]) -> Callable[..., Any]:
    sig_defn: list[str] = []
    sig_call: list[str] = []

    meta = copy.deepcopy(data)
    params = OrderedDict()

    for param in meta.pop('params'):
        if not is_identifier(param['name']):
            raise ValueError(f'invalid parameter name: {param["name"]}')
        kind = {
            0: Param.POSITIONAL_ONLY,
            1: Param.POSITIONAL_OR_KEYWORD,
            2: Param.VAR_POSITIONAL,
            3: Param.KEYWORD_ONLY,
            4: Param.VAR_KEYWORD,
        }[param['kind']]

        if kind == Param.KEYWORD_ONLY:
            continue
        if kind == Param.VAR_POSITIONAL:
            name = f'*{param["name"]}'
        elif kind == Param.VAR_KEYWORD:
            name = f'**{param["name"]}'
        else:
            name = param['name']

        def_name = name
        if 'default' in param:
            def_name += f'={param["default"]!r}'
        sig_defn.append(def_name)
        sig_call.append(name)

        params[param.pop('name')] = param

    meta['params'] = params

    definition = ', '.join(sig_defn)
    call = ', '.join(sig_call)

    is_generator = meta.pop('isgen', False)
    tpl = (
        'def {}({}):\n  for x in callback({}):\n    yield x'
        if is_generator
        else 'def {}({}):\n  return callback({})'
    )
    src = tpl.format(data['name'], definition, call)

    namespace: dict[str, Any] = {'callback': callback}
    exec(src, namespace)

    func = namespace[meta.pop('name')]
    func.__doc__ = meta.pop('doc', None)
    func.__dict__['_meta'] = meta
    return func


def get_func_name(name: str | None) -> str:
    return to_unicode(name or 'str')

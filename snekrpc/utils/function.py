"""Utilities for describing and reconstructing callable signatures."""

from __future__ import annotations

from inspect import Parameter, Signature, formatannotation, isgeneratorfunction, signature
from typing import Any, Callable, ParamSpec, TypeVar

import msgspec
from makefun import create_function

P = ParamSpec('P')
R = TypeVar('R')


class ParamMeta(msgspec.Struct):
    doc: str | None = None
    hide: bool = False
    metadata: dict[str, Any] = msgspec.field(default_factory=dict)


class CommandMeta(msgspec.Struct):
    stream: str | None = None
    params: dict[str, ParamMeta] = msgspec.field(default_factory=dict)


def command() -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that records metadata about a command function."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        """Add command metadata to `func._meta`"""
        func.__dict__.setdefault('_meta', CommandMeta())
        return func

    return decorator


def param(
    name: str,
    doc: str | None = None,
    hide: bool = False,
    **metadata: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for attaching metadata about a single parameter."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        """Add param metadata to `func._meta`."""
        meta: CommandMeta = func.__dict__.setdefault('_meta', CommandMeta())
        param_meta = meta.params.setdefault(name, ParamMeta())

        if doc:
            param_meta.doc = doc
        if hide:
            param_meta.hide = hide

        param_meta.metadata.update(metadata)

        return func

    return decorator


class ParameterSpec(msgspec.Struct, frozen=True):
    """Description of a single callable parameter."""

    name: str
    doc: str | None
    kind: str
    annotation: str | None
    default: Any | None = None
    has_default: bool = False
    hide: bool = False


class SignatureSpec(msgspec.Struct, frozen=True):
    """Description of a callable signature."""

    name: str
    doc: str | None
    parameters: tuple[ParameterSpec, ...]
    return_annotation: str | None
    is_generator: bool = False


def encode(func: Callable[..., Any], remove_self: bool = False) -> SignatureSpec:
    """Encode the signature of `func` into a serializable `SignatureSpec`.

    If `remove_self` is `True`, remove the first argument.
    """
    sig = signature(func)

    if remove_self:
        parameters = list(sig.parameters.values())[1:]
        sig = sig.replace(parameters=parameters)

    params = []
    for param in sig.parameters.values():
        has_default = param.default is not Parameter.empty
        params.append(
            ParameterSpec(
                param.name,
                None,
                param.kind.name,
                None if param.annotation is Parameter.empty else formatannotation(param.annotation),
                param.default if has_default else None,
                has_default,
            )
        )

    return SignatureSpec(
        func.__name__,
        func.__doc__,
        tuple(params),
        None
        if sig.return_annotation is Signature.empty
        else formatannotation(sig.return_annotation),
        isgeneratorfunction(func),
    )


def decode(spec: SignatureSpec, func: Callable[..., Any]) -> Callable[..., Any]:
    """Recreate a callable from a `SignatureSpec`."""
    if spec.is_generator != isgeneratorfunction(func):
        func_type = 'generator' if spec.is_generator else 'regular'
        raise TypeError(f'expected {func_type} function to decode signature')

    params = []
    for param in spec.parameters:
        params.append(
            Parameter(
                name=param.name,
                kind=getattr(Parameter, param.kind),
                default=param.default if param.has_default else Parameter.empty,
                annotation=param.annotation if param.annotation is not None else Signature.empty,
            )
        )

    return_annotation = (
        spec.return_annotation if spec.return_annotation is not None else Signature.empty
    )
    sig = Signature(parameters=params, return_annotation=return_annotation)
    return create_function(sig, func, func_name=spec.name)

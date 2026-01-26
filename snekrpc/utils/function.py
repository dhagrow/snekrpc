"""Utilities for describing and reconstructing callable signatures."""

from __future__ import annotations

import typing
from inspect import (
    Parameter,
    Signature,
    isgeneratorfunction,
    signature,
)
from inspect import _ParameterKind as ParameterKind
from typing import Any, Callable, ParamSpec, TypeVar, cast

import msgspec
from makefun import create_function

P = ParamSpec('P')
R = TypeVar('R')


class ParamMeta(msgspec.Struct):
    doc: str | None = None
    hide: bool = False


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

        return func

    return decorator


class ParameterSpec(msgspec.Struct, frozen=True):
    """Description of a single callable parameter."""

    name: str
    doc: str | None = None
    kind: ParameterKind = ParameterKind.POSITIONAL_OR_KEYWORD
    annotation: str | None = None
    default: Any | None = None
    has_default: bool = False
    hide: bool = False


class SignatureSpec(msgspec.Struct, frozen=True):
    """Description of a callable signature."""

    name: str
    doc: str | None = None
    parameters: tuple[ParameterSpec, ...] = ()
    return_annotation: str | None = None
    is_generator: bool = False

    def to_signature(self, include_self: bool = False) -> Signature:
        params = []

        if include_self:
            params.append(Parameter('self', ParameterKind.POSITIONAL_OR_KEYWORD))

        for param in self.parameters:
            params.append(
                Parameter(
                    name=param.name,
                    kind=param.kind,
                    default=param.default if param.has_default else Parameter.empty,
                    annotation=param.annotation
                    if param.annotation is not None
                    else Signature.empty,
                )
            )

        return_annotation = (
            self.return_annotation if self.return_annotation is not None else Signature.empty
        )
        return Signature(parameters=params, return_annotation=return_annotation)


def encode(func: Callable[..., Any], remove_self: bool = False) -> SignatureSpec:
    """Encode the signature of `func` into a serializable `SignatureSpec`.

    If `remove_self` is `True`, remove the first argument.
    """
    sig = signature(func)

    if remove_self:
        parameters = list(sig.parameters.values())[1:]
        sig = sig.replace(parameters=parameters)

    meta: CommandMeta | None = getattr(func, '_meta', None)

    params: dict[str, ParameterSpec] = {}
    for param in sig.parameters.values():
        param_meta = None if meta is None else meta.params.get(param.name)

        has_default = param.default is not Parameter.empty
        params[param.name] = ParameterSpec(
            param.name,
            None if param_meta is None else param_meta.doc,
            param.kind,
            None if param.annotation is Parameter.empty else format_annotation(param.annotation),
            param.default if has_default else None,
            has_default,
            False if param_meta is None else param_meta.hide,
        )

    # add any params defined by the `param()` decorator
    if meta is not None:
        for name, param_meta in meta.params.items():
            if name in params:
                continue
            params[name] = ParameterSpec(
                name, param_meta.doc, ParameterKind.KEYWORD_ONLY, hide=param_meta.hide
            )

    return SignatureSpec(
        func.__name__,
        func.__doc__,
        tuple(params.values()),
        None
        if sig.return_annotation is Signature.empty
        else format_annotation(sig.return_annotation),
        isgeneratorfunction(func),
    )


def decode(spec: SignatureSpec, func: Callable[..., Any]) -> Callable[..., Any]:
    """Recreate a callable from a `SignatureSpec`."""
    if spec.is_generator != isgeneratorfunction(func):
        func_type = 'generator' if spec.is_generator else 'regular'
        raise TypeError(f'expected {func_type} function to decode signature')

    sig = spec.to_signature()
    return cast(Callable[..., Any], create_function(sig, func, func_name=spec.name))


def format_annotation(anno: Any) -> str:
    """Formats annotations in a format compatible with snekrpc client generation."""

    def split_last(s: str) -> str:
        return s.rsplit('.', 1)[-1]

    if isinstance(anno, str):
        # probably a type too complicated to bother with
        return anno

    origin = typing.get_origin(anno)
    if not origin:
        return str(anno) if anno is None else split_last(anno.__name__)
    args = typing.get_args(anno)
    if not args:
        return str(origin)

    return f'{split_last(origin.__name__)}[{split_last(args[0].__name__)}]'

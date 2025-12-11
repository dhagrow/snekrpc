# encoding: utf-8

import contextlib
import inspect
import sys
from inspect import Parameter as Param

import pytest

from snekrpc.utils import function
from snekrpc.utils.function import ParameterKind, ParameterSpec, SignatureSpec


@contextlib.contextmanager
def does_not_raise():
    yield


class F(object):
    def null(self):
        pass

    def positional(self, a):
        "positional"
        return a

    def default(self, a=None):
        "default"
        return a

    @function.command()
    def command(self, a: bool):
        "command"
        return a

    def stream(self):
        "stream"
        for i in range(5):
            yield i

    def positional_only(self, a, /):
        "positional_only"
        return a

    def var_positional(self, *a):
        "var_positional"
        return a

    def var_keyword(self, **a):
        "var_keyword"
        return a

    def mixed_params(self, a, b=None, *c, **d):
        "mixed_params"
        return a, b, c, d

    def default_no_hint(self, a=42):
        "default_no_hint"
        return a

    @function.param('a')
    def kwargs_param(self, **kwargs):
        "kwargs_param"
        return kwargs

    @function.param('a', 'a param')
    def param_decorator(self, a: str):
        "param_decorator"
        return a


def test_roundtrip():
    f1 = F().mixed_params
    d1 = function.encode(f1)
    f2 = function.decode(d1, f1)
    d2 = function.encode(f2)

    assert d1 == d2
    assert f1(1, 2, 3, 4, d=5, e=6) == f2(1, 2, 3, 4, d=5, e=6)


def test_roundtrip_generator():
    f1 = F().stream
    d1 = function.encode(f1)
    f2 = function.decode(d1, f1)
    d2 = function.encode(f2)

    assert d1 == d2
    assert inspect.isgeneratorfunction(f1)
    assert inspect.isgeneratorfunction(f2)
    assert list(f1()) == list(f2())


##
## decode tests
##


def test_decode_null():
    f = F().null
    s = SignatureSpec('null')
    func = function.decode(s, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    assert func() == f()


def test_decode_positional():
    f = F().positional
    s = SignatureSpec('positional', doc='positional', parameters=[ParameterSpec('a')])
    func = function.decode(s, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    assert func(1) == f(1)


def test_decode_default():
    f = F().default
    s = SignatureSpec('default', doc='default', parameters=[ParameterSpec('a', has_default=True)])
    func = function.decode(s, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    assert func() == f()
    assert func(1) == f(1)


def test_decode_command():
    f = F().command
    s = SignatureSpec('command', doc='command', parameters=[ParameterSpec('a', annotation='bool')])
    func = function.decode(s, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    assert func(True) == f(True)


def test_decode_stream():
    f = F().stream
    s = SignatureSpec('stream', doc='stream', is_generator=True)
    func = function.decode(s, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__
    assert inspect.isgeneratorfunction(func)

    assert list(func()) == list(f())


@pytest.mark.skipif(sys.version_info < (3, 8), reason='requires Python >= 3.8')
def test_decode_positional_only():
    f = F().positional_only
    s = SignatureSpec(
        'positional_only',
        doc='positional_only',
        parameters=[ParameterSpec('a', kind=ParameterKind.POSITIONAL_ONLY)],
    )
    func = function.decode(s, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    assert func(1) == f(1)

    with pytest.raises(TypeError):
        func(a=1)


def test_decode_var_positional():
    f = F().var_positional
    s = SignatureSpec(
        'var_positional',
        doc='var_positional',
        parameters=[ParameterSpec('a', kind=ParameterKind.VAR_POSITIONAL)],
    )
    func = function.decode(s, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    for i in range(5):
        args = list(range(i))
        assert func(*args) == f(*args)


def test_decode_var_keyword():
    f = F().var_keyword
    s = SignatureSpec(
        'var_keyword',
        doc='var_keyword',
        parameters=[ParameterSpec('a', kind=ParameterKind.VAR_KEYWORD)],
    )
    func = function.decode(s, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    for i in range(5):
        args = {'arg{}'.format(j): j for j in range(i)}
        assert func(**args) == f(**args)


def test_decode_mixed_params():
    f = F().mixed_params
    s = SignatureSpec(
        'mixed_params',
        doc='mixed_params',
        parameters=[
            ParameterSpec('a'),
            ParameterSpec('b', has_default=True),
            ParameterSpec('c', kind=ParameterKind.VAR_POSITIONAL),
            ParameterSpec('d', kind=ParameterKind.VAR_KEYWORD),
        ],
    )
    func = function.decode(s, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    assert func(1, 2, 3, 4, d=5, e=6) == f(1, 2, 3, 4, d=5, e=6)


def test_decode_default_no_hint():
    f = F().default_no_hint
    s = SignatureSpec(
        'default_no_hint',
        doc='default_no_hint',
        parameters=[ParameterSpec('a', default=42, has_default=True)],
    )
    func = function.decode(s, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    assert func() == f() == 42
    assert func(666) == f(666) == 666


def test_decode_kwargs_param():
    f = F().kwargs_param
    s = SignatureSpec(
        'kwargs_param',
        doc='kwargs_param',
        parameters=[
            ParameterSpec('a', annotation='int', kind=ParameterKind.KEYWORD_ONLY),
            ParameterSpec('kwargs', kind=ParameterKind.VAR_KEYWORD),
        ],
    )
    func = function.decode(s, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    with pytest.raises(TypeError):
        assert func(1) == f(1)
    with pytest.raises(TypeError):
        assert func() == f()
    with pytest.raises(TypeError):
        assert func(x=2) == f(x=2)
    assert func(a=1) == f(a=1)
    assert func(a=1, x=2) == f(a=1, x=2)


def test_decode_param_decorator():
    f = F().param_decorator
    s = SignatureSpec(
        'param_decorator',
        doc='kwargs_param',
        parameters=[ParameterSpec('a', doc='a param', annotation='str')],
    )
    func = function.decode(s, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    assert func(1) == f(1)


@pytest.mark.parametrize(
    'name, expectation',
    [
        ('sys.path', pytest.raises(ValueError)),
        ('l[0]', pytest.raises(ValueError)),
        ('l()', pytest.raises(ValueError)),
        ('1name', pytest.raises(ValueError)),
        ('#name', pytest.raises(ValueError)),
        ('__import__', does_not_raise()),
        ('name1', does_not_raise()),
    ],
)
def test_decode_invalid_param_name(name, expectation):
    s = SignatureSpec('invalid', parameters=[ParameterSpec(name)])
    with expectation:
        function.decode(s, lambda: None)


##
## encode tests
##


def test_encode_null():
    assert function.encode(F().null) == SignatureSpec(name='null')


def test_encode_positional():
    s = function.encode(F().positional)
    assert s == SignatureSpec(name='positional', doc='positional', parameters=(ParameterSpec('a'),))
    assert s.parameters[0].kind == Param.POSITIONAL_OR_KEYWORD


def test_encode_default():
    s = function.encode(F().default)
    assert s == SignatureSpec(
        name='default', doc='default', parameters=(ParameterSpec('a', has_default=True),)
    )
    assert s.parameters[0].kind == Param.POSITIONAL_OR_KEYWORD


def test_encode_command():
    s = function.encode(F().command)
    assert s == SignatureSpec(
        name='command', doc='command', parameters=(ParameterSpec('a', annotation='bool'),)
    )
    assert s.parameters[0].kind == Param.POSITIONAL_OR_KEYWORD


def test_encode_stream():
    s = function.encode(F().stream)
    assert s == SignatureSpec(name='stream', doc='stream', is_generator=True)


@pytest.mark.skipif(sys.version_info < (3, 8), reason='requires Python >= 3.8')
def test_encode_positional_only():
    s = function.encode(F().positional_only)
    assert s == SignatureSpec(
        name='positional_only',
        doc='positional_only',
        parameters=(ParameterSpec('a', kind=ParameterKind.POSITIONAL_ONLY),),
    )
    assert s.parameters[0].kind == Param.POSITIONAL_ONLY


def test_encode_var_positional():
    s = function.encode(F().var_positional)
    assert s == SignatureSpec(
        name='var_positional',
        doc='var_positional',
        parameters=(ParameterSpec('a', kind=ParameterKind.VAR_POSITIONAL),),
    )
    assert s.parameters[0].kind == Param.VAR_POSITIONAL


def test_encode_var_keyword():
    s = function.encode(F().var_keyword)
    assert s == SignatureSpec(
        name='var_keyword',
        doc='var_keyword',
        parameters=(ParameterSpec('a', kind=ParameterKind.VAR_KEYWORD),),
    )
    assert s.parameters[0].kind == Param.VAR_KEYWORD


def test_encode_mixed_params():
    s = function.encode(F().mixed_params)
    assert s == SignatureSpec(
        name='mixed_params',
        doc='mixed_params',
        parameters=(
            ParameterSpec('a'),
            ParameterSpec('b', has_default=True),
            ParameterSpec('c', kind=ParameterKind.VAR_POSITIONAL),
            ParameterSpec('d', kind=ParameterKind.VAR_KEYWORD),
        ),
    )
    assert s.parameters[0].kind == Param.POSITIONAL_OR_KEYWORD
    assert s.parameters[1].kind == Param.POSITIONAL_OR_KEYWORD
    assert s.parameters[2].kind == Param.VAR_POSITIONAL
    assert s.parameters[3].kind == Param.VAR_KEYWORD


def test_encode_default_no_hint():
    s = function.encode(F().default_no_hint)
    assert s == SignatureSpec(
        name='default_no_hint',
        doc='default_no_hint',
        parameters=(ParameterSpec('a', default=42, has_default=True),),
    )
    assert s.parameters[0].kind == Param.POSITIONAL_OR_KEYWORD


### TODO: this looks like an actual regression. The param is not registered
def test_encode_kwargs_param():
    s = function.encode(F().kwargs_param)
    assert s == SignatureSpec(
        name='kwargs_param',
        doc='kwargs_param',
        parameters=(
            ParameterSpec('kwargs', kind=ParameterKind.VAR_KEYWORD),
            ParameterSpec('a', kind=ParameterKind.KEYWORD_ONLY),
        ),
    )
    assert s.parameters[0].kind == Param.VAR_KEYWORD
    assert s.parameters[1].kind == Param.KEYWORD_ONLY


def test_encode_param_decorator():
    s = function.encode(F().param_decorator)
    assert s == SignatureSpec(
        name='param_decorator',
        doc='param_decorator',
        parameters=(ParameterSpec('a', 'a param', annotation='str'),),
    )
    assert s.parameters[0].kind == Param.POSITIONAL_OR_KEYWORD

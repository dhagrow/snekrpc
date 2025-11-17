# encoding: utf-8

import contextlib
import inspect
import sys
from inspect import Parameter as Param

import pytest

from snekrpc.utils import function


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

    @function.param('a', int)
    def kwargs_param(self, **kwargs):
        "kwargs_param"
        return kwargs

    @function.param('a', str, 'a param', extra=42)
    def param_decorator(self, a):
        "param_decorator"
        return a


def test_roundtrip():
    f1 = F().mixed_params
    d1 = function.func_to_dict(f1)
    f2 = function.dict_to_func(d1, f1)
    d2 = function.func_to_dict(f2)

    assert d1 == d2
    assert f1(1, 2, 3, 4, d=5, e=6) == f2(1, 2, 3, 4, d=5, e=6)


def test_roundtrip_generator():
    f1 = F().stream
    d1 = function.func_to_dict(f1)
    f2 = function.dict_to_func(d1, f1)
    d2 = function.func_to_dict(f2)

    assert d1 == d2
    assert inspect.isgeneratorfunction(f1)
    assert inspect.isgeneratorfunction(f2)
    assert list(f1()) == list(f2())


##
## dict_to_func tests
##


def test_d2f_null():
    f = F().null
    d = {
        'name': 'null',
        'params': [],
    }
    func = function.dict_to_func(d, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    assert func() == f()


def test_d2f_positional():
    f = F().positional
    d = {
        'name': 'positional',
        'doc': 'positional',
        'params': [{'name': 'a', 'kind': 1}],
    }
    func = function.dict_to_func(d, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    assert func(1) == f(1)


def test_d2f_default():
    f = F().default
    d = {
        'name': 'default',
        'doc': 'default',
        'params': [{'name': 'a', 'kind': 1, 'default': None}],
    }
    func = function.dict_to_func(d, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    assert func() == f()
    assert func(1) == f(1)


def test_d2f_command():
    f = F().command
    d = {
        'name': 'command',
        'doc': 'command',
        'params': [{'name': 'a', 'hint': 'bool', 'kind': 1}],
    }
    func = function.dict_to_func(d, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    assert func(True) == f(True)


def test_d2f_stream():
    f = F().stream
    d = {
        'name': 'stream',
        'doc': 'stream',
        'isgen': True,
        'params': [],
    }
    func = function.dict_to_func(d, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__
    assert inspect.isgeneratorfunction(func)

    assert list(func()) == list(f())


@pytest.mark.skipif(sys.version_info < (3, 8), reason='requires Python >= 3.8')
def test_d2f_positional_only():
    f = F().positional_only
    d = {
        'name': 'positional_only',
        'doc': 'positional_only',
        'params': [{'name': 'a', 'kind': 0}],
    }
    func = function.dict_to_func(d, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    assert func(1) == f(1)

    # expected: created function does not honor POSITIONAL_ONLY
    assert func(a=1) == f(1)


def test_d2f_var_positional():
    f = F().var_positional
    d = {
        'name': 'var_positional',
        'doc': 'var_positional',
        'params': [{'name': 'a', 'kind': 2}],
    }
    func = function.dict_to_func(d, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    for i in range(5):
        args = list(range(i))
        assert func(*args) == f(*args)


def test_d2f_var_keyword():
    f = F().var_keyword
    d = {
        'name': 'var_keyword',
        'doc': 'var_keyword',
        'params': [{'name': 'a', 'kind': 4}],
    }
    func = function.dict_to_func(d, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    for i in range(5):
        args = {'arg{}'.format(j): j for j in range(i)}
        assert func(**args) == f(**args)


def test_d2f_mixed_params():
    f = F().mixed_params
    d = {
        'name': 'mixed_params',
        'doc': 'mixed_params',
        'params': [
            {'kind': 1, 'name': 'a'},
            {'kind': 1, 'name': 'b', 'default': None},
            {'kind': 2, 'name': 'c'},
            {'kind': 4, 'name': 'd'},
        ],
    }
    func = function.dict_to_func(d, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    assert func(1, 2, 3, 4, d=5, e=6) == f(1, 2, 3, 4, d=5, e=6)


def test_d2f_default_no_hint():
    f = F().default_no_hint
    d = {
        'name': 'default_no_hint',
        'doc': 'default_no_hint',
        'params': [{'name': 'a', 'kind': 1, 'hint': 'int', 'default': 42}],
    }
    func = function.dict_to_func(d, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    assert func() == f() == 42
    assert func(666) == f(666) == 666


def test_d2f_kwargs_param():
    f = F().kwargs_param
    d = {
        'name': 'kwargs_param',
        'doc': 'kwargs_param',
        'params': [
            {'name': 'kwargs', 'kind': 4},
            {'name': 'a', 'kind': 3, 'hint': 'int'},
        ],
    }
    func = function.dict_to_func(d, f)

    assert func.__name__ == f.__name__
    assert func.__doc__ is f.__doc__

    with pytest.raises(TypeError):
        assert func(1) == f(1)
    assert func() == f()
    assert func(a=1) == f(a=1)
    assert func(a=1, x=2) == f(a=1, x=2)
    assert func(x=2) == f(x=2)


def test_d2f_param_decorator():
    f = F().param_decorator
    d = {
        'name': 'param_decorator',
        'doc': 'param_decorator',
        'params': [
            {
                'name': 'a',
                'kind': 1,
                'hint': 'str',
                'doc': 'a param',
                'extra': 42,
            }
        ],
    }
    func = function.dict_to_func(d, f)

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
def test_d2f_invalid_param_name(name, expectation):
    d = {'name': 'invalid', 'params': [{'name': name, 'kind': 1}]}
    with expectation:
        function.dict_to_func(d, lambda: None)


##
## func_to_dict tests
##


def test_f2d_null():
    d = function.func_to_dict(F().null)
    assert d == {
        'name': 'null',
        'doc': None,
        'params': [],
    }


def test_f2d_positional():
    d = function.func_to_dict(F().positional)
    assert d == {
        'name': 'positional',
        'doc': 'positional',
        'params': [{'name': 'a', 'kind': 1}],
    }
    assert d['params'][0]['kind'] == Param.POSITIONAL_OR_KEYWORD


def test_f2d_default():
    d = function.func_to_dict(F().default)
    assert d == {
        'name': 'default',
        'doc': 'default',
        'params': [{'name': 'a', 'kind': 1, 'default': None}],
    }
    assert d['params'][0]['kind'] == Param.POSITIONAL_OR_KEYWORD


def test_f2d_command():
    d = function.func_to_dict(F().command)
    assert d == {
        'name': 'command',
        'doc': 'command',
        'params': [{'name': 'a', 'hint': 'bool', 'kind': 1}],
    }
    assert d['params'][0]['kind'] == Param.POSITIONAL_OR_KEYWORD


def test_f2d_stream():
    d = function.func_to_dict(F().stream)
    assert d == {
        'name': 'stream',
        'doc': 'stream',
        'isgen': True,
        'params': [],
    }


@pytest.mark.skipif(sys.version_info < (3, 8), reason='requires Python >= 3.8')
def test_f2d_positional_only():
    d = function.func_to_dict(F().positional_only)
    assert d == {
        'name': 'positional_only',
        'doc': 'positional_only',
        'params': [{'name': 'a', 'kind': 0}],
    }
    assert d['params'][0]['kind'] == Param.POSITIONAL_ONLY


def test_f2d_var_positional():
    d = function.func_to_dict(F().var_positional)
    assert d == {
        'name': 'var_positional',
        'doc': 'var_positional',
        'params': [{'name': 'a', 'kind': 2}],
    }
    assert d['params'][0]['kind'] == Param.VAR_POSITIONAL


def test_f2d_var_keyword():
    d = function.func_to_dict(F().var_keyword)
    assert d == {
        'name': 'var_keyword',
        'doc': 'var_keyword',
        'params': [{'name': 'a', 'kind': 4}],
    }
    assert d['params'][0]['kind'] == Param.VAR_KEYWORD


def test_f2d_mixed_params():
    d = function.func_to_dict(F().mixed_params)
    assert d == {
        'name': 'mixed_params',
        'doc': 'mixed_params',
        'params': [
            {'kind': 1, 'name': 'a'},
            {'kind': 1, 'name': 'b', 'default': None},
            {'kind': 2, 'name': 'c'},
            {'kind': 4, 'name': 'd'},
        ],
    }
    assert d['params'][0]['kind'] == Param.POSITIONAL_OR_KEYWORD
    assert d['params'][1]['kind'] == Param.POSITIONAL_OR_KEYWORD
    assert d['params'][2]['kind'] == Param.VAR_POSITIONAL
    assert d['params'][3]['kind'] == Param.VAR_KEYWORD


def test_f2d_default_no_hint():
    d = function.func_to_dict(F().default_no_hint)
    assert d == {
        'name': 'default_no_hint',
        'doc': 'default_no_hint',
        'params': [{'name': 'a', 'kind': 1, 'hint': 'int', 'default': 42}],
    }
    assert d['params'][0]['kind'] == Param.POSITIONAL_OR_KEYWORD


def test_f2d_kwargs_param():
    d = function.func_to_dict(F().kwargs_param)
    assert d == {
        'name': 'kwargs_param',
        'doc': 'kwargs_param',
        'params': [
            {'name': 'kwargs', 'kind': 4},
            {'name': 'a', 'kind': 3, 'hint': 'int'},
        ],
    }
    assert d['params'][0]['kind'] == Param.VAR_KEYWORD
    assert d['params'][1]['kind'] == Param.KEYWORD_ONLY


def test_f2d_param_decorator():
    d = function.func_to_dict(F().param_decorator)
    assert d == {
        'name': 'param_decorator',
        'doc': 'param_decorator',
        'params': [
            {
                'name': 'a',
                'kind': 1,
                'hint': 'str',
                'doc': 'a param',
                'extra': 42,
            }
        ],
    }
    assert d['params'][0]['kind'] == Param.POSITIONAL_OR_KEYWORD

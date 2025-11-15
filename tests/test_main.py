def test_null(service):
    assert service.null() is None


def test_echo(service):
    value = 'echooo'
    assert service.echo(value) == value


def test_params(service):
    result = service.params(1)
    assert result == [1, None, True, False, [], {}]

    result = service.params(2, 'a', False, True, 1, 2, 3, z=1)
    assert result == [2, 'a', False, True, [1, 2, 3], {'z': 1}]


def test_upstream(service):
    rtup = list(range(10))

    # send generator
    result = service.upstream((x for x in range(10)))
    assert result == rtup


def test_downstream(service):
    result = list(service.downstream(limit=10))
    assert result == list(range(10))


def test_dualstream(service):
    rtup = list(range(10))
    result = list(service.dualstream(rtup))
    assert result == rtup

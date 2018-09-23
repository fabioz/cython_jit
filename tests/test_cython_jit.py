import pytest

from cython_jit import jit


@jit(nogil=True)
def my_func(bar: 'int'):
    return bar + 1


@jit(nogil=False)
def my_func2(bar):
    return bar + 1


@pytest.mark.parametrize('func, expected', [
    [my_func,
        [
            'cdef int64_t my_func(int bar) nogil:',
            '    return bar + 1'
        ]
    ],
    [my_func2,
        [
            'cdef int64_t my_func2(int64_t bar):',
            '    return bar + 1'
        ]
    ],
])
def test_cython_jit(func, expected, tmpdir):
    from cython_jit._info_collector import all_collectors
    from cython_jit.cython_generator import CythonGenerator
    assert func(1) == 2

    cython_generator = CythonGenerator()
    cython_generator.generate(all_collectors[func.__name__])
    assert [x.rstrip() for x in cython_generator.lines if x.strip()] == expected

    assert cython_generator.temp_dir.exists()
    cython_generator.temp_dir = str(tmpdir.join('cython_jit'))
    assert cython_generator.temp_dir.exists()

    raise AssertionError('finish generation')


def test_compile_with_cython(tmpdir):
    from cython_jit.compile_with_cython import compile_with_cython
    import sys
    target_dir = str(tmpdir.join('target_dir'))
    compile_with_cython(
        'mymod1',
        'def func():\n    return 1\n\n',
        str(tmpdir),
        target_dir,
        silent=True,
    )
    with pytest.raises(ImportError):
        import mymod1  # @UnresolvedImport @UnusedImport

    sys.path.insert(0, target_dir)
    import mymod1  # @UnresolvedImport @Reimport
    assert mymod1.func() == 1
    assert sys.path[0] == target_dir
    del sys.path[0]
    del sys.modules['mymod1']

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
def test_cython_jit(func, expected):
    from cython_jit._info_collector import all_collectors
    from cython_jit.cython_generator import CythonGenerator
    assert func(1) == 2

    cython_generator = CythonGenerator()
    cython_generator.generate(all_collectors[func.__name__])
    assert [x.rstrip() for x in cython_generator.lines if x.strip()] == expected


def test_compile_with_cython(tmpdir):
    temp_dir = tmpdir.join('temp')
    build_dir = tmpdir.join('build')
    from cython_jit.compile_with_cython import compile_with_cython
    compile_with_cython('def func():\n    return 1\n\n', temp_dir, build_dir)

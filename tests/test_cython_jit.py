from contextlib import contextmanager

import pytest

from cython_jit import jit


@jit(nogil=True)
def my_func(bar: 'int'):
    return bar + 1


@jit(nogil=False)
def my_func2(bar):
    return bar + 1


@pytest.fixture(scope='function', autouse=True)
def _auto_pop_module1():
    import sys
    sys.modules.pop('mymod1', None)


@pytest.mark.parametrize('func, expected', [
    [my_func,
        [
            'def my_func_cy_wrapper(int bar) -> int64_t:',
            '    return my_func(bar)',

            'cdef int64_t my_func(int bar) nogil:',
            '    return bar + 1'
        ]
    ],
    [my_func2,
        [
            'def my_func2_cy_wrapper(int64_t bar) -> int64_t:',
            '    return my_func2(bar)',

            'cdef int64_t my_func2(int64_t bar):',
            '    return bar + 1'
        ]
    ],
])
def test_cython_jit(func, expected, tmpdir):
    from cython_jit._info_collector import all_collectors
    from cython_jit.cython_generator import CythonGenerator
    from cython_jit.compile_with_cython import compile_with_cython

    # When calling the function the info is collected.
    assert func(1) == 2

    cython_generator = CythonGenerator()
    cython_generator.generate(all_collectors[func.__name__])
    assert [x.rstrip() for x in cython_generator.func_lines if x.strip()] == expected

    assert cython_generator.temp_dir.exists()
    cython_generator.temp_dir = str(tmpdir.join('cython_jit'))
    assert cython_generator.temp_dir.exists()

    target_dir = str(tmpdir.join('target_dir'))
    compile_with_cython(
        'mymod1',
        '\n'.join(cython_generator.c_import_lines) + '\n' + '\n'.join(cython_generator.func_lines),
        str(tmpdir),
        target_dir,
        silent=True,
    )

    with add_to_sys_path(target_dir):
        import mymod1  # @UnresolvedImport @Reimport
        new_func = getattr(mymod1, func.__name__ + '_cy_wrapper')

    assert new_func(1) == 2


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

    with add_to_sys_path(target_dir):
        import mymod1  # @UnresolvedImport @Reimport
    assert mymod1.func() == 1


@contextmanager
def add_to_sys_path(directory):
    import sys
    sys.path.insert(0, directory)
    try:
        yield
    finally:
        sys.path.remove(directory)

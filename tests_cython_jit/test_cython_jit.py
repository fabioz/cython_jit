from contextlib import contextmanager

import pytest

from tests_cython_jit._to_cython import my_func, my_func2


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

    collector = all_collectors[func.__name__]  # : :type collector: CythonJitInfoCollector
    generated_info = collector.generate()
    assert [x.rstrip() for x in generated_info.func_lines if x.strip()] == expected

    target_dir = str(tmpdir.join('target_dir'))
    contents = '\n'.join(generated_info.c_import_lines) + '\n' + '\n'.join(generated_info.func_lines)
    contents = contents.replace('bar + 1', 'bar + 2')  # To differentiate which version we're calling
    compile_with_cython(
        'mymod1',
        contents,
        str(tmpdir),
        target_dir,
        silent=True,
    )

    with add_to_sys_path(target_dir):
        import mymod1  # @UnresolvedImport @Reimport
        new_func = getattr(mymod1, func.__name__ + '_cy_wrapper')

    assert new_func(1) == 3

    cython_generator = CythonGenerator()
    assert cython_generator.temp_dir.exists()
    cython_generator.temp_dir = str(tmpdir.join('cython_jit'))
    assert cython_generator.temp_dir.exists()


def test_compile_with_cython(tmpdir):
    from cython_jit.compile_with_cython import compile_with_cython
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

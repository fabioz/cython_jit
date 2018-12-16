

from contextlib import contextmanager

import pytest


@pytest.fixture(scope='function', autouse=True)
def _set_new_state_info_fixture(tmpdir):
    '''
    Each test gets a new state info.
    '''
    with _set_new_state_info(tmpdir):
        pass


@contextmanager
def _set_new_state_info(tmpdir):
    from cython_jit import set_cache_dir
    from cython_jit import set_temp_dir
    from cython_jit._jit_state_info import _JitStateInfo
    from cython_jit._jit_state_info import _set_jit_state_info
    from pathlib import Path

    jit_state_info = _JitStateInfo()
    with _set_jit_state_info(jit_state_info):
        set_cache_dir(Path(str(tmpdir.join('cache'))))
        set_temp_dir(Path(str(tmpdir.join('tmp'))))
        yield


@pytest.fixture(scope='function', autouse=True)
def _auto_pop_module1():
    '''

    '''
    import sys
    sys.modules.pop('mymod1_cython_tests', None)


def test_cython_jit(tmpdir):
    from cython_jit import JitStage, set_jit_stage

    with set_jit_stage(JitStage.collect_info):
        from tests_cython_jit._to_cython import my_func, my_func2

        for func, expected in [
            (my_func,
                [
                    'def my_func_cy_wrapper(int bar) -> int64_t:',
                    '    return my_func(bar)',

                    'cdef int64_t my_func(int bar) nogil:',
                    '    return bar + 1'
                ]
            ),
            (my_func2,
                [
                    'def my_func2_cy_wrapper(int64_t bar) -> int64_t:',
                    '    return my_func2(bar)',

                    'cdef int64_t my_func2(int64_t bar):',
                    '    return bar + 1'
                ]
            )]:
            _check_cython_jit(func, expected, tmpdir.join(func.__name__))


def test_cython_jit_ifdef(tmpdir):
    from cython_jit import JitStage, set_jit_stage
    from cython_jit._jit_state_info import _get_jit_state_info

    with set_jit_stage(JitStage.collect_info):
        from tests_cython_jit._to_cython3 import my_func
        assert my_func(2) == 4

        all_collectors = _get_jit_state_info().all_collectors
        collector = all_collectors[my_func.__name__]  # : :type collector: CythonJitInfoCollector
        generated_info = collector.generate()
        assert [x.rstrip() for x in generated_info.func_lines if x.strip()] == [
            'def my_func_cy_wrapper(int64_t bar) -> int64_t:',
            '    return my_func(bar)',
            'cdef int64_t my_func(int64_t bar):',
            '    # IFDEF CYTHON -- DONT EDIT THIS FILE (it is automatically generated)',
            '    cdef Py_ssize_t x',
            '    # ENDIF',
            '    x = 1',
            '    return bar + x + 1',
        ]


def _check_cython_jit(func, expected, tmpdir):
    from cython_jit.compile_with_cython import compile_with_cython
    from cython_jit._jit_state_info import add_to_sys_path
    from cython_jit._jit_state_info import _get_jit_state_info
    import sys

    all_collectors = _get_jit_state_info().all_collectors

    # When calling the function the info is collected.
    assert func(1) == 2

    collector = all_collectors[func.__name__]  # : :type collector: CythonJitInfoCollector
    generated_info = collector.generate()
    assert [x.rstrip() for x in generated_info.func_lines if x.strip()] == expected

    target_dir = str(tmpdir.join('target_dir'))
    contents = '\n'.join(generated_info.c_import_lines) + '\n' + '\n'.join(generated_info.func_lines)
    contents = contents.replace('bar + 1', 'bar + 2')  # To differentiate which version we're calling
    compile_with_cython(
        'mymod1_cython_tests',
        contents,
        str(tmpdir),
        target_dir,
        silent=True,
    )

    with add_to_sys_path(target_dir):
        import mymod1_cython_tests  # @UnresolvedImport @Reimport
        new_func = getattr(mymod1_cython_tests, func.__name__ + '_cy_wrapper')

    assert new_func(1) == 3

    del new_func
    del mymod1_cython_tests
    del sys.modules['mymod1_cython_tests']


def test_cache_working(tmpdir):
    from cython_jit import JitStage, set_jit_stage
    from importlib import reload

    from cython_jit import ModuleNotCachedError
    from cython_jit._jit_state_info import _get_jit_state_info

    # Only collect (and erase) info
    all_collectors = _get_jit_state_info().all_collectors
    with set_jit_stage(JitStage.collect_info):
        from tests_cython_jit import _to_cython2
        _to_cython2.my_func3(1)
    all_collectors.clear()

    # Check that cache is still not there
    with set_jit_stage(JitStage.use_compiled):
        with pytest.raises(ModuleNotCachedError):
            reload(_to_cython2)
    all_collectors.clear()

    # Properly compile it now.
    with set_jit_stage(JitStage.collect_info):
        reload(_to_cython2)
        _to_cython2.my_func3(1)
        _to_cython2.my_func4(1)
        _to_cython2.my_func5(1)
        assert all_collectors['my_func3'].func_first_line == 4
        assert all_collectors['my_func3'].func_last_line == 7

        assert all_collectors['my_func4'].func_first_line == 9
        assert all_collectors['my_func4'].func_last_line == 12

        assert all_collectors['my_func5'].func_first_line == 14
        assert all_collectors['my_func5'].func_last_line == 16

        _get_jit_state_info().compile_collected(silent=True)
    all_collectors.clear()

    # Use compiled version.
    with set_jit_stage(JitStage.use_compiled):
        _to_cython2_reloaded = reload(_to_cython2)
        _to_cython2_reloaded.my_func3(1)

    # Now, use a new info (so, we'll be forced to load it again).
    with _set_new_state_info(tmpdir):
        _to_cython2_reloaded = reload(_to_cython2)
        _to_cython2_reloaded.my_func3(1)


def test_compile_numpy_arrays(tmpdir):
    from cython_jit import JitStage, set_jit_stage
    from importlib import reload

    from cython_jit._jit_state_info import _get_jit_state_info

    with set_jit_stage(JitStage.collect_info):
        from tests_cython_jit import _to_cython_numpy_arrays
        import numpy
        pixels_array = numpy.zeros(shape=(5, 2), dtype=numpy.uint32)
        result = numpy.zeros_like(pixels_array, dtype=numpy.uint8)
        _to_cython_numpy_arrays.check_parameters(pixels_array, 0, 0, 0, result, 0.8)
        _get_jit_state_info().compile_collected(silent=False)

    # Use compiled version.
    with set_jit_stage(JitStage.use_compiled):
        _to_cython_numpy_arrays_reloaded = reload(_to_cython_numpy_arrays)
        _to_cython_numpy_arrays_reloaded.check_parameters(pixels_array, 0, 0, 0, result, 0.8)


def test_compile_with_cython(tmpdir):
    from cython_jit.compile_with_cython import compile_with_cython
    from cython_jit._jit_state_info import add_to_sys_path

    target_dir = str(tmpdir.join('target_dir'))
    compile_with_cython(
        'mymod1_cython_tests',
        'def func():\n    return 1\n\n',
        str(tmpdir),
        target_dir,
        silent=True,
    )
    with pytest.raises(ImportError):
        import mymod1_cython_tests  # @UnresolvedImport @UnusedImport

    with add_to_sys_path(target_dir):
        import mymod1_cython_tests  # @UnresolvedImport @Reimport
    assert mymod1_cython_tests.func() == 1

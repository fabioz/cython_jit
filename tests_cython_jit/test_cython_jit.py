
import pytest

from cython_jit import JitStage, set_jit_stage


@pytest.fixture(scope='function', autouse=True)
def _set_new_state_info():
    '''
    Each test gets a new state info.
    '''
    from cython_jit._jit_state_info import _set_jit_state_info
    from cython_jit._jit_state_info import _JitStateInfo

    jit_state_info = _JitStateInfo()
    with _set_jit_state_info(jit_state_info):
        yield


@pytest.fixture(scope='function', autouse=True)
def _auto_pop_module1():
    '''

    '''
    import sys
    sys.modules.pop('mymod1_cython_tests', None)


def test_cython_jit(tmpdir):
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


def _check_cython_jit(func, expected, tmpdir):
    from cython_jit.cython_generator import CythonGenerator
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

    cython_generator = CythonGenerator()
    assert cython_generator.temp_dir.exists()
    cython_generator.temp_dir = str(tmpdir.join('cython_jit'))
    assert cython_generator.temp_dir.exists()

    del new_func
    del mymod1_cython_tests
    del sys.modules['mymod1_cython_tests']


def test_cache_working(tmpdir):
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
        _get_jit_state_info().compile_collected()
    all_collectors.clear()

    # Use compiled version.
    with set_jit_stage(JitStage.use_compiled):
        _to_cython2_reloaded = reload(_to_cython2)
        _to_cython2_reloaded.my_func3(1)


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

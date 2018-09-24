import atexit
import enum
from functools import wraps


class JitStage(enum.Enum):

    # This mode will not really jit, it'll collect all information needed
    # and when the process exists it'll compile everything so that the next
    # call will actually use the cache.
    collect_info_and_compile_at_exit = 0

    # This mode will force using only compiled information (so, if it's not
    # available it'll fail).
    use_compiled = 1

    # This mode will only collect information (mostly useful for testing).
    collect_info = 2


def _get_jit_state_info():
    try:
        # Store the 'global' info on the function (created on demand).
        return _get_jit_state_info._jit_state_info
    except AttributeError:
        from cython_jit._jit_state_info import _JitStateInfo
        _get_jit_state_info._jit_state_info = _JitStateInfo()

        def _compile_collected():
            pass

        atexit.register(_compile_collected)
    return _get_jit_state_info._jit_state_info


class _RestoreState(object):

    def __init__(self, state_to_restore):
        self.state_to_restore = state_to_restore

    def __enter__(self, *args, **kwargs):
        pass

    def __exit__(self, *args, **kwargs):
        _get_jit_state_info().stage = self.state_to_restore


def set_jit_stage(jit_stage):
    prev = _get_jit_state_info().stage
    _get_jit_state_info().stage = jit_stage
    return _RestoreState(prev)


def get_jit_stage():
    return _get_jit_state_info().stage


def set_cache_dir(directory):
    '''
    The directory where the caches will be stored.
    '''
    _get_jit_state_info().set_dir('cache', directory)


def get_cache_dir():
    return _get_jit_state_info().get_dir('cache')


def set_temp_dir(directory):
    '''
    The directory where the temp files will be stored.
    '''
    _get_jit_state_info().set_dir('temp', directory)


def get_temp_dir():
    return _get_jit_state_info().get_dir('temp')


def jit(nogil=False):

    stage = get_jit_stage()
    jit_state_info = _get_jit_state_info()
    if stage in (JitStage.collect_info_and_compile_at_exit, JitStage.collect_info):

        def method(func):
            from cython_jit import _info_collector
            collector = _info_collector.CythonJitInfoCollector(func, nogil=nogil, jit_stage=stage)

            @wraps(func)
            def actual_method(*args, **kwargs):
                collector.collect_args(args, kwargs)
                ret = func(*args, **kwargs)
                collector.collect_return(ret)
                jit_state_info.collected = True
                return ret

            return actual_method

        return method

    elif stage == JitStage.use_compiled:

        def method(func):
            from cython_jit import _info_collector
            collector = _info_collector.CythonJitInfoCollector(func, nogil=nogil, jit_stage=stage)

            cached = jit_state_info.get_cached(collector)
            if cached is None:
                raise RuntimeError('Unable to find cython-compiled module for: %s' % (func,))
            return cached

        return method

    else:
        raise AssertionError('TODO')


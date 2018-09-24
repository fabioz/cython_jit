import atexit
import enum
from functools import wraps


def _compile_collected():
    pass


atexit.register(_compile_collected)


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


class _StateHolder:
    stage = JitStage.use_compiled
    collected = False


class _RestoreState(object):

    def __init__(self, state_to_restore):
        self.state_to_restore = state_to_restore

    def __enter__(self, *args, **kwargs):
        pass

    def __exit__(self, *args, **kwargs):
        _StateHolder.stage = self.state_to_restore


def set_jit_stage(jit_stage):
    prev = _StateHolder.stage
    _StateHolder.stage = jit_stage
    return _RestoreState(prev)


def get_jit_stage():
    return _StateHolder.stage


def jit(nogil=False):

    stage = get_jit_stage()
    if stage in (JitStage.collect_info_and_compile_at_exit, JitStage.collect_info):

        def method(func):
            from cython_jit import _info_collector
            collector = _info_collector.CythonJitInfoCollector(func, nogil=nogil, jit_stage=stage)
            collector

            @wraps(func)
            def actual_method(*args, **kwargs):
                collector.collect_args(args, kwargs)
                ret = func(*args, **kwargs)
                collector.collect_return(ret)
                _StateHolder.collected = True
                return ret

            return actual_method

        return method

    elif stage == JitStage.use_compiled:
        raise AssertionError('TODO')

    else:
        raise AssertionError('TODO')


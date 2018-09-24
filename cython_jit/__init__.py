from functools import wraps

_collect_info = True


def jit(nogil=False):

    if _collect_info:

        def method(func):
            from cython_jit import _info_collector
            collector = _info_collector.CythonJitInfoCollector(func, nogil=nogil)

            @wraps(func)
            def actual_method(*args, **kwargs):
                collector.collect_args(args, kwargs)
                ret = func(*args, **kwargs)
                collector.collect_return(ret)
                return ret

            return actual_method

    else:
        raise AssertionError('TODO')

    return method

from cython_jit import jit


@jit(nogil=True)
def my_func(bar: 'int'):
    return bar + 1


@jit(nogil=False)
def my_func2(bar):
    return bar + 1
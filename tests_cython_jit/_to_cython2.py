from cython_jit import jit


@jit(nogil=True)
def my_func3(bar):
    return bar + 1
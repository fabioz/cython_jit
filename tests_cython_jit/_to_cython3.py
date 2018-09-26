from cython_jit import jit


@jit(nogil=False)
def my_func(bar):
    # IFDEF CYTHON
    # cdef Py_ssize_t x
    # ENDIF
    x = 1
    return bar + x + 1
from collections import namedtuple


def get_line_indent(line):
    return len(line) - len(line.lstrip())


all_collectors = {}

_GeneratedInfo = namedtuple('_GeneratedInfo', 'func_lines, c_import_lines')


class CythonJitInfoCollector(object):

    def __init__(self, func, nogil):
        import io
        import hashlib
        import inspect
        self._c_imports = set()

        assert func.__name__ not in all_collectors, 'There is already a function named: %s' % (
            func.__name__,)

        self._func = func
        self._nogil = nogil
        self._arg_name_to_arg_type = {}

        all_collectors[func.__name__] = self
        m = hashlib.sha256()
        m.update(func.__code__.co_code)
        self._sig = inspect.signature(func)
        m.update(str(self._sig).encode('utf-8'))
        key = m.hexdigest()

        # If the key is not the same the function must be recompiled.
        self._key = key

        func_lines = []
        with io.open(func.__code__.co_filename, 'r') as stream:
            start_indent = None
            for i_line, line in enumerate(stream.readlines()):
                if start_indent is not None:
                    if line.strip():
                        if get_line_indent(line) <= start_indent:
                            break

                    func_lines.append(line)

                elif i_line == func.__code__.co_firstlineno:
                    func_lines.append(line)
                    start_indent = get_line_indent(line)

        assert func_lines
        self._func_lines = tuple(func_lines)
        self._return_type = 'NOT_COLLECTED'

    def generate(self):
        generated_func_lines = []
        generated_c_import_lines = set()

        def_line = self.func_lines[0].strip()
        assert def_line.endswith(':'), \
            'Can currently only support function where def starts and ends in same line. Found: %s' % (def_line,)
        assert def_line.startswith('def '), \
            'Expected line: %s to start with def.' % (def_line,)

        generated_func_lines.extend(self.get_wrapper_func_lines())
        generated_func_lines.append(self.get_def_line())
        generated_func_lines.extend(self.func_lines[1:])

        generated_c_import_lines.update(self.get_c_import_lines())
        return _GeneratedInfo(generated_func_lines, generated_c_import_lines)

    @property
    def func_lines(self):
        return self._func_lines

    @property
    def func_contents(self):
        return ''.join(self._func_lines)

    @property
    def func(self):
        return self._func

    @property
    def nogil(self):
        return self._nogil

    @property
    def key(self):
        return self._key

    def collect_args(self, args, kwargs):
        bound_arguments = self._sig.bind(*args, **kwargs)
        for arg_name, arg_value in bound_arguments.arguments.items():
            self._collect_arg(arg_name, arg_value)

    def _collect_arg(self, arg_name, arg_value):
        self._arg_name_to_arg_type[arg_name] = type(arg_value)

    def collect_return(self, ret):
        self._return_type = type(ret)

    def _get_arg_type(self, arg_name):
        ann = self._sig.parameters[arg_name].annotation
        if isinstance(ann, str):
            return ann
        arg_type = self._arg_name_to_arg_type[arg_name]
        return self._translate_type(arg_type)

    def get_def_line(self):
        args = []
        for arg in self._sig.parameters:
            args.append('%s %s' % (self._get_arg_type(arg), arg))

        return 'cdef %(ret_type)s %(func_name)s(%(args)s)%(nogil)s:' % (dict(
            ret_type=self.get_cython_ret_type(),
            func_name=self.func.__name__,
            args=', '.join(args),
            nogil=' nogil' if self.nogil else ''
            ))

    def get_wrapper_func_lines(self):
        call_args = []
        args = []
        for arg in self._sig.parameters:
            args.append('%s %s' % (self._get_arg_type(arg), arg))
            call_args.append(arg)

        d = dict(
            ret_type=self.get_cython_ret_type(),
            func_name=self.func.__name__,
            args=', '.join(args),
            call_args=', '.join(call_args),
        )
        def_line = 'def %(func_name)s_cy_wrapper(%(args)s) -> %(ret_type)s:' % (d)

        return [def_line, '    return %(func_name)s(%(call_args)s)' % d]

    def get_c_import_lines(self):
        return sorted(self._c_imports)

    def _translate_type(self, arg_type):
        if arg_type == int:
            ret = 'int64_t'
        else:
            raise AssertionError('Unhandled: %s' % (arg_type,))

        self._c_imports.add('from libc.stdint cimport %s' % (ret,))
        return ret

    def get_cython_ret_type(self):
        return self._translate_type(self._return_type)

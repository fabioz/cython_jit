import sys
from collections import namedtuple
from contextlib import contextmanager

from cython_jit import JitStage


def get_line_indent(line):
    return len(line) - len(line.lstrip())


_GeneratedInfo = namedtuple('_GeneratedInfo', 'func_lines, c_import_lines')


class InfoNotCollectedError(RuntimeError):
    pass


def fix_cython_ifdefs(func_lines):
    state = 'regular'
    new_contents = []
    for line in func_lines:
        strip = line.strip()
        if state == 'regular':
            if strip == '# IFDEF CYTHON':
                state = 'cython'

                new_contents.append(
                    '%s -- DONT EDIT THIS FILE (it is automatically generated)\n' % 
                    line.replace('\n', '').replace('\r', ''))
                continue

            new_contents.append(line)

        elif state == 'cython':
            if strip == '# ELSE':
                state = 'nocython'
                new_contents.append(line)
                continue

            elif strip == '# ENDIF':
                state = 'regular'
                new_contents.append(line)
                continue

            assert strip.startswith('#'), 'Line inside # IFDEF CYTHON must start with "# ".'
            new_contents.append(line.replace('# ', '', 1))

        elif state == 'nocython':
            if strip == '# ENDIF':
                state = 'regular'
                new_contents.append(line)
                continue
            new_contents.append('# %s' % line)

    assert state == 'regular', 'Error: # IFDEF CYTHON found without # ENDIF'
    return new_contents


class CythonJitInfoCollector(object):

    RETURN_NOT_COLLECTED = 'RETURN_NOT_COLLECTED'

    def __init__(self, func, nogil, jit_stage):
        import hashlib
        import inspect
        from cython_jit._jit_state_info import _get_jit_state_info
        self._c_imports = set()

        all_collectors = _get_jit_state_info().all_collectors
        assert func.__name__ not in all_collectors, 'There is already a function named: %s from file: %s' % (
            func.__name__, func.__code__.co_filename)

        self._func = func
        self._nogil = nogil
        self._arg_name_to_arg_type = {}

        all_collectors[func.__name__] = self
        m = hashlib.sha256()
        m.update(func.__code__.co_code)
        self._sig = inspect.signature(func)
        m.update(str(self._sig).encode('utf-8'))
        if nogil:
            m.update(b'noexcept nogil')
        key = m.hexdigest()

        # If the key is not the same the function must be recompiled.
        self._key = key
        self._jit_stage = jit_stage

        if jit_stage in (JitStage.collect_info_and_compile_at_exit, JitStage.collect_info):
            func_lines = []
            func_first_line = self.func_first_line
            with self.file_stream() as stream:
                start_indent = None

                lines = stream.readlines()
                func_lines.append(lines[func_first_line])
                start_indent = get_line_indent(func_lines[-1])

                for i_line, line in enumerate(lines[func_first_line + 1:]):
                    if start_indent is not None:
                        if line.strip():
                            if get_line_indent(line) <= start_indent:
                                i_line -= 1
                                break

                        func_lines.append(line)
                else:
                    i_line += 1

            self._last_line = i_line + func_first_line + 1

            func_lines = fix_cython_ifdefs(func_lines)
            assert func_lines

            self._func_lines = tuple(func_lines)
            self._return_type = self.RETURN_NOT_COLLECTED

    @property
    def func_first_line(self):
        return self.func.__code__.co_firstlineno

    @property
    def func_last_line(self):
        return self._last_line

    @contextmanager
    def file_stream(self, mode='r'):
        import io
        with io.open(self.func.__code__.co_filename, mode) as stream:
            yield stream

    def collected_info(self):
        return self._return_type != self.RETURN_NOT_COLLECTED

    def get_pyd_name(self):
        return self.func.__module__.replace('.', '_') + '_cyjit' + ''.join(str(x) for x in sys.version_info[:2])

    def _check_jit_stage_collect(self):
        if self._jit_stage not in (JitStage.collect_info_and_compile_at_exit, JitStage.collect_info):
            raise AssertionError('Should only be called at collect time.')

    def generate(self):
        self._check_jit_stage_collect()
        if not self.collected_info():
            raise InfoNotCollectedError('No info was collected for: %s in file: %s' % (self.func, self.func.__code__.co_filename))

        generated_func_lines = []
        generated_c_import_lines = set()

        def_line = self.func_lines[0].strip()
        assert def_line.endswith(':'), \
            'Can currently only support function where def starts and ends in same line. Found: %s' % (def_line,)
        assert def_line.startswith('def '), \
            'Expected line: %s to start with def.' % (def_line,)

        generated_func_lines.extend(self.get_wrapper_func_lines())
        generated_func_lines.append(self.get_def_line())
        generated_func_lines.extend((x.rstrip() for x in self.func_lines[1:]))

        generated_c_import_lines.update(self.get_c_import_lines())
        return _GeneratedInfo(generated_func_lines, generated_c_import_lines)

    @property
    def func_lines(self):
        self._check_jit_stage_collect()
        return self._func_lines

    @property
    def func_contents(self):
        self._check_jit_stage_collect()
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
        self._check_jit_stage_collect()
        bound_arguments = self._sig.bind(*args, **kwargs)
        for arg_name, arg_value in bound_arguments.arguments.items():
            ann = self._sig.parameters[arg_name].annotation
            if isinstance(ann, str):
                # Don't collect if it's already annotated.
                continue

            self._collect_arg(arg_name, arg_value)

    def _collect_arg(self, arg_name, arg_value):
        self._arg_name_to_arg_type[arg_name] = self._translate_type(arg_name, arg_value)

    def collect_return(self, ret):
        self._check_jit_stage_collect()
        if self._sig.return_annotation and self._sig.return_annotation != self._sig.empty:
            self._return_type = self._sig.return_annotation
        else:
            self._return_type = self._translate_type('return value', ret)

    def _get_arg_type(self, arg_name):
        ann = self._sig.parameters[arg_name].annotation
        if isinstance(ann, str):
            return ann
        return self._arg_name_to_arg_type[arg_name]

    def get_def_line(self):
        self._check_jit_stage_collect()
        args = []
        for arg in self._sig.parameters:
            args.append('%s %s' % (self._get_arg_type(arg), arg))

        # Add:
        # @cython.boundscheck(False) # turn off bounds-checking for entire function
        # @cython.wraparound(False)  # turn off negative index wrapping for entire function

        return 'cdef %(ret_type)s %(func_name)s(%(args)s)%(nogil)s:' % (dict(
            ret_type=self.get_cython_ret_type(),
            func_name=self.func.__name__,
            args=', '.join(args),
            nogil=' noexcept nogil' if self.nogil else ''
            ))

    def get_wrapper_func_lines(self):
        self._check_jit_stage_collect()
        call_args = []
        args = []
        for arg in self._sig.parameters:
            args.append('%s %s' % (self._get_arg_type(arg), arg))
            call_args.append(arg)

        d = dict(
            ret_type=self.get_cython_ret_type(),
            func_name=self.func.__name__,
            func_wrapper_name=self.get_func_wrappr_name(),
            args=', '.join(args),
            call_args=', '.join(call_args),
        )
        def_line = 'def %(func_wrapper_name)s(%(args)s) -> %(ret_type)s:' % (d)

        return [def_line, '    return %(func_name)s(%(call_args)s)' % d]

    def get_func_wrappr_name(self):
        return '%s_cy_wrapper' % (self.func.__name__,)

    def get_c_import_lines(self):
        self._check_jit_stage_collect()
        return sorted(self._c_imports)

    def _translate_type(self, arg_name, value):
        import numpy
        if type(value) == numpy.int32:
            ret = 'int32_t'
            self._c_imports.add('from libc.stdint cimport %s' % (ret,))

        elif type(value) == numpy.uint32:
            ret = 'uint32_t'
            self._c_imports.add('from libc.stdint cimport %s' % (ret,))

        elif isinstance(value, (int, numpy.int64)):
            ret = 'int64_t'
            self._c_imports.add('from libc.stdint cimport %s' % (ret,))

        elif isinstance(value, float):
            ret = 'double'

        elif value is None:
            return 'void'

        elif isinstance(value, numpy.ndarray):
            if value.dtype == numpy.uint32:
                dtype_str = 'uint32_t'
            elif value.dtype == numpy.uint8:
                dtype_str = 'uint8_t'
            else:
                raise AssertionError('Unhandled %s: %s' % (arg_name, value.dtype,))

            self._c_imports.add('from libc.stdint cimport %s' % (dtype_str,))
            return '%s[%s]' % (dtype_str, ','.join([':'] * value.ndim))

        elif value.__class__.__name__ == self._sig.return_annotation:
            return value.__class__.__name__

        else:
            raise AssertionError('Unhandled %s: %s (%s)' % (arg_name, type(value), value))

        return ret

    def get_cython_ret_type(self):
        self._check_jit_stage_collect()
        return self._return_type

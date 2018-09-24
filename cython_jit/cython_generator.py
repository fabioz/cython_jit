class CythonGenerator(object):

    def __init__(self):
        self._func_lines = []
        self._temp_dir = None
        self._c_import_lines = set()

    @property
    def temp_dir(self):
        import tempfile
        from pathlib import Path
        ret = self._temp_dir
        if ret is None:
            ret = Path(tempfile.gettempdir()) / 'cython_jit'

        ret.mkdir(exist_ok=True)
        return ret

    @temp_dir.setter
    def temp_dir(self, temp_dir):
        from pathlib import Path
        self._temp_dir = Path(temp_dir)

    @property
    def func_lines(self):
        return tuple(self._func_lines)

    @property
    def c_import_lines(self):
        return tuple(sorted(self._c_import_lines))

    def generate(self, collector):
        def_line = collector.func_lines[0].strip()
        assert def_line.endswith(':'), \
            'Can currently only support function where def starts and ends in same line. Found: %s' % (def_line,)
        assert def_line.startswith('def '), \
            'Expected line: %s to start with def.' % (def_line,)

        self._func_lines.extend(collector.get_wrapper_func_lines())
        self._func_lines.append(collector.get_def_line())
        self._func_lines.extend(collector.func_lines[1:])

        self._c_import_lines.update(collector.get_c_import_lines())


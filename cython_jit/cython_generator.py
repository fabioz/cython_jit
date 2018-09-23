class CythonGenerator(object):

    def __init__(self):
        self.lines = []
        self._temp_dir = None

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

    def generate(self, collector):
        def_line = collector.func_lines[0].strip()
        assert def_line.endswith(':'), \
            'Can currently only support function where def starts and ends in same line. Found: %s' % (def_line,)
        assert def_line.startswith('def '), \
            'Expected line: %s to start with def.' % (def_line,)

        self.lines.append(collector.get_def_line())
        self.lines.extend(collector.func_lines[1:])

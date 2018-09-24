class CythonGenerator(object):

    def __init__(self):
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


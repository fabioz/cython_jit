from contextlib import contextmanager


@contextmanager
def add_to_sys_path(directory):
    import sys
    sys.path.insert(0, directory)
    try:
        yield
    finally:
        sys.path.remove(directory)


class _JitStateInfo:

    def __init__(self):
        from cython_jit import JitStage
        self.stage = JitStage.use_compiled
        self._dirs = {}
        self.collected = False

    def set_dir(self, dir_type, directory):
        assert dir_type in ('cache', 'temp')
        from pathlib import Path
        assert isinstance(directory, Path)
        directory.mkdir(exist_ok=True)
        self._dirs[dir_type] = directory

    def get_dir(self, dir_type):
        directory = self._dirs.get(dir_type)
        if directory is None:
            # Use default
            from pathlib import Path
            import tempfile
            if dir_type == 'cache':
                directory = Path(tempfile.gettempdir()) / 'cython_jit_temp'
            elif dir_type == 'temp':
                directory = Path(tempfile.gettempdir()) / 'cython_jit'
            else:
                raise AssertionError('Unexpected dir type: %s' % (dir_type,))
        return directory

    def get_cached(self, collector):
        '''
        :param CythonJitInfoCollector collector:
        '''
        import importlib
        pyd_name = collector.func.replace('.', '_') + 'cyjit'
        cache_dir = self.get_dir('cache')

        raise AssertionError('todo')
        with add_to_sys_path(cache_dir):
            importlib.import_module(pyd_name)
            collector.key
            collector.func

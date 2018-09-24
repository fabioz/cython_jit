

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
        from cython_jit import JitStage
        if self.stage in (JitStage.collect_info_and_compile_at_exit, JitStage.collect_info):
            pyd_name = collector.func.__module__
            print(pyd_name)
            collector.key
            collector.func
            raise AssertionError('todo')
        elif self.stage == (JitStage.use_compiled):
            raise AssertionError('todo')
        else:
            raise AssertionError('Unexpected stage: %s' % (self.stage,))

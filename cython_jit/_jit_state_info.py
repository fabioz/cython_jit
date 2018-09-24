import atexit
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
        self.all_collectors = {}

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
        pyd_name = collector.func.__module__.replace('.', '_') + 'cyjit'
        cache_dir = self.get_dir('cache')

        with add_to_sys_path(cache_dir):
            try:
                mod = importlib.import_module(pyd_name)
            except ImportError:
                return None

            collector.key
            collector.func

    def compile_collected(self):
        pass


def _get_jit_state_info():
    '''
    Private API. Don't use.
    '''
    try:
        # Store the 'global' info on the function (created on demand).
        return _get_jit_state_info._jit_state_info
    except AttributeError:
        jit_state_info = _get_jit_state_info._jit_state_info = _JitStateInfo()

        atexit.register(jit_state_info.compile_collected)
    return _get_jit_state_info._jit_state_info


class _RestoreJitStateInfo(object):

    def __init__(self, _jit_state_info):
        self.jit_state_info_to_restore = _jit_state_info

    def __enter__(self, *args, **kwargs):
        pass

    def __exit__(self, *args, **kwargs):
        _get_jit_state_info()._jit_state_info = self.jit_state_info_to_restore


def _set_jit_state_info(jit_state_info):
    '''
    :note: may be used as a context-manager which restores the previous info.
        i.e.:
        temp_info = _JitStateInfo
        with _set_jit_state_info(temp_info):
            ...
    '''
    prev = _get_jit_state_info()
    return _RestoreJitStateInfo(prev)

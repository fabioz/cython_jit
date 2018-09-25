from contextlib import contextmanager


@contextmanager
def add_to_sys_path(directory):
    directory = str(directory)  # just in case it's a Path and not a str.
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
                directory = Path(tempfile.gettempdir()) / 'cython_jit'
            elif dir_type == 'temp':
                directory = Path(tempfile.gettempdir()) / 'cython_jit_temp'
            else:
                raise AssertionError('Unexpected dir type: %s' % (dir_type,))
            self.set_dir(dir_type, directory)
        return directory

    def get_cached(self, collector):
        '''
        :param CythonJitInfoCollector collector:
        '''
        import importlib
        pyd_name = collector.get_pyd_name()
        cache_dir = self.get_dir('cache')

        with add_to_sys_path(cache_dir):
            try:
                mod = importlib.import_module(pyd_name)
            except ImportError:
                return None

            collector.key
            collector.func

    def compile_collected(self, silent=False):
        from collections import defaultdict
        from pathlib import Path
        from cython_jit.compile_with_cython import compile_with_cython
        import cython_jit

        pyd_name_to_collectors = defaultdict(list)
        for collector in self.all_collectors.values():
            if collector.collected_info:
                pyd_name = collector.get_pyd_name()
                pyd_name_to_collectors[pyd_name].append(collector)

        for pyd_name, collectors in pyd_name_to_collectors.items():
            first_collector = next(iter(collectors))
            filepath = Path(first_collector.func.__code__.co_filename)

            if not filepath.exists():
                raise RuntimeError('Expected: %s to exist.' % (filepath,))

            with filepath.open() as stream:
                original_lines = [x.rstrip() for x in stream.readlines()]

            # We must apply bottom to top so that lines are correct.
            collectors = sorted(
                collectors, key=lambda collector:-collector.func_first_line)

            import_lines = set()
            for collector in collectors:
                info_to_apply = collector.generate()

                # Remove decorators too
                func_first_line = collector.func_first_line
                while original_lines[func_first_line].startswith('def') or \
                        original_lines[func_first_line].startswith('@'):
                    func_first_line -= 1

                original_lines[func_first_line:collector.func_last_line] = info_to_apply.func_lines
                import_lines.update(info_to_apply.c_import_lines)

            original_lines = sorted(import_lines) + original_lines

            pyd_name = first_collector.get_pyd_name()

            target_dir = cython_jit.get_cache_dir()
            temp_dir = cython_jit.get_temp_dir()

            for filepath in target_dir.iterdir():
                if filepath.name.startswith(pyd_name):
                    filepath.unlink()

            compile_with_cython(
                pyd_name, '\n'.join(original_lines), temp_dir, target_dir, silent=silent)


def _get_jit_state_info():
    '''
    Private API. Don't use.
    '''
    try:
        # Store the 'global' info on the function (created on demand).
        return _get_jit_state_info._jit_state_info
    except AttributeError:
        _get_jit_state_info._jit_state_info = _JitStateInfo()

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

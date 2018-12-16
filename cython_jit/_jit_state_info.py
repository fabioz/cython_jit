from collections import namedtuple
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


class _EraseHelper(object):

    def __init__(self):
        self._removed = set()

    def remove(self, filepath):
        if filepath not in self._removed:
            self._removed.add(filepath)
            try:
                filepath.unlink()
            except OSError:
                pass


class _JitStateInfo:

    def __init__(self):
        from cython_jit import JitStage
        self.stage = JitStage.use_compiled
        self._dirs = {}
        self.all_collectors = {}
        self._erase_helper = _EraseHelper()
        self._pyd_name_to_module = {}

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

        module = self._pyd_name_to_module.get(pyd_name)
        if module is not None:
            return getattr(module, collector.get_func_wrappr_name())

        target_dir = self.get_dir('cache')

        pyd_info = self._get_pyd_info_from_dir(pyd_name, target_dir)
        if pyd_info.latest_pyd_name:
            with add_to_sys_path(target_dir):
                try:
                    module = importlib.import_module(pyd_info.latest_pyd_name)
                except ImportError:
                    return None

                try:
                    ret = getattr(module, collector.get_func_wrappr_name())
                except AttributeError:
                    return None
                else:
                    if module.cython_jit_key_matches(collector.func.__name__, collector.key):
                        self._pyd_name_to_module[pyd_name] = module
                        return ret

    def compile_collected(self, silent=False, debug=False):
        from collections import defaultdict
        from pathlib import Path
        from cython_jit.compile_with_cython import compile_with_cython
        import cython_jit
        import importlib
        from ._info_collector import fix_cython_ifdefs

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
                original_lines = fix_cython_ifdefs([x.rstrip() for x in stream.readlines()])

            # We must apply bottom to top so that lines are correct.
            collectors = sorted(
                collectors, key=lambda collector:-collector.func_first_line)

            import_lines = set()

            keys_collected = {}
            for collector in collectors:
                info_to_apply = collector.generate()
                keys_collected[collector.func.__name__] = collector.key

                # Remove decorators too
                func_first_line = collector.func_first_line
                while original_lines[func_first_line].startswith('def') or \
                        original_lines[func_first_line].startswith('@'):
                    func_first_line -= 1

                original_lines[func_first_line:collector.func_last_line] = info_to_apply.func_lines
                import_lines.update(info_to_apply.c_import_lines)

            cython_jit_key_matches_method = '''
_keys_collected = %(keys_collected)r
def cython_jit_key_matches(func_name, key):
    return _keys_collected.get(func_name) == key
''' % dict(keys_collected=keys_collected)

            original_lines = sorted(import_lines) + \
                [x.rstrip() for x in cython_jit_key_matches_method.splitlines()] + \
                original_lines

            original_lines = ['# cython: language_level=3'] + original_lines

            pyd_name = first_collector.get_pyd_name()

            target_dir = cython_jit.get_cache_dir()
            temp_dir = cython_jit.get_temp_dir()

            pyd_info = self._get_pyd_info_from_dir(pyd_name, target_dir)

            compile_with_cython(
                pyd_info.next_pyd_name, '\n'.join(original_lines), temp_dir, target_dir, silent=silent, debug=debug)

            with add_to_sys_path(target_dir):
                self._pyd_name_to_module[pyd_name] = importlib.import_module(pyd_info.next_pyd_name)

    def _get_pyd_info_from_dir(self, pyd_name, target_dir):
        # pyd_name is something as: tests_cython_jit__to_cython2_cyjit
        # file name is something as: tests_cython_jit__to_cython2_cyjit.cp36-win_amd64.pyd
        found_paths = set()
        existing_pyd_names_to_filepath = {}
        latest_pyd_name = None
        for filepath in target_dir.iterdir():
            if filepath.name.startswith(pyd_name):
                found_paths.add(filepath)
                existing_pyd_names_to_filepath[filepath.name.split('.')[0]] = filepath

        next_pyd_name = pyd_name
        if existing_pyd_names_to_filepath:
            version_to_pyd_name = {}

            # Find the latest version compiled
            for existing_pyd_name in existing_pyd_names_to_filepath:
                if existing_pyd_name == pyd_name:
                    version_to_pyd_name[0] = existing_pyd_name
                else:
                    try:
                        version_to_pyd_name[int(existing_pyd_name[len(pyd_name) + 1:])] = existing_pyd_name
                    except ValueError:
                        continue

            last_version = max(version_to_pyd_name.keys())
            next_pyd_name = '%s_%04d' % (pyd_name, last_version + 1)
            latest_pyd_name = version_to_pyd_name[last_version]

            for _version, existing_pyd_name in sorted(version_to_pyd_name.items())[:-1]:
                self._erase_helper.remove(existing_pyd_names_to_filepath[existing_pyd_name])

        return _PydInfo(
            next_pyd_name=next_pyd_name,
            existing_pyd_names=list(existing_pyd_names_to_filepath.keys()),
            latest_pyd_name=latest_pyd_name)


_PydInfo = namedtuple('_PydInfo', 'next_pyd_name, existing_pyd_names, latest_pyd_name')


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
    _get_jit_state_info._jit_state_info = jit_state_info
    prev = _get_jit_state_info()
    return _RestoreJitStateInfo(prev)

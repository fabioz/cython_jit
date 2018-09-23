import os
from contextlib import contextmanager


@contextmanager
def working_directory(path):
    from pathlib import Path
    prev_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)


def compile_with_cython(module_name, module_contents, temp_dir, target_dir, silent=False):
    import json
    import os.path
    import subprocess
    import sys
    from pathlib import Path

    temp_dir = Path(temp_dir)

    temp_dir.mkdir(exist_ok=True)
    Path(target_dir).mkdir(exist_ok=True)

    pyx_file = temp_dir / (module_name + '.pyx')
    with pyx_file.open('w') as stream:
        stream.write(module_contents)

    setup_template = '''
from Cython.Build import cythonize
from distutils.core import setup

ext_modules = %(ext_modules)s
setup(
    name='Cythonize',
    ext_modules=cythonize(ext_modules),
)
''' % dict(
    ext_modules=json.dumps([str(pyx_file)]),
    )

    setup_cython = temp_dir / 'setup_cython.py'
    with setup_cython.open('w') as stream:
        stream.write(setup_template)

    from py_compile_win_helpers import get_compile_env
    env = get_compile_env()
    build_temp_artifacts = temp_dir
    build_temp_artifacts.mkdir(exist_ok=True)
    env['TMPDIR'] = env['TEMP'] = str(build_temp_artifacts)

    assert os.path.exists(setup_cython), 'Expected %s to exist.' % (setup_cython,)
    args = [
        sys.executable,
        str(setup_cython),
        'build_ext',
        '--build-lib', str(target_dir),
        '--build-temp', str(build_temp_artifacts)
    ]
    if not silent:
        print('Calling args: %s' % (args,))
    with working_directory(os.path.dirname(setup_cython)):
        kwargs = {}
        if silent:
            process = subprocess.Popen(
                args, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            process.communicate()
            if process.returncode:
                from subprocess import CalledProcessError
                raise CalledProcessError(process.returncode, args)
        else:
            subprocess.check_call(args, env=env, **kwargs)

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import find_packages, setup

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = ['cython', ]

setup_requirements = [
    'pytest-runner',
]

test_requirements = [
    'pytest',
]


setup(
    author="Fabio Zadrozny",
    author_email='fabiofz@gmail.com',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Eclipse Public License 2.0 (EPL-2.0)',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
    description="Use Cython as a Jit for Python",
    entry_points={
    },
    install_requires=requirements,
    license="EPL (Eclipse Public License)",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords=['cython', 'jit', 'cython_jit'],
    name='cython_jit',
    packages=find_packages(include=['cython_jit']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/fabioz/cython_jit',
    version='0.0.1',
    zip_safe=False,
)

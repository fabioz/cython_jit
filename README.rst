===============
cython_jit
===============


.. image:: https://img.shields.io/pypi/v/cython_jit.svg
        :target: https://pypi.python.org/pypi/cython_jit

.. image:: https://img.shields.io/travis/fabioz/cython_jit.svg
        :target: https://travis-ci.org/fabioz/cython_jit


Features
==========

Provides a decorator which allows using cython as a jit.

Installing
============

Requisites
-----------

- python 3.6 onwards
- cython 0.2.9 onwards

Install with pip
-----------------

To install it use:

``pip install cython_jit``


How to use
------------

The idea of cython_jit is automatically compiling a method using cython gathering runtime
information on the parameters for the function being called.

It's still a work in progress...

License
==========

* EPL (Eclipse Public License) 2.0

Releasing
==========

- Update versions on ``setup.py`` and ``version.py``
- ``git tag {{version}}`` (i.e.: v0.1.2)
- ``git push --tags`` (travis should build and deploy)

Local release
---------------

- Update versions on ``setup.py`` and ``version.py``
- ``python setup.py sdist bdist_wheel``
- ``python -m twine upload dist/*``

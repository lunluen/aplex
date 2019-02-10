.. intallation:

Installation
============

Python Version
--------------

Aplex supports Python3.5+.

Dependencies
------------

Required
~~~~~~~~

* None

Optional
~~~~~~~~

* `uvloop`_ is a fast, drop-in replacement of the built-in asyncio event loop.

.. _uvloop: https://github.com/MagicStack/uvloop

Install Aplex
-----------------

For General Users
~~~~~~~~~~~~~~~~~

Use the package manager `pip <https://pip.pypa.io/en/stable/>`_ or `pipenv <http://pipenv.org/>`_ to
install aplex.

With pip::

    $ pip install aplex

Or with pipenv::

    $ pipenv install aplex

Install Optional Dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Simply add a suffix::

    $ pip install aplex[uvloop]

For Contributors
~~~~~~~~~~~~~~~~

Install with pipenv(recommand if you want to build docs)::

    git clone https://github.com/lunluen/aplex.git
    cd aplex
    pipenv install --dev

or with `setuptools <https://github.com/pypa/setuptools>`_::

    git clone https://github.com/lunluen/aplex.git
    cd aplex
    python setup.py develop

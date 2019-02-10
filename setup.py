#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Note: To use the 'upload' functionality of this file, you must:
#   $ pip install twine

# Modified from https://github.com/kennethreitz/setup.py


import io
import os
import sys
from shutil import rmtree

from setuptools import find_packages, setup, Command
from setuptools.command.test import test as TestCommand


NAME = 'aplex'
DESCRIPTION = ('Run your coroutines and functions in child process or '
               'thread like the way using concurrent.futures.')
URL = 'https://github.com/lunluen/aplex'
EMAIL = 'mas581301@gmail.com'
AUTHOR = 'Lunluen'
REQUIRES_PYTHON = '>=3.5.0'
VERSION = None

REQUIRED = []
EXTRAS = {
    'uvloop': ['uvloop'],
}

TEST_REQUIRED = [
    'pytest',
    'pytest-cov',
    'pytest-mock',
    'pytest-timeout',
]


here = os.path.abspath(os.path.dirname(__file__))

# Import the README and use it as the long-description.
try:
    with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
        long_description = '\n' + f.read()
except FileNotFoundError:
    long_description = DESCRIPTION

# Load the package's __version__.py module as a dictionary.
about = {}
if not VERSION:
    with open(os.path.join(here, NAME, '__version__.py')) as f:
        exec(f.read(), about)
else:
    about['__version__'] = VERSION


class UploadCommand(Command):
    """Support setup.py upload."""

    description = 'Build and publish the package.'
    user_options = [('test=', 't', 'Upload to TestPyPI.')]

    @staticmethod
    def status(s):
        """Prints things in bold."""
        print('\033[1m{0}\033[0m'.format(s))

    def initialize_options(self):
        self.test = None

    def finalize_options(self):
        pass

    def run(self):
        try:
            self.status('Removing previous builds…')
            rmtree(os.path.join(here, 'dist'))
        except OSError:
            pass

        self.status('Building Source and Wheel (universal) distribution…')
        os.system('{0} setup.py sdist bdist_wheel --universal'.format(
            sys.executable))

        if self.test is not None:
            # TODO(Lun): If type "python setup.py upload -t",
            # than self.test == ''? or None?
            # How about "python setup.py upload -t      "?
            self.status('Uploading the package to TestPyPI via Twine…')
            os.system('twine upload --repository-url '
                      'https://test.pypi.org/legacy/ dist/*')

            sys.exit()

        # TODO(Lun): `twine check` for README render.
        self.status('Uploading the package to PyPI via Twine…')
        os.system('twine upload dist/*')

        self.status('Pushing git tags…')
        os.system('git tag v{0}'.format(about['__version__']))
        os.system('git push --tags')

        sys.exit()


class PyTest(TestCommand):
    user_options = [("pytest-args=", "a", "Arguments to pass to pytest")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = ''

    def finalize_options(self):
        TestCommand.finalize_options(self)

    def run(self):
        import shlex

        # import here, cause outside the eggs aren't loaded
        import pytest

        errno = pytest.main(shlex.split(self.pytest_args))
        sys.exit(errno)


setup(
    name=NAME,
    version=about['__version__'],
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type='text/markdown',
    author=AUTHOR,
    author_email=EMAIL,
    python_requires=REQUIRES_PYTHON,
    url=URL,
    packages=find_packages(exclude=('tests',)),
    install_requires=REQUIRED,
    extras_require=EXTRAS,
    include_package_data=True,
    license='MIT',
    zip_safe=False,
    classifiers=[
        # Trove classifiers
        # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
        # Or see: https://pypi.org/classifiers/
        'Development Status :: 4 - Beta',
        # Development Status :: 5 - Production/Stable,
        'Framework :: AsyncIO',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython',
        # TODO(Lun): PyPy(not tested).
        # 'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    # $ setup.py publish support.
    cmdclass={
        'upload': UploadCommand,
        'pytest': PyTest,
    },
    tests_require=TEST_REQUIRED,
)

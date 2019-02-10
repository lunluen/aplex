# A workaround to solve ImportError of pytest.
# This has pytest add the directory containing this file, which is
# placed with the package folder, to sys.path.
# No need for `pip install -e .` nor `python setup.py pytest` nor
# `python -m pytest tests/` nor `PYTHONPATH=. py.test`.
# Just simply type `pytest`!
# See details at:
# https://stackoverflow.com/questions/10253826/path-issue-with-pytest-importerror-no-module-named-yadayadayada

.PHONY: docs

init:
	pip install --user --upgrade pipenv
	pipenv install --dev

check:
	echo "TODO"

test:
	pipenv run pytest

ci:
	pipenv run pytest --cov=aplex tests --cov-config=.coveragerc --cov-append

lint:
	pipenv run flake8

coverage:
	pipenv run coverage report
	pipenv run codecov

publish:
	echo "TODO"
	# pipenv run python setup.py upload
	# TODO(Lun): upload docs.

docs:
	cd docs && pipenv run make html
	sphinx-apidoc -f -o docs/source projectdir
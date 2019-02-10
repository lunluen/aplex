.PHONY: docs

init:
	pip install --upgrade pipenv
	pipenv install --dev
	
	# TODO(Lun): To be deleted. Just a workaround for now considering Windows.
	pipenv install --dev uvloop

check:
	echo "TODO"

test:
	pipenv run pytest

ci:
	pipenv run pytest --cov=aplex tests --cov-config=.coveragerc --cov-append

lint:
	pipenv run flake8

coverage:
	# TODO(Lun): To be deleted. Just a workaround for now for a combined
	# report of py35-37
	pip install tox
	tox
	#pipenv run coverage report
	#pipenv run codecov

docs:
	cd docs && pipenv run make html

publish:
	echo "TODO"
	# pipenv run python setup.py upload
	# TODO(Lun): upload docs.
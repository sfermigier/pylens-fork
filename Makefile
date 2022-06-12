all: test

test:
	pytest tests/test_all.py pylens
	python examples/basic.py
	python examples/advanced.py

lint:
	flake8 pylens

format:
	isort pylens tests examples
	black pylens tests examples


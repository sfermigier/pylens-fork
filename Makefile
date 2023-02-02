all: test

test:
	pytest tests/test_all.py pylens
	python examples/basic.py > /dev/null
	python examples/advanced.py > /dev/null

lint:
	flake8 pylens

format:
	isort pylens tests examples
	black pylens tests examples


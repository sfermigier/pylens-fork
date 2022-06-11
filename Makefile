all: test

test:
	pytest tests/test_all.py pylens
	python examples/basic.py
	python examples/advanced.py

format:
	isort pylens tests examples
	black pylens tests examples


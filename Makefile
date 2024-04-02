all: test lint

test:
	pytest tests pylens

lint:
	ruff check pylens

format:
	isort pylens tests
	black pylens tests


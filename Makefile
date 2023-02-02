all: test lint

test:
	pytest tests pylens

lint:
	ruff pylens

format:
	isort pylens tests
	black pylens tests


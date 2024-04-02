all: test lint

test:
	pytest tests src

lint:
	ruff check src

format:
	isort src tests
	black src tests


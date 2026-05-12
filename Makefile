.PHONY: install dev test lint typecheck format clean

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest -v --tb=short

test-unit:
	pytest -v -k unit

test-integration:
	pytest -v -k integration

lint:
	ruff check kapynis tests

format:
	ruff format kapynis tests
	ruff check --fix kapynis tests

typecheck:
	mypy kapynis

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	rm -rf build dist *.egg-info

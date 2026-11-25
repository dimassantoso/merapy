.PHONY: install dev test test-unit test-integration lint format typecheck ui-build build-binary release clean

PYTHON ?= .venv/bin/python

install:
	$(PYTHON) -m pip install -e "./packages/merapy-taskqueue[all]"
	$(PYTHON) -m pip install -e .

dev:
	$(PYTHON) -m pip install -e "./packages/merapy-taskqueue[all,dev]"
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests/unit packages/merapy-taskqueue/tests -v --tb=short

test-unit:
	$(PYTHON) -m pytest tests/unit packages/merapy-taskqueue/tests -v

ui-build:
	cd packages/merapy-taskqueue/ui && npm run build
	rm -rf src/merapy/codebase/app/task_queue_worker/dashboard_static
	cp -r packages/merapy-taskqueue/src/merapy_taskqueue/dashboard_static src/merapy/codebase/app/task_queue_worker/dashboard_static

test-integration:
	$(PYTHON) -m pytest -v -k integration

lint:
	$(PYTHON) -m ruff check src tests

format:
	$(PYTHON) -m ruff format src tests
	$(PYTHON) -m ruff check --fix src tests

typecheck:
	$(PYTHON) -m mypy src

build-binary:
	$(PYTHON) scripts/build_binary.py

release:
	$(PYTHON) scripts/build_binary.py --with-dist

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	rm -rf build dist *.egg-info

.PHONY: install dev test test-unit test-integration lint format typecheck ui-build build-binary release clean

PYTHON ?= .venv/bin/python
TASKQUEUE_DIR ?= ../merapy-taskqueue
TASKQUEUE_URL ?= git+https://github.com/dimassantoso/merapy-taskqueue.git

install:
	@if [ -d "$(TASKQUEUE_DIR)" ]; then \
		$(PYTHON) -m pip install -e "$(TASKQUEUE_DIR)[all]"; \
	else \
		$(PYTHON) -m pip install "merapy-taskqueue[all] @ $(TASKQUEUE_URL)"; \
	fi
	$(PYTHON) -m pip install -e .

dev:
	@if [ -d "$(TASKQUEUE_DIR)" ]; then \
		$(PYTHON) -m pip install -e "$(TASKQUEUE_DIR)[all,dev]"; \
	else \
		$(PYTHON) -m pip install "merapy-taskqueue[all] @ $(TASKQUEUE_URL)"; \
	fi
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests/unit -v --tb=short

test-unit:
	$(PYTHON) -m pytest tests/unit -v

ui-build:
	$(MAKE) -C "$(TASKQUEUE_DIR)" embed MERAPY_DIR="$(CURDIR)"

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

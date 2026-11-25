.PHONY: ui-install ui-build test lint build

PYTHON ?= ../../.venv/bin/python

ui-install:
	cd ui && npm install

ui-build:
	cd ui && npm run build

test:
	$(PYTHON) -m pytest tests -v

lint:
	$(PYTHON) -m ruff check src tests

build: ui-build
	$(PYTHON) -m build

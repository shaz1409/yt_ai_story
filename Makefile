# AI Story Shorts Factory - Makefile
PYTHON ?= python3

.PHONY: help venv install test lint run-preview run-daily test-hf quality-dashboard

help:
	@echo "Available commands:"
	@echo "  make venv       - Create virtual environment"
	@echo "  make install    - Install dependencies"
	@echo "  make test       - Run tests"
	@echo "  make lint       - Basic lint check"
	@echo "  make run-preview - Run single pipeline (preview mode)"
	@echo "  make run-daily  - Run full daily batch"
	@echo "  make test-hf    - Test Hugging Face image generation"
	@echo "  make quality-dashboard - View quality metrics dashboard"

venv:
	$(PYTHON) -m venv venv

install:
	venv/bin/pip install --upgrade pip
	venv/bin/pip install -r requirements_backend.txt

test:
	venv/bin/pytest -q

lint:
	venv/bin/python -m compileall app

run-preview:
	venv/bin/python run_full_pipeline.py --preview --topic "test story" --style courtroom_drama

run-daily:
	venv/bin/python run_full_pipeline.py --daily-mode --batch-count 5 --date $(shell date +%Y-%m-%d)

test-hf:
	venv/bin/python scripts/test_hf_image.py

quality-dashboard:
	venv/bin/python scripts/quality_dashboard.py


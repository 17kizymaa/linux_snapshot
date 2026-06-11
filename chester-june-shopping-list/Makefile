.PHONY: install test validate generate clean

install:
	pip install -e ".[dev]"

test:
	pytest

validate:
	python scripts/validate_data.py

generate:
	python scripts/output_markdown.py 2026-06-15 --scale 4

freezer-audit:
	python scripts/freezer_audit.py

clean:
	rm -rf .pytest_cache __pycache__ outputs/weekly/*

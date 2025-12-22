.PHONY: format lint test

format:
	python -m black .

lint:
	python -m ruff check .

test:
	pytest

.PHONY: install data test lint

install:
	pip install -e ".[dev,ml,api,ui]"

data:
	python -m sahtekarlik.data.download

test:
	pytest -q

lint:
	ruff check src tests

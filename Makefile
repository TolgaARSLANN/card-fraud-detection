.PHONY: install data quality test lint

install:
	pip install -e ".[dev,ml,api,ui]"

data:
	python -m sahtekarlik.data.download

quality:
	python -m sahtekarlik.data.quality

test:
	pytest -q

lint:
	ruff check src tests

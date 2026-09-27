.PHONY: install data quality test lint

install:
	pip install -e ".[dev,ml,api,ui]"

data:
	python -m card_fraud_detection.data.download

quality:
	python -m card_fraud_detection.data.quality

test:
	pytest -q

lint:
	ruff check src tests

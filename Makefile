.PHONY: install data quality process test lint

install:
	pip install -e ".[dev,ml,api,ui]"

data:
	python -m card_fraud_detection.data.download

quality:
	python -m card_fraud_detection.data.quality

process:
	python -m card_fraud_detection.data.clean

test:
	pytest -q

lint:
	ruff check src tests

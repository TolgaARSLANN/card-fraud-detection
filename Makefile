.PHONY: install data quality process eda features baselines train tune threshold errors final \
        test lint

install:
	pip install -e ".[dev,ml,api,ui]"

data:
	python -m card_fraud_detection.data.download

quality:
	python -m card_fraud_detection.data.quality

process:
	python -m card_fraud_detection.data.clean

eda:
	jupyter nbconvert --to notebook --execute --inplace notebooks/01_eda.ipynb

features:
	python -m card_fraud_detection.features.build

baselines:
	python -m card_fraud_detection.models.baselines

train:
	python -m card_fraud_detection.models.train

tune:
	python -m card_fraud_detection.models.tune

threshold:
	python -m card_fraud_detection.models.threshold

errors:
	python -m card_fraud_detection.evaluation.error_analysis

# Test bir kez değerlendirilir; ikinci çalıştırma reddedilir (bkz. models/final.py)
final:
	python -m card_fraud_detection.models.final

test:
	pytest -q

lint:
	ruff check src tests

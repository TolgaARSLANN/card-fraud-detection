.PHONY: install data quality process eda features baselines train tune threshold errors final \
        explain api consistency panel-data ui space-lock space-data space space-smoke test lint

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

explain:
	jupyter nbconvert --to notebook --execute --inplace notebooks/02_model.ipynb

api:
	uvicorn card_fraud_detection.serving.app:app --port 8000

consistency:
	python -m card_fraud_detection.serving.consistency

panel-data:
	python -m card_fraud_detection.ui.prepare

# Faz 5: Space için demo veri kesiti (build/space/), tutarlılık kontrolüyle
space-data:
	python -m card_fraud_detection.space.data

# Space bağımlılıklarını sabitler: space/requirements.txt
space-lock:
	bash scripts/space_lock.sh

# Space paketini build/space/ altında toplar ve denetler (önce: make space-data)
space:
	python -m card_fraud_detection.space.package

# Paketi Docker ile Space'e yakın kısıtlarla (2 CPU, 3 GB) çalıştırıp üç sekmeyi dener
space-smoke:
	bash scripts/space_smoke.sh

# Tek komut: API çalışmıyorsa başlatır, paneli açar; Ctrl+C ikisini de kapatır
ui:
	bash scripts/ui.sh

test:
	pytest -q

lint:
	ruff check src tests

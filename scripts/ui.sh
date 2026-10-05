#!/usr/bin/env bash
# Paneli tek komutla açar: API çalışmıyorsa arka planda başlatır, hazır olmasını bekler,
# sonra paneli açar. Ctrl+C ile çıkınca yalnızca kendi başlattığı API'yi kapatır; başka bir
# terminalde zaten çalışan bir API varsa ona dokunmaz, onu kullanır.
set -euo pipefail

API_PORT="${API_PORT:-8000}"
UI_PORT="${UI_PORT:-8501}"
API_LOG=".api.log"
health() { curl -s -o /dev/null "http://localhost:${API_PORT}/health"; }

if [ ! -f models/model.joblib ]; then
    echo "Model dosyası yok (models/model.joblib). Önce: make threshold" >&2
    exit 1
fi

if health; then
    echo "API zaten çalışıyor (port ${API_PORT}); o kullanılacak."
else
    echo "API başlatılıyor (port ${API_PORT}, günlük: ${API_LOG})…"
    uvicorn card_fraud_detection.serving.app:app --port "${API_PORT}" > "${API_LOG}" 2>&1 &
    API_PID=$!
    trap 'echo; echo "API kapatılıyor…"; kill "${API_PID}" 2>/dev/null || true' EXIT
    for _ in $(seq 1 90); do
        health && break
        if ! kill -0 "${API_PID}" 2>/dev/null; then
            echo "API başlatılamadı. Ayrıntı: ${API_LOG}" >&2
            exit 1
        fi
        sleep 1
    done
    health || { echo "API 90 saniyede hazır olmadı. Ayrıntı: ${API_LOG}" >&2; exit 1; }
    echo "API hazır."
fi

[ -f data/processed/panel_scores.parquet ] || \
    echo "Not: 'Eşik ve maliyet' sekmesi için skor dosyası yok; oluşturmak için: make panel-data"

echo "Panel: http://localhost:${UI_PORT}   (kapatmak için Ctrl+C)"
# Yalnızca bu bilgisayardan erişilsin (varsayılan tüm ağ arayüzlerini dinler); API de öyle
streamlit run src/card_fraud_detection/ui/app.py --server.port "${UI_PORT}" \
    --server.address localhost --server.headless true

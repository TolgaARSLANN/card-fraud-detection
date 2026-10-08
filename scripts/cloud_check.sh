#!/usr/bin/env bash
# Streamlit Community Cloud yayın klasörünü (build/cloud) Cloud'a benzer biçimde dener:
# temiz python:3.12-slim, packages.txt'teki apt paketleri, requirements.txt, ortam değişkeni
# YOK (demo modu ve bellek havuzu sınırını streamlit_app.py kendisi ayarlamalı), 1 GB bellek.
# Sağlık ucu ve ana sayfa yoklanır, panel giriş dosyası üzerinden üç sekmesiyle denenir.
# Kullanım: make cloud-check   (önce make space-data && make cloud)
#           KEEP=1 make cloud-check    (konteyner açık kalır: tarayıcıda localhost:8596)
set -euo pipefail

NAME="cfd-cloud"
PORT="${PORT:-8596}"
MEM="${MEM:-1g}"
DIR="$(pwd)/build/cloud"

docker rm -f "$NAME" >/dev/null 2>&1 || true
[ "${KEEP:-0}" = 1 ] || trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT
docker run -d --name "$NAME" --cpus=2 --memory="$MEM" -p "$PORT:8501" \
    -v "$DIR:/app:ro" -w /app python:3.12-slim bash -c '
        apt-get update -qq && xargs -a packages.txt apt-get install -y -qq >/dev/null &&
        pip install -q --root-user-action=ignore -r requirements.txt &&
        streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0 \
            --server.headless true' >/dev/null

echo "kurulum ve açılış bekleniyor (bağımlılıklar kuruluyor, birkaç dakika)..."
for _ in $(seq 600); do
    curl -sf "localhost:$PORT/_stcore/health" >/dev/null && break
    docker ps -q --filter "name=$NAME" | grep -q . || { docker logs "$NAME" | tail -30; exit 1; }
    sleep 1
done
curl -sf "localhost:$PORT/_stcore/health" >/dev/null || { docker logs "$NAME" | tail -30; exit 1; }
code=$(curl -s -o /dev/null -w '%{http_code}' "localhost:$PORT/")
[ "$code" = 200 ] || { echo "ana sayfa: HTTP $code"; exit 1; }
echo "sağlık ucu ve ana sayfa: tamam · ortam: DEMO_MODE=$(docker exec "$NAME" printenv DEMO_MODE || echo yok)"
echo "boşta bellek: $(docker stats --no-stream --format '{{.MemUsage}}' "$NAME")"

docker exec -w /app -e PYTHONPATH=/app/src "$NAME" \
    python -m card_fraud_detection.space.smoke --app streamlit_app.py \
    2>/dev/null | tail -1 || { echo "duman testi başarısız"; exit 1; }
echo "duman testi sonrası bellek: $(docker stats --no-stream --format '{{.MemUsage}}' "$NAME")"
echo "CLOUD KONTROLÜ GEÇTİ"

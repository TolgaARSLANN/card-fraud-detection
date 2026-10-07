#!/usr/bin/env bash
# Space paketinin duman testi: imajı kurar, konteyneri Space'e yakın kısıtlarla başlatır,
# sağlık ucunu ve ana sayfayı yoklar, konteynerin içinde paneli üç sekmesiyle dener.
# Kullanım: make space-smoke   (önce make space-data && make space)
#           CPUS=2 MEM=3g PORT=8599 make space-smoke
set -euo pipefail

IMAGE="${IMAGE:-card-fraud-space}"
NAME="cfd-space-smoke"
CPUS="${CPUS:-2}"
MEM="${MEM:-3g}"
PORT="${PORT:-8599}"
DIR="${DIR:-build/space}"

docker build -q -t "$IMAGE" "$DIR" >/dev/null
docker rm -f "$NAME" >/dev/null 2>&1 || true
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT

t0=$(date +%s%N)
docker run -d --name "$NAME" --cpus="$CPUS" --memory="$MEM" -p "$PORT:8501" "$IMAGE" >/dev/null
for _ in $(seq 180); do
    curl -sf "localhost:$PORT/_stcore/health" >/dev/null && break
    sleep 1
done
curl -sf "localhost:$PORT/_stcore/health" >/dev/null || { docker logs "$NAME" | tail -30; exit 1; }
echo "sağlık ucu: $(( ($(date +%s%N) - t0) / 1000000 )) ms"

code=$(curl -s -o /dev/null -w '%{http_code}' "localhost:$PORT/")
[ "$code" = 200 ] || { echo "ana sayfa: HTTP $code"; exit 1; }
echo "ana sayfa: HTTP 200"
uid=$(docker exec "$NAME" id -u)
[ "$uid" != 0 ] || { echo "konteyner root ile çalışıyor"; exit 1; }
echo "kullanıcı: uid $uid, DEMO_MODE=$(docker exec "$NAME" printenv DEMO_MODE)"

docker exec "$NAME" python -m card_fraud_detection.space.smoke
echo "DUMAN TESTİ GEÇTİ"

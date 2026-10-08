#!/usr/bin/env bash
# Space ölçümü: konteyneri kısıtlarla başlatır; sağlık ucuna kadar geçen süreyi ve boştaki
# belleği ölçer, sonra konteynerin içinde demo arka ucunu ölçer (space/measure.py).
# Kullanım: make space-measure                 (2 CPU, 3 GB; önce make space)
#           CPUS=8 MEM=0 SESSIONS=10 PER_SESSION=2000 make space-measure
set -euo pipefail

IMAGE="${IMAGE:-card-fraud-space}"
NAME="cfd-space-measure"
CPUS="${CPUS:-2}"
MEM="${MEM:-3g}"
PORT="${PORT:-8598}"
SESSIONS="${SESSIONS:-10}"
PER_SESSION="${PER_SESSION:-2000}"
EXTRA="${EXTRA:-}"

docker build -q -t "$IMAGE" build/space >/dev/null
docker rm -f "$NAME" >/dev/null 2>&1 || true
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT
limits=(--cpus="$CPUS")
[ "$MEM" = 0 ] || limits+=(--memory="$MEM")

t0=$(date +%s%N)
docker run -d --name "$NAME" "${limits[@]}" -p "$PORT:8501" "$IMAGE" >/dev/null
until curl -sf "localhost:$PORT/_stcore/health" >/dev/null; do sleep 0.2; done
echo "kısıt: cpus=$CPUS memory=$MEM"
echo "sağlık_ucu_ms: $(( ($(date +%s%N) - t0) / 1000000 ))"
sleep 5
echo "boşta_bellek: $(docker stats --no-stream --format '{{.MemUsage}}' "$NAME")"
docker exec "$NAME" python -m card_fraud_detection.space.measure \
    --sessions "$SESSIONS" --per-session "$PER_SESSION" $EXTRA | grep -E '^(\{|SONUC)'
echo "ölçüm_sonrası_konteyner_bellek: $(docker stats --no-stream --format '{{.MemUsage}}' "$NAME")"

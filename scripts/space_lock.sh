#!/usr/bin/env bash
# Space bağımlılıklarını sabitler: panelin çalışma zamanı paketleri, bu projenin test edildiği
# sürümlerle (.venv) temiz bir ortama kurulur; tüm bağımlılık zinciri space/requirements.txt'e
# yazılır. FastAPI/uvicorn bilerek yoktur (Space'te API açılmaz).
# Kullanım: make space-lock   (proje kökünde, .venv etkinken)
set -euo pipefail

RUNTIME=(numpy pandas pyarrow scikit-learn lightgbm shap streamlit plotly httpx joblib)
pins=()
for pkg in "${RUNTIME[@]}"; do
    pins+=("${pkg}==$(python -c "import importlib.metadata as m; print(m.version('${pkg}'))")")
done

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
python3.12 -m venv "$tmp/venv" 2>/dev/null || python3 -m venv "$tmp/venv"
"$tmp/venv/bin/pip" install -q --disable-pip-version-check "${pins[@]}"
{
    echo "# Space çalışma zamanı bağımlılıkları (tüm zincir sabit). Üreten: make space-lock"
    echo "# Python $("$tmp/venv/bin/python" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
    "$tmp/venv/bin/pip" freeze --disable-pip-version-check | sort -f
} > space/requirements.txt
echo "[ok] space/requirements.txt ($(grep -vc '^#' space/requirements.txt) paket)"

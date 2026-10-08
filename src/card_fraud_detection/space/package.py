"""Yayın paketlerini build/ altında toplar ve içeriklerini denetler.

Kullanım (önce make space-data):
    python -m card_fraud_detection.space.package               # make space → build/space/
    python -m card_fraud_detection.space.package --target cloud  # make cloud → build/cloud/

- space: Hugging Face Docker Space (README başlık bilgileri, Dockerfile, LFS ayarları).
- cloud: Streamlit Community Cloud. Kökteki streamlit_app.py demo modunu ve bellek havuzu
  sınırını ayarlayıp paneli çalıştırır; ayrı, herkese açık bir yayın reposuna gönderilir.

İkisinde de: sabit bağımlılıklar, Streamlit ayarları, kod (src/), lisans, demo veri kesiti ve
model dosyaları. Ana GitHub reposuna veri ya da model eklenmez (build/ git dışında).
Denetim: yalnızca izin verilen veri sütunları, takma kart numaraları, yasak dosya yok, boyut.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd

from card_fraud_detection.config import CARD_COL, ROOT, TARGET, TIME_COL
from card_fraud_detection.data.demo import DEMO_COLUMNS
from card_fraud_detection.space.data import MODEL_FILES, OUT_DIR, luhn_valid

TEMPLATE = ROOT / "space"
CLOUD_DIR = ROOT / "build" / "cloud"
SIZE_LIMIT_MB = 100
SCORE_COLUMNS = ["tx_id", TIME_COL, "amt", TARGET, "p"]
DATA_FILES = {"data/processed/transactions.parquet": DEMO_COLUMNS,
              "data/processed/panel_scores.parquet": SCORE_COLUMNS}
FORBIDDEN_NAMES = {"kaggle.json", ".env", "features.parquet", "optuna.db"}
COMMON = [".streamlit/config.toml", "LICENSE", "README.md", "requirements.txt",
          "src/card_fraud_detection/ui/app.py", *DATA_FILES,
          *(f"models/{m}" for m in MODEL_FILES)]
REQUIRED = {"space": [*COMMON, "Dockerfile", "pyproject.toml"],
            "cloud": [*COMMON, "streamlit_app.py", "packages.txt"]}


def _copy_code(out: Path) -> None:
    src = out / "src" / "card_fraud_detection"
    if src.exists():
        shutil.rmtree(src)
    shutil.copytree(ROOT / "src" / "card_fraud_detection", src,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (out / ".streamlit").mkdir(parents=True, exist_ok=True)
    shutil.copy2(TEMPLATE / "config.toml", out / ".streamlit" / "config.toml")
    shutil.copy2(ROOT / "LICENSE", out / "LICENSE")
    shutil.copy2(TEMPLATE / "requirements.txt", out / "requirements.txt")


def assemble(out: Path = OUT_DIR) -> None:
    for name in ["Dockerfile", "README.md", ".gitattributes"]:
        shutil.copy2(TEMPLATE / name, out / name)
    shutil.copy2(ROOT / "pyproject.toml", out / "pyproject.toml")
    _copy_code(out)


def assemble_cloud(out: Path = CLOUD_DIR, data_from: Path = OUT_DIR) -> None:
    """Cloud yayın klasörü; veri ve model `make space-data` çıktısından kopyalanır. Klasördeki
    .git (yayın reposu) korunur."""
    out.mkdir(parents=True, exist_ok=True)
    for name in ["streamlit_app.py", "README.md", "packages.txt"]:  # packages.txt: apt (LightGBM)
        shutil.copy2(TEMPLATE / "cloud" / name, out / name)
    _copy_code(out)
    for sub in ["data", "models"]:
        if (out / sub).exists():
            shutil.rmtree(out / sub)
        shutil.copytree(data_from / sub, out / sub)


def _files(out: Path) -> list[Path]:
    return [f for f in out.rglob("*") if f.is_file() and ".git" not in f.relative_to(out).parts]


def verify(out: Path = OUT_DIR, target: str = "space") -> list[str]:
    """Paket sorunları (boş liste: sorun yok)."""
    problems = [f"eksik: {p}" for p in REQUIRED[target] if not (out / p).exists()]
    for rel, allowed in DATA_FILES.items():
        if (out / rel).exists():
            cols = list(pd.read_parquet(out / rel).columns)
            if cols != allowed:
                problems.append(f"{rel}: sütunlar {cols}, beklenen {allowed}")
    tx_path = out / "data/processed/transactions.parquet"
    if tx_path.exists():
        cards = pd.read_parquet(tx_path, columns=[CARD_COL])[CARD_COL].unique()
        if any(len(str(c)) != 7 or luhn_valid(int(c)) for c in cards):
            problems.append("takma olmayan ya da Luhn'dan geçen kart numarası var")
    files = _files(out)
    rels = [f.relative_to(out).as_posix() for f in files if f.suffix in {".parquet", ".csv"}]
    problems += [f"beklenmeyen veri dosyası: {r}" for r in rels if r not in DATA_FILES]
    problems += [f"yasak dosya: {f.name}" for f in files if f.name in FORBIDDEN_NAMES]
    size = sum(f.stat().st_size for f in files) / 1e6
    if size > SIZE_LIMIT_MB:
        problems.append(f"toplam boyut {size:.1f} MB > {SIZE_LIMIT_MB} MB")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", choices=["space", "cloud"], default="space")
    args = parser.parse_args()
    out = OUT_DIR if args.target == "space" else CLOUD_DIR
    (assemble if args.target == "space" else assemble_cloud)(out)
    problems = verify(out, args.target)
    files = _files(out)
    for f in sorted(files, key=lambda f: -f.stat().st_size)[:6]:
        print(f"  {f.stat().st_size / 1e6:6.1f} MB  {f.relative_to(out).as_posix()}")
    print(f"[{'ok' if not problems else 'HATA'}] {out}: {len(files)} dosya, "
          f"{sum(f.stat().st_size for f in files) / 1e6:.1f} MB")
    for p in problems:
        print("  -", p)
    raise SystemExit(1 if problems else 0)


if __name__ == "__main__":
    main()

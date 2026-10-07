"""Space paketini build/space/ altında toplar ve içeriğini denetler.

Kullanım:
    python -m card_fraud_detection.space.package     # make space (önce make space-data)

Paket: Space README'si (başlık bilgileri), Dockerfile, sabit bağımlılıklar, LFS ayarları,
Streamlit ayarları, kod (src/), lisans, demo veri kesiti ve model dosyaları. Paket ayrı bir
Space reposuna yüklenir; GitHub reposuna veri ya da model eklenmez (build/ git dışında).
Denetim: yalnızca izin verilen veri sütunları, takma kart numaraları, toplam boyut sınırı.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from card_fraud_detection.config import CARD_COL, ROOT, TARGET, TIME_COL
from card_fraud_detection.data.demo import DEMO_COLUMNS
from card_fraud_detection.space.data import MODEL_FILES, OUT_DIR, luhn_valid

TEMPLATE = ROOT / "space"
SIZE_LIMIT_MB = 100
SCORE_COLUMNS = ["tx_id", TIME_COL, "amt", TARGET, "p"]
DATA_FILES = {"data/processed/transactions.parquet": DEMO_COLUMNS,
              "data/processed/panel_scores.parquet": SCORE_COLUMNS}
FORBIDDEN_NAMES = {"kaggle.json", ".env", "features.parquet", "optuna.db"}


def assemble(out: Path = OUT_DIR) -> None:
    for name in ["Dockerfile", "README.md", ".gitattributes", "requirements.txt"]:
        shutil.copy2(TEMPLATE / name, out / name)
    (out / ".streamlit").mkdir(exist_ok=True)
    shutil.copy2(TEMPLATE / "config.toml", out / ".streamlit" / "config.toml")
    for name in ["pyproject.toml", "LICENSE"]:
        shutil.copy2(ROOT / name, out / name)
    src = out / "src" / "card_fraud_detection"
    if src.exists():
        shutil.rmtree(src)
    shutil.copytree(ROOT / "src" / "card_fraud_detection", src,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def verify(out: Path = OUT_DIR) -> list[str]:
    """Paket sorunları (boş liste: sorun yok)."""
    problems = []
    required = ["Dockerfile", "README.md", "requirements.txt", ".streamlit/config.toml",
                "LICENSE", "src/card_fraud_detection/ui/app.py",
                *DATA_FILES, *(f"models/{m}" for m in MODEL_FILES)]
    problems += [f"eksik: {p}" for p in required if not (out / p).exists()]
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
    files = [f for f in out.rglob("*") if f.is_file()]
    rels = [f.relative_to(out).as_posix() for f in files if f.suffix in {".parquet", ".csv"}]
    extra = [r for r in rels if r not in DATA_FILES]
    problems += [f"beklenmeyen veri dosyası: {e}" for e in extra]
    problems += [f"yasak dosya: {f.name}" for f in files if f.name in FORBIDDEN_NAMES]
    size = sum(f.stat().st_size for f in files) / 1e6
    if size > SIZE_LIMIT_MB:
        problems.append(f"toplam boyut {size:.1f} MB > {SIZE_LIMIT_MB} MB")
    return problems


def main() -> None:
    assemble()
    problems = verify()
    files = [f for f in OUT_DIR.rglob("*") if f.is_file()]
    big = sorted(files, key=lambda f: -f.stat().st_size)[:6]
    for f in big:
        print(f"  {f.stat().st_size / 1e6:6.1f} MB  {f.relative_to(OUT_DIR).as_posix()}")
    print(f"[{'ok' if not problems else 'HATA'}] {OUT_DIR}: {len(files)} dosya, "
          f"{sum(f.stat().st_size for f in files) / 1e6:.1f} MB")
    for p in problems:
        print("  -", p)
    raise SystemExit(1 if problems else 0)


if __name__ == "__main__":
    main()

"""Streamlit Community Cloud yayın klasörü: içerik denetimi ve bellek havuzu ayarı."""

import sys

import pandas as pd
import pytest

from card_fraud_detection.data.demo import DEMO_COLUMNS
from card_fraud_detection.space import package
from card_fraud_detection.space.data import MODEL_FILES, pseudonyms
from card_fraud_detection.space.memory import limit_malloc_arenas


def fake_build(root, extra_column=None):
    """make space-data çıktısının küçük bir benzeri (sentetik)."""
    processed, models = root / "data" / "processed", root / "models"
    processed.mkdir(parents=True)
    models.mkdir()
    cards = list(pseudonyms([4_000_000_000_000_001, 4_000_000_000_000_002]).values())
    tx = pd.DataFrame({c: [1, 2] for c in DEMO_COLUMNS})
    tx["cc_num"] = cards
    if extra_column:
        tx[extra_column] = ["x", "y"]
    tx.to_parquet(processed / "transactions.parquet")
    pd.DataFrame({c: [1] for c in package.SCORE_COLUMNS}).to_parquet(
        processed / "panel_scores.parquet")
    for name in MODEL_FILES:
        (models / name).write_text("{}")
    return root


def test_cloud_package_is_complete_and_clean(tmp_path):
    out = tmp_path / "cloud"
    package.assemble_cloud(out, fake_build(tmp_path / "space"))
    assert package.verify(out, "cloud") == []
    assert (out / "packages.txt").read_text().split() == ["libgomp1"]
    entry = (out / "streamlit_app.py").read_text(encoding="utf-8")
    assert 'os.environ["DEMO_MODE"] = "1"' in entry and "limit_malloc_arenas(2)" in entry
    assert ".setdefault(" not in entry
    assert "fastapi" not in (out / "requirements.txt").read_text().lower()


def test_cloud_package_keeps_deploy_repo_and_rejects_personal_columns(tmp_path):
    out = tmp_path / "cloud"
    (out / ".git").mkdir(parents=True)
    (out / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    package.assemble_cloud(out, fake_build(tmp_path / "space", extra_column="dob"))
    assert (out / ".git" / "HEAD").exists()                  # yayın reposunun geçmişi korunur
    problems = package.verify(out, "cloud")
    assert any("transactions.parquet: sütunlar" in p for p in problems)


def test_cloud_entry_forces_demo_mode_over_secrets(tmp_path):
    """Cloud'da kök seviyedeki secrets ortam değişkeni olarak gelir. DEMO_MODE=0 ya da başka bir
    proje kökü verilse de giriş dosyası demo modunda, kendi klasöründen ve 20 oturum sınırıyla
    açılmalı. Gerçek giriş dosyası, gerçek config ve bellek modülü; panel yerine ortamı yazan
    küçük bir betik çalıştırılır."""
    import json
    import os
    import shutil
    import subprocess

    src = package.ROOT / "src" / "card_fraud_detection"
    pkg = tmp_path / "src" / "card_fraud_detection"
    (pkg / "space").mkdir(parents=True)
    (pkg / "ui").mkdir()
    for rel in ["__init__.py", "config.py", "space/__init__.py", "space/memory.py"]:
        shutil.copy2(src / rel, pkg / rel)
    (pkg / "ui" / "app.py").write_text(
        "import json, os\n"
        "from card_fraud_detection import config\n"
        "print('ENV' + json.dumps({'demo': config.demo_mode(), 'root': str(config.ROOT),\n"
        "    'sessions': config.DEMO_MAX_SESSIONS, 'omp': os.environ['OMP_NUM_THREADS']}))\n")
    shutil.copy2(package.TEMPLATE / "cloud" / "streamlit_app.py", tmp_path / "streamlit_app.py")

    env = {**os.environ, "DEMO_MODE": "0", "DEMO_MAX_SESSIONS": "99", "OMP_NUM_THREADS": "8",
           "CARD_FRAUD_ROOT": "/baska/yer"}
    out = subprocess.run([sys.executable, str(tmp_path / "streamlit_app.py")], env=env,
                         capture_output=True, text=True, check=True)
    got = json.loads(next(x for x in out.stdout.splitlines() if x.startswith("ENV"))[3:])
    assert got == {"demo": True, "root": str(tmp_path.resolve()), "sessions": 20, "omp": "1"}


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="glibc yalnızca Linux'ta")
def test_limit_malloc_arenas_on_glibc():
    assert limit_malloc_arenas(2) is True

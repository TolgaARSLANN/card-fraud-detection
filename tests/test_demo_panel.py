"""Demo modu: panel duman testi (sentetik veri ve model, ayrı süreç).

Panel, proje kökünü içe aktarma anında okuduğu için test ayrı bir süreçte, geçici bir proje
köküyle (CARD_FRAUD_ROOT) ve DEMO_MODE=1 ile çalışır. Gerçek veri gerekmez; CI'da da koşar.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import joblib
import lightgbm as lgb
import pandas as pd
import pytest
from conftest import TIME, synthetic_transactions

from card_fraud_detection.config import TEST_START
from card_fraud_detection.features.build import FEATURES, build_features, fit_stats
from card_fraud_detection.models.calibration import Calibrator

APP = Path(__file__).parents[1] / "src/card_fraud_detection/ui/app.py"
N_TEST = 150

SCRIPT = r"""
import json, sys
import card_fraud_detection.config as config
config.DEMO_STREAM_LIMIT = 60                       # sınırı küçült: demo_backend bunu alır
from streamlit import config as st_config
from streamlit.testing.v1 import AppTest

def button(at, label):
    return next(b for b in at.button if b.label == label)

def mast(at):
    return next(m.value for m in at.markdown if "işlem geçmişi" in m.value)

out = {}
a = AppTest.from_file(sys.argv[1], default_timeout=120).run()
out["exceptions"] = [e.value for e in a.exception]
text = " ".join(m.value for m in a.markdown)
out["notice"] = "tamamen sentetik" in text and "Gerçek kart numarası" in text
out["resync_button"] = any("yeniden kur" in b.label for b in a.button)
out["error_details"] = st_config.get_option("client.showErrorDetails")
b = AppTest.from_file(sys.argv[1], default_timeout=120).run()
mast_b0 = mast(b)
button(a, "Sonraki →").click().run()
button(a, "Sonraki →").click().run()                # 50 + 10 (sınır 60)
out["a_after"] = mast(a)
out["next_disabled"] = button(a, "Sonraki →").disabled
out["b_unchanged"] = mast(b.run()) == mast_b0
out["b_mast"] = mast_b0
a.radio[0].set_value("Elle işlem gir").run()
out["card_inputs"] = [n.label for n in a.number_input]
out["text_inputs"] = [t.label for t in a.text_input]
card = next(s for s in a.selectbox if s.label == "Kart (sentetik)")
out["card_options"] = list(card.options)[:3]
next(s for s in a.selectbox if s.label == "Kategori").set_value("shopping_net")
next(b for b in a.button if "Skorla" in b.label).click().run()
out["manual_exceptions"] = [e.value for e in a.exception]
out["manual_ok"] = any("Karar" in m.value for m in a.markdown)
print("JSON" + json.dumps(out, ensure_ascii=False))
"""


@pytest.fixture(scope="module")
def demo_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("demo_root")
    tx = synthetic_transactions(n=900)
    times = pd.Timestamp(TEST_START) + pd.to_timedelta(range(0, 600 * N_TEST, 600), unit="s")
    tx.loc[tx.index[-N_TEST:], TIME] = times
    tx.loc[tx.index[-N_TEST:], "split"] = "test"
    train = tx[tx["split"] == "train"]
    stats = fit_stats(train)
    model = lgb.LGBMClassifier(n_estimators=20, num_leaves=7, verbose=-1).fit(
        build_features(train, stats)[FEATURES], train["is_fraud"])
    (root / "models").mkdir()
    (root / "data/processed").mkdir(parents=True)
    joblib.dump({"model": model, "calibrator": Calibrator("ham").state(), "features": FEATURES},
                root / "models/model.joblib")
    (root / "models/decision.json").write_text(json.dumps(
        {"kural": "beklenen maliyet", "esik": None, "inceleme_ucreti": 10.0}))
    (root / "models/feature_stats.json").write_text(stats.to_json(), encoding="utf-8")
    tx.to_parquet(root / "data/processed/transactions.parquet", index=False)
    return root


@pytest.fixture(scope="module")
def run(demo_root):
    env = {**os.environ, "DEMO_MODE": "1", "CARD_FRAUD_ROOT": str(demo_root)}
    out = subprocess.run([sys.executable, "-c", SCRIPT, str(APP)], capture_output=True,
                         text=True, env=env, timeout=600)
    assert out.returncode == 0, out.stderr[-3000:]
    line = next(x for x in out.stdout.splitlines() if x.startswith("JSON"))
    return json.loads(line[4:])


def test_demo_panel_opens_with_notice_and_hidden_details(run):
    assert run["exceptions"] == [] and run["notice"]
    assert run["error_details"] == "none"
    assert not run["resync_button"]                 # ortak durumu eşitleme / sıfırlama yok


def test_demo_panel_sessions_are_isolated_and_limited(run):
    assert run["b_unchanged"], (run["a_after"], run["b_mast"])
    assert run["a_after"] != run["b_mast"]
    assert run["next_disabled"]                     # oturum sınırına (60) ulaşıldı


def test_demo_panel_has_no_free_card_entry(run):
    assert "Kart numarası" not in run["card_inputs"] and "Satıcı" not in run["text_inputs"]
    assert run["card_options"] and all(o.startswith("Kart ") and "••••" in o
                                       for o in run["card_options"])
    assert run["manual_exceptions"] == [] and run["manual_ok"]

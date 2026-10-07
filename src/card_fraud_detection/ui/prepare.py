"""Panelin "Eşik ve maliyet" sekmesi için test dönemi olasılıklarını önceden hesaplar.

Kullanım:
    python -m card_fraud_detection.ui.prepare     # -> data/processed/panel_scores.parquet

Olasılıklar Faz 3.5'teki test değerlendirmesiyle aynı model ve kalibrasyonla hesaplanır. Bu
yalnızca gösterimdir; model, kalibrasyon veya eşikle ilgili hiçbir karar vermez.
"""

from __future__ import annotations

import joblib
import pandas as pd

from card_fraud_detection.config import MODEL_PATH, PROCESSED_DIR, TARGET, TIME_COL
from card_fraud_detection.features.build import FEATURES_PATH
from card_fraud_detection.models.calibration import Calibrator

PANEL_SCORES = PROCESSED_DIR / "panel_scores.parquet"


def compute_scores(features_path=FEATURES_PATH, model_path=MODEL_PATH) -> pd.DataFrame:
    """Test dönemi: tx_id, zaman, tutar, etiket ve kalibre olasılık (kart numarası yok)."""
    bundle = joblib.load(model_path)
    cal = Calibrator.from_state(bundle["calibrator"])
    cols = ["tx_id", TIME_COL, "amt", TARGET, *bundle["features"]]
    test = pd.read_parquet(features_path, columns=list(dict.fromkeys(cols)),
                           filters=[("split", "==", "test")])
    p = cal.transform(bundle["model"].predict_proba(test[bundle["features"]])[:, 1])
    return test[["tx_id", TIME_COL, "amt", TARGET]].assign(p=p.astype("float64"))


def main() -> None:
    out = compute_scores()
    out.to_parquet(PANEL_SCORES, index=False)
    print(f"[ok] {PANEL_SCORES} ({len(out):,} işlem)")


if __name__ == "__main__":
    main()

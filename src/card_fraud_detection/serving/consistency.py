"""Eğitim/servis tutarlılığını gerçek veride doğrular.

Kullanım:
    python -m card_fraud_detection.serving.consistency [--n 2000]

Servis, test dönemi başlangıcına kadarki geçmişle yüklenir; test döneminin ilk `n` işlemi
sırayla (tx_id sırası) servisten geçirilir. Her işlemin özellikleri `features.parquet` ile,
olasılığı ise aynı modelin kaydedilmiş özelliklerden hesapladığı olasılıkla karşılaştırılır.
Bu bir kod doğruluğu kontrolüdür; model, kalibrasyon veya eşikle ilgili hiçbir karar vermez.
"""

from __future__ import annotations

import argparse
import time

import numpy as np
import pandas as pd

from card_fraud_detection.config import TIME_COL
from card_fraud_detection.data.clean import OUT_PATH as TRANSACTIONS_PATH
from card_fraud_detection.features.build import FEATURES, FEATURES_PATH
from card_fraud_detection.serving.service import ScoringService

INPUT = [TIME_COL, "cc_num", "amt", "category", "merchant"]


def compare(online: pd.DataFrame, batch: pd.DataFrame) -> pd.Series:
    """Özellik başına en büyük mutlak fark (kategori için uyuşmayan satır sayısı)."""
    out = {}
    for col in FEATURES:
        if col == "category":
            out[col] = float((online[col].astype(str) != batch[col].astype(str)).sum())
        else:
            a, b = online[col].astype(float).to_numpy(), batch[col].astype(float).to_numpy()
            both_nan = np.isnan(a) & np.isnan(b)
            one_nan = np.isnan(a) ^ np.isnan(b)
            diff = np.where(both_nan, 0.0, np.abs(a - b))
            out[col] = np.inf if one_nan.any() else float(np.nanmax(diff))
    return pd.Series(out)


def check(service: ScoringService, tx: pd.DataFrame, batch: pd.DataFrame):
    """İşlemleri sırayla servisten geçirir (skorla ve geçmişe ekle); özellikleri `batch` ile,
    olasılıkları aynı modelin `batch` üzerindeki olasılığıyla karşılaştırır.
    Dönen: (özellik farkları, en büyük olasılık farkı, istek süreleri ms, tutarlı mı)."""
    rows, probs, seconds = [], [], []
    for _, r in tx.iterrows():
        t = r[INPUT].to_dict()
        t0 = time.perf_counter()
        rows.append(service.features_for(t)[FEATURES].iloc[0])
        probs.append(service.score(t)["olasilik"])          # skorla ve geçmişe ekle
        seconds.append(time.perf_counter() - t0)
    online = pd.DataFrame(rows).reset_index(drop=True)
    batch = batch.reset_index(drop=True)

    diffs = compare(online, batch)
    raw = service.model.predict_proba(batch[FEATURES])[:, 1]
    p_batch = service.calibrator.transform(raw)
    p_diff = float(np.max(np.abs(np.array(probs) - p_batch)))
    ok = bool(diffs.max() < 1e-9) and p_diff < 1e-12
    return diffs, p_diff, 1000 * np.array(seconds), ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=2000)
    args = parser.parse_args()

    service = ScoringService.load()
    print(f"Servis: {service.store.n_cards} kart, {service.store.n_transactions:,} işlem geçmişi")
    tx = pd.read_parquet(TRANSACTIONS_PATH, columns=["tx_id", "split", *INPUT],
                         filters=[("split", "==", "test")]).sort_values("tx_id").head(args.n)
    batch = pd.read_parquet(FEATURES_PATH, columns=["tx_id", *FEATURES],
                            filters=[("split", "==", "test")]).set_index("tx_id").loc[tx["tx_id"]]

    diffs, p_diff, ms, ok = check(service, tx, batch)
    print(f"{len(tx):,} işlem · özellik başına en büyük fark:")
    print(diffs.to_string())
    print(f"Olasılık farkı (en büyük): {p_diff:.2e}")
    print(f"İstek süresi (özellik + skor + açıklama): medyan {np.median(ms):.1f} ms, "
          f"%95 {np.percentile(ms, 95):.1f} ms")
    print("TUTARLI" if ok else "TUTARSIZ")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()

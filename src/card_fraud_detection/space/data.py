"""Space için demo veri kesiti: yalnızca gerekli sütunlar, takma kart numaraları, tutarlılık.

Kullanım:
    python -m card_fraud_detection.space.data [--out build/space] [--check-n 500]

Kesit 2019-01-01'den SLICE_END'e kadar tüm işlemleri içerir. Kartın tüm geçmişi gerekir:
pencere özellikleri (1 saat / 24 saat / 7 gün) için 7 gün yeterli olsa da kartın geçmiş işlem
sayısı, kartın ortalamasına göre tutar ve "satıcıyla / kategoride ilk işlem" özellikleri kartın
TÜM geçmişine bakar; geçmiş kırpılırsa bu özellikler raporlanandan farklı hesaplanır.

Kart numaraları tutarlı takma numaralarla değiştirilir (aynı kart → hep aynı numara). Takma
numaralar 7 hanelidir (kart numaraları 12-19 hane) ve hiçbiri Luhn kontrolünden geçmez; gerçek
bir kart numarasına benzemezler. Eşleme tablosu pakete yazılmaz.

Paket üretilmeden önce kesit doğrulanır: her sabit başlangıçtan sonraki ilk N işlem, panelin
kullandığı yoldan (başlangıç katmanı + oturum katmanı, takma numaralarla) skorlanır; özellikler
tam veriyle hesaplanan `features.parquet` ile, olasılıklar paneldeki skorlarla birebir aynı
olmalıdır. Model, kalibrasyon ve karar kuralı değişmez; yalnızca kopyalanır.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from card_fraud_detection.config import CARD_COL, MODELS_DIR, ROOT, TIME_COL
from card_fraud_detection.data.clean import OUT_PATH as TRANSACTIONS_PATH
from card_fraud_detection.data.demo import demo_frame
from card_fraud_detection.features.build import FEATURES, FEATURES_PATH

# Son sabit başlangıç 15 Ağustos 22:00; ondan sonraki 2.000. işlem 16 Ağustos 14:42'de geliyor
SLICE_END = "2020-08-17"
PSEUDO_START = 1_000_001
MODEL_FILES = ["model.joblib", "decision.json", "feature_stats.json", "metadata.json"]
OUT_DIR = ROOT / "build" / "space"


def luhn_valid(number: int) -> bool:
    digits = [int(d) for d in str(number)][::-1]
    total = sum(d if i % 2 == 0 else (2 * d - 9 if 2 * d > 9 else 2 * d)
                for i, d in enumerate(digits))
    return total % 10 == 0


def pseudonyms(cards) -> dict[int, int]:
    """Kart → takma numara. Sıralı ve belirlenimci (aynı veri → aynı eşleme); 7 haneli,
    Luhn kontrolünden geçmeyen sayılar."""
    out, candidate = {}, PSEUDO_START
    for card in sorted({int(c) for c in cards}):
        while luhn_valid(candidate):
            candidate += 1
        out[card] = candidate
        candidate += 1
    if out and max(out.values()) > 9_999_999:
        raise ValueError("Takma numaralar 7 haneyi aştı")
    return out


def make_slice(transactions: pd.DataFrame, end: str = SLICE_END) -> pd.DataFrame:
    """Kesit: yalnızca demo sütunları, `end` öncesi, takma kart numaralarıyla."""
    frame = demo_frame(transactions[transactions[TIME_COL] < pd.Timestamp(end)])
    frame[CARD_COL] = frame[CARD_COL].map(pseudonyms(frame[CARD_COL])).astype("int64")
    return frame.sort_values("tx_id").reset_index(drop=True)


def check(service, features: pd.DataFrame, scores: pd.DataFrame, stream: pd.DataFrame,
          presets: dict[str, str | None], n: int) -> pd.DataFrame:
    """Her başlangıçtan sonraki ilk `n` işlemi panelin yolundan skorlar; tam veriyle hesaplanan
    özelliklerle (`features`, tx_id dizinli) ve skorlarla (`scores`, tx_id dizinli) karşılaştırır.
    Dönen tablo: başlangıç başına işlem sayısı, en büyük özellik farkı, en büyük olasılık farkı."""
    from card_fraud_detection.serving.consistency import compare
    from card_fraud_detection.serving.history import OverlayHistoryStore
    from card_fraud_detection.ui.demo_backend import SharedBases

    bases, rows = SharedBases(service, presets), []
    cols = [TIME_COL, CARD_COL, "amt", "category", "merchant"]
    for key, until in presets.items():
        start = stream[TIME_COL].searchsorted(pd.Timestamp(until)) if until else 0
        part = stream.iloc[start:start + n]
        session = OverlayHistoryStore(bases(key))
        online, probs = [], []
        for _, r in part.iterrows():
            tx = r[cols].to_dict()
            online.append(service.features_for(tx, session)[FEATURES].iloc[0])
            probs.append(service.score(tx, store=session)["olasilik"])
        diffs = compare(pd.DataFrame(online).reset_index(drop=True),
                        features.loc[part["tx_id"], FEATURES].reset_index(drop=True))
        p_diff = float(np.max(np.abs(np.array(probs) - scores.loc[part["tx_id"], "p"].to_numpy())))
        rows.append({"başlangıç": key, "işlem": len(part), "özellik farkı": float(diffs.max()),
                     "olasılık farkı": p_diff})
    return pd.DataFrame(rows)


def build(out: Path = OUT_DIR, check_n: int = 500) -> pd.DataFrame:
    from card_fraud_detection.serving.service import ScoringService
    from card_fraud_detection.ui.demo_backend import PRESETS
    from card_fraud_detection.ui.prepare import compute_scores

    processed, models = out / "data" / "processed", out / "models"
    processed.mkdir(parents=True, exist_ok=True)
    models.mkdir(parents=True, exist_ok=True)
    full = pd.read_parquet(TRANSACTIONS_PATH)
    demo = make_slice(full)
    demo.to_parquet(processed / "transactions.parquet", index=False)
    scores = compute_scores()
    scores.to_parquet(processed / "panel_scores.parquet", index=False)
    for name in MODEL_FILES:
        shutil.copy2(MODELS_DIR / name, models / name)
    print(f"[ok] kesit: {len(demo):,} işlem, {demo[CARD_COL].nunique()} kart, "
          f"sütunlar {list(demo.columns)}")

    service = ScoringService.load(models, processed / "transactions.parquet")
    service.num_threads = 1
    stream = demo[demo["split"] == "test"].sort_values("tx_id").reset_index(drop=True)
    features = pd.read_parquet(FEATURES_PATH, columns=["tx_id", *FEATURES],
                               filters=[("split", "==", "test")]).set_index("tx_id")
    report = check(service, features, scores.set_index("tx_id"), stream, PRESETS, check_n)
    print(report.to_string(index=False))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument("--check-n", type=int, default=500)
    args = parser.parse_args()
    report = build(args.out, args.check_n)
    ok = (report["özellik farkı"] < 1e-9).all() and (report["olasılık farkı"] < 1e-12).all()
    print("KESİT TUTARLI" if ok else "KESİT TUTARSIZ")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()

"""Panelin Streamlit'ten bağımsız hesapları (test edilebilir olsun diye ayrı)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from card_fraud_detection.config import REVIEW_COST
from card_fraud_detection.formatting import tr_num


def money(x: float) -> str:
    return f"${tr_num(x)}"


def mask_card(cc_num) -> str:
    return f"•••• {str(int(cc_num))[-4:]}"


def stream_kpis(results: pd.DataFrame, review_cost: float = REVIEW_COST) -> dict:
    """Akıştaki işlemlerin özeti. `results` sütunları: karar, is_fraud, amt."""
    if results.empty:
        return {"işlem": 0, "alarm": 0, "yakalanan": 0, "kaçan": 0, "yanlış alarm": 0,
                "kaçan tutar": 0.0, "maliyet": 0.0}
    alert = results["karar"].eq("alarm")
    fraud = results["is_fraud"].eq(1)
    missed_amt = float(results.loc[fraud & ~alert, "amt"].sum())
    return {"işlem": len(results), "alarm": int(alert.sum()),
            "yakalanan": int((alert & fraud).sum()), "kaçan": int((~alert & fraud).sum()),
            "yanlış alarm": int((alert & ~fraud).sum()), "kaçan tutar": missed_amt,
            "maliyet": missed_amt + review_cost * int(alert.sum())}


def review_cost_point(p, amt, y, review_cost: float) -> dict:
    """Beklenen maliyet kuralı (olasılık × tutar >= ücret) bu ücretle uygulanırsa sonuç."""
    p, amt, y = np.asarray(p), np.asarray(amt), np.asarray(y).astype(bool)
    alert = p * amt >= review_cost
    n_alert, tp = int(alert.sum()), int((alert & y).sum())
    fraud_amt, caught = float(amt[y].sum()), float(amt[alert & y].sum())
    return {"inceleme ücreti": review_cost, "alarm": n_alert,
            "precision": tp / n_alert if n_alert else 0.0,
            "recall": tp / int(y.sum()) if y.any() else 0.0,
            "tutar recall": caught / fraud_amt if fraud_amt else 0.0,
            "kaçan tutar": fraud_amt - caught,
            "maliyet": fraud_amt - caught + review_cost * n_alert}


def review_cost_curve(p, amt, y, costs) -> pd.DataFrame:
    return pd.DataFrame([review_cost_point(p, amt, y, c) for c in costs])


def alert_queue(results: pd.DataFrame, limit: int = 200) -> pd.DataFrame:
    """Akıştaki alarmlar, en yeni üstte; ilk neden tek satırda."""
    a = results[results["karar"].eq("alarm")].tail(limit).iloc[::-1]
    return pd.DataFrame({
        "işlem no": a["islem_no"],
        "zaman": a["trans_date_trans_time"].dt.strftime("%d.%m %H:%M"),
        "kart": a["cc_num"].map(mask_card),
        "tutar ($)": a["amt"].round(2),
        "kategori": a["category"],
        "olasılık": a["olasilik"],
        "beklenen kayıp ($)": a["beklenen_kayip"].round(0),
        "en güçlü neden": a["nedenler"].map(lambda n: n[0]["aciklama"] if n else ""),
        "gerçek etiket": a["is_fraud"].map({1: "dolandırıcılık", 0: "normal"}),
    }).reset_index(drop=True)

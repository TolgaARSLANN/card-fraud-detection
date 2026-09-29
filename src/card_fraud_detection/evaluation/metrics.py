"""Dengesiz dolandırıcılık verisi için değerlendirme metrikleri.

Üç düzeyde ölçüm yapılır:
1. Sıralama (eşikten bağımsız): PR-AUC (ana metrik), ROC-AUC, sabit precision'da recall.
2. Operasyon (eşik ya da alarm bütçesiyle): alarm sayısı, precision, recall, yakalanan
   tutar ve maliyet. Maliyet = kaçırılan dolandırıcılık tutarı + her alarm için inceleme
   ücreti (`REVIEW_COST`). Günlük alarm bütçesi, her gün en yüksek skorlu k işlemin
   incelendiği durumu ölçer.
3. Patlama: Bir kartın dolandırıcılıkları `BURST_GAP`'ten kısa aralıklarla geliyorsa tek
   patlamadır. Patlama yakalandı mı, kaçıncı işlemde yakalandı ve o ana kadar ne kadar
   kaybedildi? **Varsayım:** İlk alarmda kart bloke edilir; kayıp yalnızca ilk alarmdan
   önceki dolandırıcılıklardır. Bu yüzden işlem bazlı `kacan_tutar`'dan daha iyimserdir;
   ikisi birlikte raporlanmalıdır.

Alarm kuralı her yerde aynıdır: skor >= eşik.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score

from card_fraud_detection.config import BURST_GAP, CARD_COL, REVIEW_COST, TARGET, TIME_COL


def _arrays(*xs):
    return [np.asarray(x) for x in xs]


# 1. Sıralama ----------------------------------------------------------------------------------

def pr_auc(y, score) -> float:
    return float(average_precision_score(y, score))


def roc_auc(y, score) -> float:
    return float(roc_auc_score(y, score))


def recall_at_precision(y, score, min_precision: float) -> float:
    """Precision en az `min_precision` iken ulaşılabilen en yüksek recall (yoksa 0)."""
    precision, recall, _ = precision_recall_curve(y, score)
    ok = precision >= min_precision
    return float(recall[ok].max()) if ok.any() else 0.0


# 2. Operasyon ---------------------------------------------------------------------------------

def alert_metrics(y, alert, amt, review_cost: float = REVIEW_COST) -> dict:
    """Verilen alarm kararları (0/1) için adet, tutar ve maliyet özeti."""
    y, alert, amt = _arrays(y, alert, amt)
    y, alert = y.astype(bool), alert.astype(bool)
    tp, fp, fn = (y & alert).sum(), (~y & alert).sum(), (y & ~alert).sum()
    fraud_amt = amt[y].sum()
    caught_amt = amt[y & alert].sum()
    n_alerts = int(alert.sum())
    return {
        "alarm": n_alerts,
        "tp": int(tp), "fp": int(fp), "fn": int(fn),
        "precision": float(tp / n_alerts) if n_alerts else 0.0,
        "recall": float(tp / (tp + fn)) if tp + fn else 0.0,
        "yakalanan_tutar": float(caught_amt),
        "tutar_recall": float(caught_amt / fraud_amt) if fraud_amt else 0.0,
        "kacan_tutar": float(fraud_amt - caught_amt),
        "maliyet": float(fraud_amt - caught_amt + review_cost * n_alerts),
    }


def threshold_metrics(y, score, amt, threshold: float, review_cost: float = REVIEW_COST) -> dict:
    return alert_metrics(y, np.asarray(score) >= threshold, amt, review_cost)


def cost_curve(y, score, amt, review_cost: float = REVIEW_COST) -> pd.DataFrame:
    """Her olası eşik için alarm sayısı ve maliyet. Eşitlik durumunda aynı skorlu işlemler
    birlikte alarm alır; bu yüzden yalnızca skorun değiştiği noktalarda kesilir."""
    y, score, amt = _arrays(y, score, amt)
    order = np.argsort(-score, kind="stable")
    s, fraud_amt_sorted = score[order], np.where(y[order] == 1, amt[order], 0.0)
    last_of_tie = np.r_[s[1:] != s[:-1], True]
    n_alerts = np.arange(1, len(s) + 1)[last_of_tie]
    caught = np.cumsum(fraud_amt_sorted)[last_of_tie]
    tp = np.cumsum(y[order] == 1)[last_of_tie]
    curve = pd.DataFrame({"esik": s[last_of_tie], "alarm": n_alerts, "tp": tp,
                          "yakalanan_tutar": caught})
    no_alert = pd.DataFrame({"esik": [np.inf], "alarm": [0], "tp": [0], "yakalanan_tutar": [0.0]})
    curve = pd.concat([no_alert, curve], ignore_index=True)
    curve["maliyet"] = amt[y == 1].sum() - curve["yakalanan_tutar"] + review_cost * curve["alarm"]
    return curve


def best_threshold_by_cost(y, score, amt, review_cost: float = REVIEW_COST) -> float:
    """Maliyeti en aza indiren eşik. Hiç alarm vermemek en ucuzsa `inf` döner."""
    curve = cost_curve(y, score, amt, review_cost)
    return float(curve.loc[curve["maliyet"].idxmin(), "esik"])


def daily_budget_alerts(score, day, k: int) -> np.ndarray:
    """Her gün en yüksek skorlu en fazla k işleme alarm verir (eşitlikte ilk gelen)."""
    score, day = _arrays(score, day)
    rank = pd.Series(-score).groupby(day).rank(method="first").to_numpy()
    return rank <= k


# 3. Patlama -----------------------------------------------------------------------------------

def assign_bursts(card, time, y, gap: str = BURST_GAP) -> np.ndarray:
    """Her dolandırıcılık işlemine patlama numarası verir; normal işlemler -1 alır."""
    df = pd.DataFrame({"card": np.asarray(card), "time": pd.to_datetime(np.asarray(time)),
                       "y": np.asarray(y)})
    fraud = df[df["y"] == 1].sort_values(["card", "time"], kind="stable")
    new = (fraud["card"] != fraud["card"].shift()) | (
        fraud["time"].diff() >= pd.Timedelta(gap))
    burst = pd.Series(-1, index=df.index)
    burst[fraud.index] = new.cumsum() - 1
    return burst.to_numpy()


def burst_metrics(card, time, y, alert, amt, gap: str = BURST_GAP) -> dict:
    """Patlama düzeyinde yakalama. Bir patlama, işlemlerinden en az biri alarm alırsa
    yakalanmış sayılır; kaybedilen tutar ilk alarmdan önceki dolandırıcılıkların toplamıdır."""
    burst = assign_bursts(card, time, y, gap)
    df = pd.DataFrame({"burst": burst, "time": pd.to_datetime(np.asarray(time)),
                       "alert": np.asarray(alert).astype(bool), "amt": np.asarray(amt)})
    df = df[df["burst"] >= 0].sort_values(["burst", "time"], kind="stable")
    df["sira"] = df.groupby("burst").cumcount() + 1
    df["alarm_oncesi"] = df.groupby("burst")["alert"].cumsum().eq(0)

    per = df.groupby("burst").agg(
        islem=("sira", "max"), toplam_tutar=("amt", "sum"), yakalandi=("alert", "any"))
    first_alert = df[df["alert"]].groupby("burst")["sira"].min()
    per["ilk_alarm_sira"] = first_alert.reindex(per.index)
    per["kayip_tutar"] = df[df["alarm_oncesi"]].groupby("burst")["amt"].sum().reindex(
        per.index, fill_value=0.0)

    if per.empty:
        return {"patlama": 0, "patlama_recall": 0.0, "ilk_islemde_yakalanan": 0.0,
                "ilk_alarm_sira_medyan": np.nan, "kayip_tutar_orani": 0.0}
    return {
        "patlama": len(per),
        "patlama_recall": float(per["yakalandi"].mean()),
        "ilk_islemde_yakalanan": float((per["ilk_alarm_sira"] == 1).mean()),
        # Medyan yalnızca yakalanan patlamalar üzerinden (hiçbiri yakalanmadıysa NaN)
        "ilk_alarm_sira_medyan": float(per["ilk_alarm_sira"].median()),
        "kayip_tutar_orani": float(per["kayip_tutar"].sum() / per["toplam_tutar"].sum()),
    }


# Tümü -----------------------------------------------------------------------------------------

def evaluate(df: pd.DataFrame, score, threshold: float, *,
             review_cost: float = REVIEW_COST, min_precision: float = 0.5) -> dict:
    """Bir skor vektörünü tek sözlükte özetler. `df`: hedef, tutar, kart ve zaman sütunları."""
    y, amt = df[TARGET].to_numpy(), df["amt"].to_numpy()
    alert = np.asarray(score) >= threshold
    return {
        "pr_auc": pr_auc(y, score),
        "roc_auc": roc_auc(y, score),
        f"recall@p{min_precision:g}": recall_at_precision(y, score, min_precision),
        "esik": float(threshold),
        **alert_metrics(y, alert, amt, review_cost),
        **burst_metrics(df[CARD_COL], df[TIME_COL], y, alert, amt),
    }

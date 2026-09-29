"""Birden çok modelin skorlarını aynı satırlar ve aynı metriklerle karşılaştırır."""

from __future__ import annotations

import pandas as pd

from card_fraud_detection.config import DAILY_BUDGET, REVIEW_COST, TARGET, TIME_COL
from card_fraud_detection.evaluation.metrics import (
    alert_metrics,
    best_threshold_by_cost,
    daily_budget_alerts,
    evaluate,
)
from card_fraud_detection.reporting import to_markdown

MAIN_COLUMNS = ["PR-AUC", "ROC-AUC", "recall@p0.5", "bütçe: recall", "bütçe: tutar recall",
                "bütçe: precision", "süre (sn)"]
INT_COLUMNS = ["eşik*: alarm", "eşik*: kaçan tutar ($)", "eşik*: maliyet ($)"]


def comparison_table(valid: pd.DataFrame, scores: dict, seconds: dict) -> pd.DataFrame:
    """Her model için eşikten bağımsız metrikler, günlük bütçe ve maliyet eşiğindeki sonuçlar."""
    y, amt = valid[TARGET].to_numpy(), valid["amt"].to_numpy()
    day = valid[TIME_COL].dt.date.to_numpy()
    rows = {}
    for name, s in scores.items():
        budget = alert_metrics(y, daily_budget_alerts(s, day, DAILY_BUDGET), amt)
        thr = best_threshold_by_cost(y, s, amt)
        m = evaluate(valid, s, thr)
        rows[name] = {
            "PR-AUC": m["pr_auc"], "ROC-AUC": m["roc_auc"], "recall@p0.5": m["recall@p0.5"],
            "bütçe: recall": budget["recall"], "bütçe: tutar recall": budget["tutar_recall"],
            "bütçe: precision": budget["precision"],
            "eşik*: alarm": m["alarm"], "eşik*: precision": m["precision"],
            "eşik*: recall": m["recall"], "eşik*: tutar recall": m["tutar_recall"],
            "eşik*: kaçan tutar ($)": m["kacan_tutar"], "eşik*: maliyet ($)": m["maliyet"],
            "eşik*: patlama recall": m["patlama_recall"],
            "eşik*: ilk işlemde yakalanan": m["ilk_islemde_yakalanan"],
            "süre (sn)": seconds.get(name, float("nan")),
        }
    return pd.DataFrame(rows).T


def comparison_sections(table: pd.DataFrame, valid: pd.DataFrame) -> list[str]:
    """Karşılaştırma tablosunu iki Markdown bölümü olarak döndürür (PR-AUC'ye göre sıralı)."""
    n_days = valid[TIME_COL].dt.date.nunique()
    no_alert_cost = valid.loc[valid[TARGET] == 1, "amt"].sum()
    rank = table.sort_values("PR-AUC", ascending=False)
    main = rank[MAIN_COLUMNS].copy()
    thr = rank[[c for c in rank.columns if c.startswith("eşik*")]].copy()
    for col in INT_COLUMNS:
        thr[col] = thr[col].round().astype(int)
    main.index.name = thr.index.name = "model"
    return [
        "## Eşikten bağımsız karşılaştırma (ana ölçüt)",
        "",
        f"Bütçe: Her gün en yüksek skorlu **{DAILY_BUDGET}** işlem incelenir "
        f"(ölçüm döneminde günde ortalama {valid[TARGET].sum() / n_days:.1f} dolandırıcılık var).",
        "",
        to_markdown(main, ".3f"),
        "",
        "## Maliyete göre seçilen eşikte (iyimser)",
        "",
        f"\\* Eşik, maliyeti (kaçan tutar + alarm başına ${REVIEW_COST:g}) en aza indirecek "
        "biçimde **ölçüm verisinin kendisinde** seçildi; sonuçlar iyimserdir. Nihai eşik Faz "
        "3.3'te doğrulamada seçilip testte sabit tutulacak. "
        f"Hiç alarm vermemenin maliyeti: ${no_alert_cost:,.0f}.",
        "",
        to_markdown(thr, ".3f"),
        "",
    ]

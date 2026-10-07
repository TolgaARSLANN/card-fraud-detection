"""Faz 3.6: SHAP ile açıklama ve alarmlar için Türkçe "ilk 3 neden".

SHAP değerleri ham model skorunu (log-oran) açıklar. Kalibrasyon skoru monoton biçimde
dönüştürdüğü için nedenlerin sıralaması değişmez; katkılar olasılık değil log-oran cinsindendir.

Aynı bilgiyi taşıyan özellikler anlam gruplarına toplanır (ör. `amt` ve `log_amt` → "tutar");
SHAP toplanabilir olduğu için grup katkısı, gruptaki özelliklerin katkılarının toplamıdır.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import shap

from card_fraud_detection.formatting import tr_num

# Özellik → anlam grubu. Her ana özellik tam olarak bir gruba girer (testle denetlenir).
GROUPS: dict[str, list[str]] = {
    "tutar": ["amt", "log_amt"],
    "kategoriye göre tutar": ["amt_to_cat_median"],
    "karta göre tutar": ["amt_to_card_mean", "amt_card_z"],
    "son 1 saat": ["n_1h", "amt_sum_1h"],
    "son 24 saat": ["n_24h", "amt_sum_24h"],
    "son 7 gün": ["n_7d", "amt_sum_7d"],
    "saat": ["hour", "is_night"],
    "kategori": ["category"],
    "haftanın günü": ["dow"],
    "önceki işlemden süre": ["hrs_since_prev"],
    "kart geçmişi uzunluğu": ["card_n_prev"],
    "yeni satıcı / kategori": ["first_at_merchant", "first_in_category"],
}
DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def explainer(model) -> shap.TreeExplainer:
    booster = getattr(model, "booster_", model)
    return shap.TreeExplainer(booster)


def shap_values(expl: shap.TreeExplainer, x: pd.DataFrame,
                num_threads: int | None = None) -> pd.DataFrame:
    """Satır × özellik SHAP değerleri (log-oran). İkili sınıflamada tek çıktı kullanılır.

    `num_threads` verilirse katkılar, SHAP'ın LightGBM için kullandığı aynı çağrıyla
    (`Booster.predict(pred_contrib=True)`) ama sabit iş parçacığı sayısıyla hesaplanır. SHAP bu
    çağrıyı iş parçacığı belirtmeden yapar (tüm çekirdekler); demo'da eşzamanlı oturumlar
    birbirini boğmasın diye 1 verilir. Sonuç SHAP yoluyla aynıdır (testle denetlenir)."""
    booster = getattr(getattr(expl, "model", None), "original_model", None)
    if num_threads is not None and hasattr(booster, "predict") and hasattr(booster, "num_trees"):
        phi = np.asarray(booster.predict(x, pred_contrib=True, num_threads=num_threads))
        return pd.DataFrame(phi[:, :-1], index=x.index, columns=x.columns)   # son sütun: taban
    with warnings.catch_warnings():
        # SHAP her çağrıda LightGBM çıktı biçimiyle ilgili bilgi uyarısı yazar; aşağıda ele alınır
        warnings.filterwarnings("ignore", message="LightGBM binary classifier with TreeExplainer")
        values = expl.shap_values(x)
    if isinstance(values, list):                       # eski shap: sınıf başına liste
        values = values[1]
    values = np.asarray(values)
    if values.ndim == 3:                               # yeni shap: (satır, özellik, sınıf)
        values = values[:, :, 1]
    return pd.DataFrame(values, index=x.index, columns=x.columns)


def base_value(expl: shap.TreeExplainer) -> float:
    ev = np.atleast_1d(expl.expected_value)
    return float(ev[-1])


def group_contributions(sv: pd.DataFrame) -> pd.DataFrame:
    """Özellik katkılarını anlam gruplarına toplar (yalnızca var olan sütunlar)."""
    return pd.DataFrame({g: sv[[c for c in cols if c in sv]].sum(axis=1)
                         for g, cols in GROUPS.items() if any(c in sv for c in cols)},
                        index=sv.index)


def describe(group: str, row: pd.Series) -> str:
    """Bir grubun bu işlemdeki değerini Türkçe cümleye çevirir."""
    amt = row.get("amt", np.nan)
    if group == "tutar":
        return f"Tutar: ${tr_num(amt, 2)}"
    if group == "kategoriye göre tutar":
        return (f"Tutar, {row.get('category')} kategorisindeki olağan tutarın "
                f"{tr_num(row['amt_to_cat_median'], 1)} katı")
    if group == "karta göre tutar":
        r = row.get("amt_to_card_mean", np.nan)
        return ("Kartın bu işlemden önce geçmişi yok" if pd.isna(r)
                else f"Tutar, kartın geçmiş ortalamasının {tr_num(r, 1)} katı")
    if group in ("son 1 saat", "son 24 saat", "son 7 gün"):
        key = {"son 1 saat": "1h", "son 24 saat": "24h", "son 7 gün": "7d"}[group]
        n, s = int(row[f"n_{key}"]), row[f"amt_sum_{key}"]
        label = group[0].upper() + group[1:]
        return (f"{label}te kartta başka işlem yok" if n == 0
                else f"{label}te kartta {n} işlem, toplam ${tr_num(s)}")
    if group == "saat":
        h = int(row["hour"])
        return f"İşlem saati {h:02d}:00" + (" (gece)" if row.get("is_night") == 1 else "")
    if group == "kategori":
        return f"Kategori: {row.get('category')}"
    if group == "haftanın günü":
        return f"Gün: {DAYS[int(row['dow'])]}"
    if group == "önceki işlemden süre":
        h = row.get("hrs_since_prev", np.nan)
        return ("Kartın ilk işlemi" if pd.isna(h)
                else f"Önceki işlemden {tr_num(h, 1)} saat sonra")
    if group == "kart geçmişi uzunluğu":
        return f"Kartın geçmişinde {tr_num(row['card_n_prev'])} işlem"
    if group == "yeni satıcı / kategori":
        parts = [t for f, t in (("first_at_merchant", "bu satıcıyla ilk işlem"),
                                ("first_in_category", "bu kategoride ilk işlem"))
                 if row.get(f) == 1]
        return ("; ".join(parts) or "Bilinen satıcı ve kategori").capitalize()
    raise ValueError(f"Bilinmeyen grup: {group}")


def top_reasons(contrib: pd.Series, row: pd.Series, k: int = 3) -> list[dict]:
    """Skoru en çok yukarı iten (pozitif katkılı) en fazla k grup ve Türkçe açıklaması."""
    positive = contrib[contrib > 0].sort_values(ascending=False).head(k)
    return [{"grup": g, "katki": float(v), "aciklama": describe(g, row)}
            for g, v in positive.items()]


def explain_rows(model, x: pd.DataFrame, k: int = 3) -> list[list[dict]]:
    """Kolay kullanım: her satır için ilk k neden."""
    expl = explainer(model)
    contrib = group_contributions(shap_values(expl, x))
    return [top_reasons(contrib.loc[i], x.loc[i], k) for i in x.index]

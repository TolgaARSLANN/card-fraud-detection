"""Faz 3.4: kaçan dolandırıcılıklar ve yanlış alarmlar.

Kullanım:
    python -m card_fraud_detection.evaluation.error_analysis   # -> reports/hata_analizi.md

İncelenen alarmlar, Faz 3.3'te maliyeti raporlanan alarmların aynısıdır: Mayıs ve Haziran
işlemleri, her ay yalnızca önceki aylarla öğrenilmiş kalibrasyon ve seçilen karar kuralıyla.
Test bölmesine dokunulmaz.

Sorular: (1) kaçan dolandırıcılıklar hangi kategori, tutar ve saatte; (2) patlamanın kaçıncı
işleminde kaçıyor, tamamen kaçan patlama var mı; (3) yanlış alarmlar nerede ve birkaç kartta mı
yoğunlaşıyor; (4) patlama sonrası kart sahibinin gerçek işlemleri yanlış alarm alıyor mu;
(5) model yaş ve cinsiyeti kullanmasa da hata oranları bu gruplarda farklı mı?
"""

from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd

from card_fraud_detection.config import CARD_COL, REPORTS_DIR, TARGET, TIME_COL
from card_fraud_detection.evaluation.metrics import assign_bursts
from card_fraud_detection.features.build import DEMOGRAPHIC_FEATURES, FEATURES
from card_fraud_detection.models.threshold import (
    DECISION_PATH,
    MODEL_PATH,
    Calibrator,
    forward_folds,
    rule_alerts,
)
from card_fraud_detection.models.train import load_splits
from card_fraud_detection.reporting import to_markdown

REPORT_MD = REPORTS_DIR / "hata_analizi.md"
POST_BURST_WINDOW = pd.Timedelta("72h")
AMOUNT_BINS = [0, 10, 50, 100, 200, 500, 1000, np.inf]
AMOUNT_LABELS = ["<10", "10–50", "50–100", "100–200", "200–500", "500–1000", "≥1000"]
AGE_BINS = [0, 25, 35, 45, 55, 65, 120]
AGE_LABELS = ["<25", "25–34", "35–44", "45–54", "55–64", "≥65"]


# Alarm üretimi ----------------------------------------------------------------------------------

def out_of_sample_alerts(valid: pd.DataFrame, score: np.ndarray, decision: dict) -> pd.DataFrame:
    """Faz 3.3'teki zaman katmanlarıyla aynı: her ay önceki aylarla kalibre edilir."""
    y = valid[TARGET].to_numpy()
    parts = []
    for _, fit_idx, eval_idx in forward_folds(valid):
        cal = Calibrator(decision["kalibrasyon"], decision["beta"]).fit(score[fit_idx], y[fit_idx])
        frame = valid.iloc[eval_idx].copy()
        frame["p"] = cal.transform(score[eval_idx])
        frame["alert"] = rule_alerts(decision["kural"], frame["p"], frame, decision.get("esik"))
        parts.append(frame)
    return pd.concat(parts)


def outcome(frame: pd.DataFrame) -> pd.Series:
    y, a = frame[TARGET] == 1, frame["alert"].astype(bool)
    return pd.Series(np.select([y & a, y & ~a, ~y & a], ["yakalandı", "kaçtı", "yanlış alarm"],
                               "doğru sessizlik"), index=frame.index)


# Yardımcı özellikler (yalnızca analiz için; etiket kullanırlar, modele girmezler) -----------------

def burst_position(frame: pd.DataFrame) -> pd.Series:
    """Dolandırıcılık işleminin patlamadaki sırası (1 = ilk); normal işlemler NaN."""
    burst = pd.Series(assign_bursts(frame[CARD_COL], frame[TIME_COL], frame[TARGET]),
                      index=frame.index)
    fraud = burst >= 0
    ordered = frame.loc[fraud].assign(_b=burst[fraud]).sort_values(TIME_COL, kind="stable")
    pos = ordered.groupby("_b").cumcount() + 1
    return pos.reindex(frame.index)


def after_fraud(frame: pd.DataFrame, window: pd.Timedelta = POST_BURST_WINDOW) -> pd.Series:
    """Normal işlem, aynı kartta son `window` içinde bir dolandırıcılıktan sonra mı geliyor?"""
    f = frame.sort_values([CARD_COL, TIME_COL], kind="stable")
    last_fraud = f[TIME_COL].where(f[TARGET] == 1).groupby(f[CARD_COL]).ffill()
    # O anki dolandırıcılığın kendisi "önceki" sayılmasın: yalnızca normal işlemler için anlamlı
    flag = (f[TARGET] == 0) & ((f[TIME_COL] - last_fraud) <= window)
    return flag.reindex(frame.index).fillna(False)


# Tablolar ---------------------------------------------------------------------------------------

def fraud_breakdown(frame: pd.DataFrame, by: pd.Series) -> pd.DataFrame:
    """Dolandırıcılıklar arasında: grup başına adet, kaçan oran ve kaçan tutar payı."""
    fraud = frame[frame[TARGET] == 1]
    g = fraud.groupby(by.loc[fraud.index], observed=True)
    missed = ~fraud["alert"].astype(bool)
    out = pd.DataFrame({
        "dolandırıcılık": g.size(),
        "kaçan": missed.groupby(by.loc[fraud.index], observed=True).sum(),
        "kaçan tutar ($)": fraud["amt"].where(missed, 0).groupby(by.loc[fraud.index],
                                                                   observed=True).sum(),
    })
    out["kaçma oranı"] = out["kaçan"] / out["dolandırıcılık"]
    out["kaçan tutar payı"] = out["kaçan tutar ($)"] / out["kaçan tutar ($)"].sum()
    return out


def alarm_breakdown(frame: pd.DataFrame, by: pd.Series) -> pd.DataFrame:
    """Normal işlemler arasında: grup başına yanlış alarm oranı ve alarmların precision'ı."""
    legit = frame[TARGET] == 0
    alert = frame["alert"].astype(bool)
    out = pd.DataFrame({
        "normal işlem": legit.groupby(by, observed=True).sum(),
        "yanlış alarm": (legit & alert).groupby(by, observed=True).sum(),
        "alarm": alert.groupby(by, observed=True).sum(),
    })
    out["yanlış alarm oranı"] = out["yanlış alarm"] / out["normal işlem"]
    out["precision"] = 1 - out["yanlış alarm"] / out["alarm"].replace(0, np.nan)
    return out


def group_error_rates(frame: pd.DataFrame, by: pd.Series) -> pd.DataFrame:
    """Adalet kontrolü: grup başına recall (dolandırıcılıklarda) ve yanlış alarm oranı."""
    y, a = frame[TARGET] == 1, frame["alert"].astype(bool)
    out = pd.DataFrame({
        "işlem": frame.groupby(by, observed=True).size(),
        "dolandırıcılık": y.groupby(by, observed=True).sum(),
        "recall": (y & a).groupby(by, observed=True).sum() / y.groupby(by, observed=True).sum(),
        "yanlış alarm oranı (‰)": 1000 * (~y & a).groupby(by, observed=True).sum()
        / (~y).groupby(by, observed=True).sum(),
    })
    return out


def standardized_rate(frame: pd.DataFrame, group: str, strata: list[str],
                      outcome_col: str) -> pd.Series:
    """Doğrudan standartlaştırma: `strata` karışımı tüm gruplarda aynı (birleşik dağılım)
    olsaydı grup başına ortalama `outcome_col`. Farkın ne kadarının karışımdan geldiğini ölçer.
    Yalnızca her grupta gözlenen katmanlar kullanılır."""
    cell = frame.groupby([*strata, group], observed=True)[outcome_col].mean().unstack(group)
    cell = cell.dropna()
    weights = frame.groupby(strata, observed=True).size().loc[cell.index]
    return cell.mul(weights, axis=0).sum() / weights.sum()


def card_concentration(frame: pd.DataFrame) -> dict:
    fp = frame[(frame[TARGET] == 0) & frame["alert"].astype(bool)]
    per_card = fp.groupby(CARD_COL).size().sort_values(ascending=False)
    n = len(per_card)
    top10 = per_card.head(max(1, int(np.ceil(0.1 * n)))).sum() if n else 0
    return {
        "yanlış alarm": int(len(fp)),
        "yanlış alarm alan kart": int(n),
        "en çok alarm alan %10 kartın payı": float(top10 / len(fp)) if len(fp) else 0.0,
        "kart başına en fazla yanlış alarm": int(per_card.max()) if n else 0,
    }


def _bin(values, bins, labels):
    return pd.cut(values, bins, labels=labels, right=False)


def _fmt(table: pd.DataFrame) -> pd.DataFrame:
    out = table.copy()
    for c in out.columns:
        if "tutar" in c and "payı" not in c:
            out[c] = out[c].round().astype(int)
    return out


# Rapor ------------------------------------------------------------------------------------------

def build_report(f: pd.DataFrame) -> str:
    kind = f["sonuç"].value_counts()
    fraud_amt = f.loc[f[TARGET] == 1, "amt"].sum()
    missed_amt = f.loc[f["sonuç"] == "kaçtı", "amt"].sum()
    fraud = f[f[TARGET] == 1]

    by_amt = _bin(f["amt"], AMOUNT_BINS, AMOUNT_LABELS).rename("tutar ($)")
    by_hour = f["is_night"].map({1: "gece (22–03)", 0: "gündüz (04–21)"}).rename("saat")
    pos = f["patlama_sira"].clip(upper=5).map(lambda v: "5+" if v == 5 else
                                               (str(int(v)) if pd.notna(v) else np.nan))
    pos = pos.rename("patlamadaki sıra")

    bursts = fraud.groupby("patlama")
    burst_tbl = pd.DataFrame({"işlem": bursts.size(), "yakalandı": bursts["alert"].any(),
                              "toplam tutar": bursts["amt"].sum()})
    missed_bursts = burst_tbl[~burst_tbl["yakalandı"]]

    post = f[(f[TARGET] == 0)].groupby("patlama_sonrasi")["alert"].agg(["size", "sum", "mean"])
    post.index = post.index.map({True: "son 72 saatte dolandırıcılık görmüş kart",
                                 False: "diğer normal işlemler"})
    post.columns = ["normal işlem", "yanlış alarm", "yanlış alarm oranı"]
    post.index.name = "normal işlem"
    fp_post = post["yanlış alarm"].get("son 72 saatte dolandırıcılık görmüş kart", 0)
    post_share = fp_post / max(kind.get("yanlış alarm", 0), 1)

    conc = pd.Series(card_concentration(f)).rename("değer")
    conc.index.name = "yanlış alarmların kartlara dağılımı"

    missed = fraud[fraud["sonuç"] == "kaçtı"]
    small_share = (missed["amt"] < 50).mean() if len(missed) else 0.0
    n_missed_large = int((missed["amt"] >= 200).sum())

    by_age = _bin(f["age"], AGE_BINS, AGE_LABELS).rename("yaş")
    by_gender = f["gender"].astype(str).rename("cinsiyet")

    big_missed = missed[missed["amt"] >= 200][["amt", "category", "hour", "p",
                                               "amt_to_cat_median", "amt_to_card_mean",
                                               "amt_sum_24h", "n_24h"]].copy()
    big_missed["p × tutar"] = big_missed["p"] * big_missed["amt"]
    big_missed.index = big_missed.index.map(lambda i: f"işlem {i}")
    big_missed.index.name = "kaçan ≥$200"

    # Cinsiyet farkı: ≥$500 normal işlemlerde kategori karışımı
    big = f[(f[TARGET] == 0) & (f["amt"] >= 500)].assign(
        cinsiyet=lambda d: d["gender"].astype(str), kategori=lambda d: d["category"].astype(str),
        gece=lambda d: d["is_night"], yanlis=lambda d: d["alert"].astype(float))
    mix = pd.concat({
        "işlem payı": pd.crosstab(big["kategori"], big["cinsiyet"], normalize="columns"),
        "yanlış alarm (‰)": 1000 * big.groupby(["kategori", "cinsiyet"])["yanlis"].mean()
        .unstack(),
    }, axis=1)
    mix = mix[mix[("işlem payı",)].max(axis=1) >= 0.05].sort_values(
        ("işlem payı", mix["işlem payı"].columns[0]), ascending=False)
    mix.columns = [f"{a}: {b}" for a, b in mix.columns]
    mix.index.name = "kategori (≥$500 normal işlem)"
    raw = 1000 * big.groupby("cinsiyet")["yanlis"].mean()
    std = 1000 * standardized_rate(big, "cinsiyet", ["kategori", "gece"], "yanlis")
    gap = pd.DataFrame({"ham (‰)": raw, "kategori × gece karışımı eşitlenmiş (‰)": std})
    gap.index.name = "≥$500 normal işlemde yanlış alarm"
    cards = f[f[TARGET] == 0].groupby([CARD_COL, "gender"], observed=True)["alert"].any() \
        .groupby(level="gender", observed=True).mean().rename("yanlış alarm alan kart oranı")
    cards.index = cards.index.astype(str)
    cards.index.name = "cinsiyet"

    return "\n".join([
        "# Hata Analizi (Faz 3.4)",
        "",
        "_Üreten: `python -m card_fraud_detection.evaluation.error_analysis` · Mayıs ve Haziran "
        "2020 (doğrulama), her ay önceki aylarla kalibre edilmiş alarmlar (Faz 3.3 ile aynı) · "
        "Kural: beklenen maliyet_",
        "",
        "## 1. Genel tablo",
        "",
        to_markdown(kind.rename("işlem").rename_axis("sonuç")),
        "",
        f"Dolandırıcılık tutarı ${fraud_amt:,.0f}; kaçan ${missed_amt:,.0f} "
        f"(%{100 * missed_amt / fraud_amt:.1f}). Kaçanların %{100 * small_share:.0f}'i $50'nin "
        f"altında; $200 ve üzeri kaçan dolandırıcılık {n_missed_large} adet.",
        "",
        "## 2. Kaçan dolandırıcılıklar",
        "",
        "### Tutara göre",
        "",
        to_markdown(_fmt(fraud_breakdown(f, by_amt)), ".3f"),
        "",
        "### Kategoriye göre",
        "",
        to_markdown(_fmt(fraud_breakdown(f, f["category"].astype(str).rename("kategori"))
                         .sort_values("kaçan", ascending=False)), ".3f"),
        "",
        "### Saate göre",
        "",
        to_markdown(_fmt(fraud_breakdown(f, by_hour)), ".3f"),
        "",
        "### Patlamadaki sıraya göre",
        "",
        to_markdown(_fmt(fraud_breakdown(f, pos)), ".3f"),
        "",
        "### $200 ve üzeri kaçan dolandırıcılıklar",
        "",
        "Kuralın bilerek atladığı küçük işlemler değil. Çoğunda tutar kategori medyanının ve "
        "kart ortalamasının çok üzerinde, ama eşlik eden bir patlama yok (24 sa tutar düşük); "
        "model aşırı sapmayı tek başına yeterli saymıyor.",
        "",
        to_markdown(big_missed, ".3f"),
        "",
        f"Patlama sayısı {len(burst_tbl)}; **tamamen kaçan patlama {len(missed_bursts)}** "
        + (f"(toplam ${missed_bursts['toplam tutar'].sum():,.0f}; işlem sayıları "
           f"{sorted(missed_bursts['işlem'].tolist())})." if len(missed_bursts) else "."),
        "",
        "## 3. Yanlış alarmlar",
        "",
        "### Tutara göre",
        "",
        to_markdown(alarm_breakdown(f, by_amt), ".4f"),
        "",
        "### Kategoriye göre",
        "",
        to_markdown(alarm_breakdown(f, f["category"].astype(str).rename("kategori"))
                    .sort_values("yanlış alarm", ascending=False), ".4f"),
        "",
        "### Saate göre",
        "",
        to_markdown(alarm_breakdown(f, by_hour), ".4f"),
        "",
        "### Kartlara dağılım",
        "",
        to_markdown(conc, ".3f"),
        "",
        "## 4. Patlama sonrası yanlış alarmlar",
        "",
        "Kart geçmişi özellikleri (24 sa / 7 g tutar, kart ortalaması) patlamanın izini bir süre "
        "taşır; bu, kart sahibinin patlamadan sonraki gerçek işlemlerinde yanlış alarm "
        "üretebilir.",
        "",
        to_markdown(post, ".4f"),
        "",
        f"Yanlış alarmların %{100 * post_share:.1f}'i son 72 saatte dolandırıcılık görmüş "
        "kartlarda.",
        "",
        "## 5. Adalet kontrolü (model yaş ve cinsiyeti kullanmıyor)",
        "",
        to_markdown(group_error_rates(f, by_age), ".3f"),
        "",
        to_markdown(group_error_rates(f, by_gender), ".3f"),
        "",
        "Kart düzeyinde (işlemler kartlara göre kümelendiği için ayrıca):",
        "",
        to_markdown(cards, ".3f"),
        "",
        "### Cinsiyet farkı nereden geliyor?",
        "",
        "Model cinsiyeti kullanmıyor; fark cinsiyetle ilişkili bir özellik üzerinden gelmeli. "
        "Farkın büyük kısmı $500 üzerindeki gerçek alışverişlerde. Kategori karışımı:",
        "",
        to_markdown(mix, ".3f"),
        "",
        to_markdown(gap, ".0f"),
        "",
        "Kategori ve gece/gündüz karışımı iki grupta eşitlendiğinde fark belirgin biçimde "
        "küçülüyor: Kategori, cinsiyetin yerine geçen bir değişken (vekil) gibi davranıyor. "
        "Korunan özelliği modelden çıkarmak, dolaylı farkı tek başına önlemiyor. Veri sentetik; "
        "harcama kalıplarını cinsiyete göre simülatör üretiyor.",
        "",
    ])


def main() -> None:
    train, valid = load_splits(FEATURES + DEMOGRAPHIC_FEATURES)
    del train
    bundle = joblib.load(MODEL_PATH)
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    score = bundle["model"].predict_proba(valid[bundle["features"]])[:, 1]

    # Patlama işaretleri doğrulamanın tamamında hesaplanır: Nisan'da başlayıp Mayıs'a taşan
    # patlamalar ve Nisan'daki patlamaların ardından gelen Mayıs işlemleri doğru işaretlensin
    valid["patlama"] = assign_bursts(valid[CARD_COL], valid[TIME_COL], valid[TARGET])
    valid["patlama_sira"] = burst_position(valid)
    valid["patlama_sonrasi"] = after_fraud(valid)
    f = out_of_sample_alerts(valid, score, decision)
    f["sonuç"] = outcome(f)

    REPORT_MD.write_text(build_report(f) + "\n", encoding="utf-8")
    print(f["sonuç"].value_counts().to_string())
    print(f"[ok] {REPORT_MD}")


if __name__ == "__main__":
    main()

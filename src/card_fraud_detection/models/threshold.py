"""Faz 3.3: olasılık kalibrasyonu ve karar kuralı seçimi.

Kullanım:
    python -m card_fraud_detection.models.threshold
        -> models/model.joblib, models/decision.json, reports/kalibrasyon_esik.md,
           reports/figures/3_kalibrasyon.png

Model: LightGBM · alt örnekleme, varsayılan parametreler (Faz 3.2 kararı), yalnızca eğitim
bölmesiyle eğitilir. Doğrulama bölmesi kalibrasyon ve eşik için ayrılır; model eğitim +
doğrulamayla yeniden eğitilseydi skor dağılımı değişir, doğrulamada öğrenilen kalibratör ve
eşik ona uymazdı.

Kalibrasyon yöntemleri: ham skor, önsel düzeltme (alt örnekleme oranından analitik), Platt,
izotonik. Karar kuralları: tek sabit eşik (maliyeti en aza indiren), beklenen maliyet kuralı
(olasılık × tutar >= inceleme ücreti; parametresiz), günlük alarm bütçesi.

Dürüst ölçüm için doğrulama dönemi zaman sırasıyla bölünür: Nisan'da öğren → Mayıs'ta ölç;
Nisan+Mayıs'ta öğren → Haziran'da ölç. Seçim ölçütü (önceden konuldu): öğrenilmeyen aylardaki
toplam maliyet. Nihai kalibratör ve eşik doğrulamanın tamamıyla öğrenilir.
"""

from __future__ import annotations

import json

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import PercentFormatter
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

from card_fraud_detection.config import (
    DAILY_BUDGET,
    MODELS_DIR,
    REPORTS_DIR,
    REVIEW_COST,
    TARGET,
    TIME_COL,
)
from card_fraud_detection.evaluation.metrics import (
    alert_metrics,
    best_threshold_by_cost,
    burst_metrics,
    daily_budget_alerts,
    pr_auc,
)
from card_fraud_detection.features.build import FEATURES
from card_fraud_detection.models.train import MINORITY_RATIO, fit, load_splits
from card_fraud_detection.reporting import to_markdown

KIND, STRATEGY = "LightGBM", "alt örnekleme"
MODEL_PATH = MODELS_DIR / "model.joblib"
DECISION_PATH = MODELS_DIR / "decision.json"
REPORT_MD = REPORTS_DIR / "kalibrasyon_esik.md"
FIGURE = REPORTS_DIR / "figures" / "3_kalibrasyon.png"
EPS = 1e-6
ORACLE = "sabit eşik, ölçülen ayda seçilmiş (tavan)"


# Kalibrasyon ------------------------------------------------------------------------------------

def prior_correction(p, beta: float):
    """Normal işlemlerin yalnızca `beta` oranı tutularak eğitilmiş modelin skorunu gerçek
    dağılıma çevirir: p' = beta·p / (beta·p − p + 1). beta = 1 ise değişiklik yoktur."""
    p = np.asarray(p, dtype=float)
    return np.clip(beta * p / (beta * p - p + 1), 0.0, 1.0)   # yuvarlama 1'i aşmasın


def _logit(p):
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return np.log(p / (1 - p)).reshape(-1, 1)


class Calibrator:
    """Skoru olasılığa çeviren tek arayüz: fit(skor, y) ve transform(skor)."""

    METHODS = ("ham", "önsel düzeltme", "Platt", "izotonik")

    def __init__(self, method: str, beta: float = 1.0):
        if method not in self.METHODS:
            raise ValueError(f"Bilinmeyen yöntem: {method}")
        self.method, self.beta, self.model = method, beta, None

    def fit(self, score, y) -> Calibrator:
        if self.method == "Platt":
            self.model = LogisticRegression(C=1e6).fit(_logit(score), y)
        elif self.method == "izotonik":
            self.model = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(score, y)
        return self

    def transform(self, score) -> np.ndarray:
        score = np.asarray(score, dtype=float)
        if self.method == "ham":
            return score
        if self.method == "önsel düzeltme":
            return prior_correction(score, self.beta)
        if self.method == "Platt":
            return self.model.predict_proba(_logit(score))[:, 1]
        return self.model.predict(score)


def quantile_bins(p, n_bins: int) -> list[np.ndarray]:
    """Yaklaşık eşit sayılı dilimler; sınırlar skor değerlerinden çizilir, böylece aynı skorlu
    işlemler hep aynı dilime düşer (izotonik çıktı çok sayıda eşit değer üretir)."""
    p = np.asarray(p, dtype=float)
    edges = np.unique(np.quantile(p, np.linspace(0, 1, n_bins + 1)[1:-1]))
    which = np.searchsorted(edges, p, side="right")
    return [idx for idx in (np.flatnonzero(which == k) for k in range(len(edges) + 1))
            if len(idx)]


def expected_calibration_error(y, p, n_bins: int = 10) -> float:
    """Dilimlerde |ortalama olasılık − gerçek oran| ağırlıklı ortalaması. Dolandırıcılık nadir
    olduğu için eşit genişlikli dilimler yerine eşit sayılı dilimler."""
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    return float(sum(len(b) * abs(p[b].mean() - y[b].mean())
                     for b in quantile_bins(p, n_bins)) / len(p))


def calibration_metrics(y, p) -> dict:
    p = np.clip(p, EPS, 1 - EPS)
    return {"Brier": brier_score_loss(y, p), "log kaybı": log_loss(y, p),
            "ECE": expected_calibration_error(y, p),
            "ortalama olasılık": float(np.mean(p)), "gerçek oran": float(np.mean(y))}


# Karar kuralları --------------------------------------------------------------------------------

RULES = ("sabit eşik", "beklenen maliyet", "günlük bütçe")


def expected_cost_alerts(p, amt, review_cost: float = REVIEW_COST) -> np.ndarray:
    """Beklenen kayıp (olasılık × tutar) inceleme ücretini aşıyorsa alarm."""
    return np.asarray(p) * np.asarray(amt) >= review_cost


def rule_alerts(rule: str, p, frame: pd.DataFrame, threshold: float | None = None) -> np.ndarray:
    if rule == "sabit eşik":
        return np.asarray(p) >= threshold
    if rule == "beklenen maliyet":
        return expected_cost_alerts(p, frame["amt"])
    if rule == "günlük bütçe":
        return daily_budget_alerts(p, frame[TIME_COL].dt.date.to_numpy(), DAILY_BUDGET)
    raise ValueError(f"Bilinmeyen kural: {rule}")


# Zaman katmanları -------------------------------------------------------------------------------

def forward_folds(valid: pd.DataFrame) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """Genişleyen pencere: her ay, kendinden önceki aylarla öğrenilip o ayda ölçülür."""
    month = valid[TIME_COL].dt.to_period("M").to_numpy()
    months = sorted(set(month))
    return [(str(m), np.flatnonzero(month < m), np.flatnonzero(month == m)) for m in months[1:]]


def _outcome(frame: pd.DataFrame, alerts) -> dict:
    y, amt = frame[TARGET].to_numpy(), frame["amt"].to_numpy()
    return {**alert_metrics(y, alerts, amt),
            **burst_metrics(frame["cc_num"], frame[TIME_COL], y, alerts, amt)}


def evaluate_fold(score, valid, fit_idx, eval_idx, beta) -> tuple[dict, dict]:
    y, amt = valid[TARGET].to_numpy(), valid["amt"].to_numpy()
    eval_frame = valid.iloc[eval_idx]
    cal_rows, rule_rows = {}, {}
    for method in Calibrator.METHODS:
        cal = Calibrator(method, beta).fit(score[fit_idx], y[fit_idx])
        p_fit, p_eval = cal.transform(score[fit_idx]), cal.transform(score[eval_idx])
        cal_rows[method] = calibration_metrics(y[eval_idx], p_eval)
        # Beklenen maliyet kuralı olasılığın ölçeğine bağlıdır; her yöntemle denenir.
        # Sabit eşik ve bütçe yalnızca sıralamaya bağlıdır; izotonikle bir kez denenir.
        for rule in RULES:
            if rule != "beklenen maliyet" and method != "izotonik":
                continue
            thr = best_threshold_by_cost(y[fit_idx], p_fit, amt[fit_idx])
            rule_rows[(rule, method)] = _outcome(eval_frame, rule_alerts(rule, p_eval,
                                                                         eval_frame, thr))
    # İyimser tavan: eşiği ölçülen ayın kendisinde seçmek
    oracle = best_threshold_by_cost(y[eval_idx], score[eval_idx], amt[eval_idx])
    rule_rows[(ORACLE, "—")] = _outcome(eval_frame, score[eval_idx] >= oracle)
    return cal_rows, rule_rows


def choose(rule_table: pd.DataFrame) -> tuple[str, str]:
    """Önceden konan ölçüt: öğrenilmeyen aylardaki toplam maliyeti en düşük kural."""
    candidates = rule_table.drop(index=ORACLE, level=0)
    return candidates.groupby(level=[0, 1])["maliyet"].sum().idxmin()


# Rapor ------------------------------------------------------------------------------------------

TAIL_LEVELS = [0.5, 0.8, 0.9, 0.95, 0.98, 0.99, 0.993, 0.996, 0.998]
FLOOR = 1e-4


def reliability_figure(y, probs: dict, path) -> None:
    """Dilimler skor dağılımının üst kuyruğuna yoğunlaşır: işlemlerin %99'dan fazlası sıfıra
    yakın skor aldığı için eşit sayılı dilimler tüm noktaları sıfırın dibine yığar. Hiç
    dolandırıcılık içermeyen dilimler atılmaz (atmak eğriyi yukarı iterdi); log eksende
    sıfır çizilemediği için tabanda içi boş işaretle gösterilir."""
    colors = {"ham": "#898781", "önsel düzeltme": "#eb6834", "Platt": "#1baf7a",
              "izotonik": "#2a78d6"}
    fig, ax = plt.subplots(figsize=(7, 5))
    for name, p in probs.items():
        edges = np.unique(np.quantile(p, TAIL_LEVELS))
        which = np.searchsorted(edges, p, side="right")
        pts = [(max(p[m].mean(), FLOOR), y[m].mean())
               for k in range(len(edges) + 1) if (m := which == k).any()]
        x, yy = np.array(pts).T
        ax.plot(x, np.maximum(yy, FLOOR), lw=2, color=colors[name], label=name)
        ax.scatter(x[yy > 0], yy[yy > 0], s=30, color=colors[name], zorder=3)
        ax.scatter(x[yy == 0], np.full((yy == 0).sum(), FLOOR), s=30, facecolor="none",
                   edgecolor=colors[name], zorder=3)
    ax.plot([FLOOR, 1], [FLOOR, 1], color="#c3c2b7", lw=1, label="mükemmel kalibrasyon")
    ax.set(xscale="log", yscale="log", xlim=(FLOOR, 1), ylim=(FLOOR * 0.8, 1),
           xlabel="Tahmin edilen olasılık (dilim ortalaması)",
           ylabel="Gerçek dolandırıcılık oranı (içi boş: dilimde hiç yok)",
           title="Güvenilirlik eğrisi (Haziran; Nisan–Mayıs'ta öğrenildi)")
    ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=2))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=2))
    ax.legend(loc="upper left", frameon=False)
    ax.grid(color="#e1e0d9", lw=0.6)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=130, facecolor="#fcfcfb")
    plt.close(fig)


RULE_COLUMNS = ["alarm", "precision", "recall", "tutar_recall", "kacan_tutar", "maliyet",
                "patlama_recall", "ilk_islemde_yakalanan"]
INT_COLUMNS = ["alarm", "kacan_tutar", "maliyet"]


def _as_int(table: pd.DataFrame) -> pd.DataFrame:
    out = table.copy()
    out[INT_COLUMNS] = out[INT_COLUMNS].round().astype(int)
    return out


def _flat(table: pd.DataFrame, name: str) -> pd.DataFrame:
    """Çok düzeyli satır adlarını 'a · b · c' biçimine çevirir (Markdown'da okunur olsun)."""
    out = table.copy()
    out.index = [" · ".join(map(str, i)) if isinstance(i, tuple) else str(i) for i in out.index]
    out.index.name = name
    return out


def main() -> None:
    train, valid = load_splits(FEATURES)
    model = fit(KIND, STRATEGY, train, FEATURES)
    score = model.predict_proba(valid[FEATURES])[:, 1]
    n_pos, n_neg = int(train[TARGET].sum()), int((train[TARGET] == 0).sum())
    beta = (n_pos / MINORITY_RATIO) / n_neg        # alt örneklemede tutulan normal oranı
    print(f"Doğrulama PR-AUC {pr_auc(valid[TARGET], score):.4f} · beta {beta:.4f}", flush=True)

    cal_parts, rule_parts = {}, {}
    for month, fit_idx, eval_idx in forward_folds(valid):
        cal_rows, rule_rows = evaluate_fold(score, valid, fit_idx, eval_idx, beta)
        cal_parts[month] = pd.DataFrame(cal_rows).T
        rule_parts[month] = pd.DataFrame(rule_rows).T[RULE_COLUMNS].astype(float)
    cal_table = pd.concat(cal_parts, names=["ölçülen ay", "yöntem"])
    rule_table = (pd.concat(rule_parts, names=["ölçülen ay", "kural", "kalibrasyon"])
                  .reorder_levels([1, 2, 0]).sort_index())
    rule, method = choose(rule_table)

    # Nihai kalibratör ve eşik: doğrulamanın tamamıyla
    y, amt = valid[TARGET].to_numpy(), valid["amt"].to_numpy()
    final_cal = Calibrator(method, beta).fit(score, y)
    threshold = (best_threshold_by_cost(y, final_cal.transform(score), amt)
                 if rule == "sabit eşik" else None)

    # Güvenilirlik grafiği: son katman
    _, fit_idx, eval_idx = forward_folds(valid)[-1]
    probs = {m: Calibrator(m, beta).fit(score[fit_idx], y[fit_idx]).transform(score[eval_idx])
             for m in Calibrator.METHODS}
    reliability_figure(y[eval_idx], probs, FIGURE)

    joblib.dump({"model": model, "calibrator": final_cal, "features": FEATURES}, MODEL_PATH)
    DECISION_PATH.write_text(json.dumps({
        "model": f"{KIND} · {STRATEGY}", "kalibrasyon": final_cal.method, "beta": beta,
        "kural": rule, "esik": threshold, "inceleme_ucreti": REVIEW_COST,
        "gunluk_butce": DAILY_BUDGET,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    totals = rule_table.groupby(level=[0, 1])[INT_COLUMNS].sum().sort_values("maliyet")
    totals = totals.round().astype(int)
    REPORT_MD.write_text("\n".join([
        "# Kalibrasyon ve Karar Kuralı (Faz 3.3)",
        "",
        f"_Üreten: `python -m card_fraud_detection.models.threshold` · Model: {KIND} · "
        f"{STRATEGY}, yalnızca eğitim bölmesiyle · Ölçüm: doğrulama bölmesi, genişleyen zaman "
        "penceresi (her ay, önceki aylarla öğrenilip o ayda ölçülür)_",
        "",
        f"## Karar: **{rule}** ({method} kalibrasyon)",
        "",
        "Seçim ölçütü (önceden konuldu): öğrenilmeyen aylardaki toplam maliyet. "
        f"`{ORACLE}` satırı yalnızca karşılaştırma içindir (iyimser tavan).",
        "",
        "## Karar kuralları (öğrenilmeyen aylar toplamı)",
        "",
        to_markdown(_flat(totals, "kural · kalibrasyon")),
        "",
        "## Kalibrasyon kalitesi (öğrenilmeyen ayda)",
        "",
        "Brier ve log kaybı: düşük daha iyi. ECE: tahmin edilen ile gerçek oran arasındaki "
        "ortalama fark (eşit sayılı 10 dilim).",
        "",
        to_markdown(_flat(cal_table, "ay · yöntem"), ".5f"),
        "",
        "![Güvenilirlik eğrisi](figures/3_kalibrasyon.png)",
        "",
        "## Karar kuralları (ay ay)",
        "",
        to_markdown(_flat(_as_int(rule_table), "kural · kalibrasyon · ay"), ".3f"),
        "",
    ]) + "\n", encoding="utf-8")
    print(totals.to_string())
    print(f"Karar: {rule} ({method}) · eşik {threshold}")
    print(f"[ok] {REPORT_MD}")


if __name__ == "__main__":
    main()

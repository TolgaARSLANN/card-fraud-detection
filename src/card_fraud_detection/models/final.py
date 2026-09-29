"""Faz 3.5: tek seferlik test değerlendirmesi.

Kullanım:
    python -m card_fraud_detection.models.final
        -> reports/test_sonuclari.md, reports/test_sonuclari.json, models/metadata.json

Protokol (docs/YOL_HARITASI.md §3.5, test verisine bakılmadan önce yazıldı ve commit edildi):
- Model, kalibrasyon ve karar kuralı Faz 3.3'te kaydedildiği gibi kullanılır; hiçbir şey
  yeniden eğitilmez veya ayarlanmaz.
- Karşılaştırma: lojistik regresyon ve yalnızca tutar (ikisi de yalnızca eğitim bölmesiyle).
- Başarı ölçütü: model ile lojistik regresyon arasındaki test PR-AUC farkının %95 güven
  aralığı (kart düzeyinde bootstrap) tamamen sıfırın üstünde.
- Test bir kez değerlendirilir: çalıştırma bir kilit dosyası bırakır ve ikinci çalıştırmayı
  reddeder.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

from card_fraud_detection.config import (
    CARD_COL,
    DAILY_BUDGET,
    MODELS_DIR,
    PROCESSED_DIR,
    RANDOM_STATE,
    REPORTS_DIR,
    REVIEW_COST,
    TARGET,
    TIME_COL,
)
from card_fraud_detection.evaluation.error_analysis import group_error_rates
from card_fraud_detection.evaluation.metrics import (
    alert_metrics,
    burst_metrics,
    daily_budget_alerts,
    pr_auc,
    roc_auc,
)
from card_fraud_detection.features.build import DEMOGRAPHIC_FEATURES, FEATURES, FEATURES_PATH
from card_fraud_detection.models.baselines import logistic_regression
from card_fraud_detection.models.threshold import (
    DECISION_PATH,
    MODEL_PATH,
    Calibrator,
    rule_alerts,
)
from card_fraud_detection.reporting import to_markdown

LOCK_PATH = PROCESSED_DIR / "test_degerlendirildi.lock"
REPORT_MD = REPORTS_DIR / "test_sonuclari.md"
REPORT_JSON = REPORTS_DIR / "test_sonuclari.json"
METADATA_PATH = MODELS_DIR / "metadata.json"
N_BOOT = 200
MODEL_NAME = "LightGBM · alt örnekleme (final)"


def card_bootstrap_diff(y, s_a, s_b, cards, n_boot: int = N_BOOT,
                        seed: int = RANDOM_STATE) -> dict:
    """PR-AUC(a) − PR-AUC(b) için kart düzeyinde bootstrap güven aralığı. Aynı karttaki işlemler
    bağımsız olmadığından işlemler değil kartlar yeniden örneklenir; iki model aynı örneklerde
    ölçülür (eşleştirilmiş fark)."""
    y, s_a, s_b = np.asarray(y), np.asarray(s_a), np.asarray(s_b)
    codes, uniq = pd.factorize(np.asarray(cards))
    rows_by_card = pd.Series(np.arange(len(y))).groupby(codes).apply(np.asarray).to_list()
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(uniq), len(uniq))
        idx = np.concatenate([rows_by_card[k] for k in pick])
        if y[idx].sum() == 0:
            continue
        diffs.append(pr_auc(y[idx], s_a[idx]) - pr_auc(y[idx], s_b[idx]))
    diffs = np.array(diffs)
    return {"fark": float(pr_auc(y, s_a) - pr_auc(y, s_b)),
            "alt_sinir_95": float(np.quantile(diffs, 0.025)),
            "ust_sinir_95": float(np.quantile(diffs, 0.975)), "tekrar": int(len(diffs))}


def check_lock(force: bool) -> None:
    if LOCK_PATH.exists() and not force:
        raise SystemExit(
            f"Test daha önce değerlendirildi ({LOCK_PATH.read_text().strip()}). Protokole göre "
            "test bir kez değerlendirilir; yalnızca raporu yeniden üretmek gerekiyorsa ve model "
            "değişmediyse --force kullanın.")


def outcome_row(frame: pd.DataFrame, p, alerts) -> dict:
    y, amt = frame[TARGET].to_numpy(), frame["amt"].to_numpy()
    return {"PR-AUC": pr_auc(y, p), "ROC-AUC": roc_auc(y, p),
            **alert_metrics(y, alerts, amt),
            **burst_metrics(frame[CARD_COL], frame[TIME_COL], y, alerts, amt)}


def monthly(frame: pd.DataFrame, p, alerts) -> pd.DataFrame:
    month = frame[TIME_COL].dt.to_period("M").astype(str).to_numpy()
    rows = {}
    for m in sorted(set(month)):
        k = month == m
        r = outcome_row(frame[k], p[k], alerts[k])
        rows[m] = {"işlem": int(k.sum()), "dolandırıcılık": int(frame[TARGET].to_numpy()[k].sum()),
                   **{c: r[c] for c in ("PR-AUC", "precision", "recall", "tutar_recall",
                                        "kacan_tutar", "maliyet", "patlama_recall")}}
    out = pd.DataFrame(rows).T
    out.index.name = "ay"
    return out


COUNT_KEYS = {"alarm", "tp", "fp", "fn", "patlama", "tekrar", "işlem", "dolandırıcılık"}
MONEY_KEYS = {"kacan_tutar", "maliyet"}


def _fmt_value(key: str, value) -> str:
    if key in COUNT_KEYS:
        return f"{int(round(value)):,}"
    if key in MONEY_KEYS:
        return f"${value:,.0f}"
    return f"{value:.4f}"


def formatted(table: pd.DataFrame | pd.Series) -> pd.DataFrame:
    """Adetler tam sayı, tutarlar dolar, oranlar 4 basamak (to_markdown yalnızca float biçimler)."""
    if isinstance(table, pd.Series):
        out = pd.DataFrame({table.name: [_fmt_value(k, v) for k, v in table.items()]},
                           index=table.index)
    else:
        out = pd.DataFrame({c: [_fmt_value(c, v) for v in table[c]] for c in table.columns},
                           index=table.index)
    out.index.name = table.index.name
    return out


def load_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cols = list(dict.fromkeys(["tx_id", TIME_COL, CARD_COL, "split", TARGET, "amt",
                               *FEATURES, *DEMOGRAPHIC_FEATURES]))
    f = pd.read_parquet(FEATURES_PATH, columns=cols)
    floats = f.select_dtypes("float64").columns.difference(["amt"])
    f[floats] = f[floats].astype("float32")          # bellek: ~3 GB'lık WSL'de sığsın
    return tuple(f[f["split"] == s].reset_index(drop=True) for s in ("train", "valid", "test"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    check_lock(args.force)

    bundle = joblib.load(MODEL_PATH)
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    cal = Calibrator.from_state(bundle["calibrator"])
    train, valid, test = load_frames()
    y = test[TARGET].to_numpy()
    print(f"Test: {len(test):,} işlem, {int(y.sum()):,} dolandırıcılık", flush=True)

    # Model: kaydedildiği gibi
    p = cal.transform(bundle["model"].predict_proba(test[bundle["features"]])[:, 1])
    alerts = rule_alerts(decision["kural"], p, test, decision.get("esik"))
    p_valid = cal.transform(bundle["model"].predict_proba(valid[bundle["features"]])[:, 1])

    # Referanslar: yalnızca eğitim bölmesiyle
    s_lr = logistic_regression(train, test)
    s_amt = test["amt"].to_numpy(dtype=float)
    del train

    day = test[TIME_COL].dt.date.to_numpy()
    summary = {}
    for name, s in [(MODEL_NAME, p), ("Referans: lojistik regresyon", s_lr),
                    ("Referans: yalnızca tutar", s_amt)]:
        budget = alert_metrics(y, daily_budget_alerts(s, day, DAILY_BUDGET), test["amt"])
        summary[name] = {"PR-AUC": pr_auc(y, s), "ROC-AUC": roc_auc(y, s),
                         f"günde {DAILY_BUDGET} alarm: recall": budget["recall"],
                         f"günde {DAILY_BUDGET} alarm: tutar recall": budget["tutar_recall"]}
    summary = pd.DataFrame(summary).T
    summary.index.name = "model"

    boot = card_bootstrap_diff(y, p, s_lr, test[CARD_COL])
    passed = boot["alt_sinir_95"] > 0

    rule = outcome_row(test, p, alerts)
    no_alert_cost = float(test.loc[test[TARGET] == 1, "amt"].sum())
    valid_vs_test = pd.DataFrame({
        "doğrulama": {"PR-AUC": pr_auc(valid[TARGET], p_valid),
                      "dolandırıcılık oranı": float(valid[TARGET].mean())},
        "test": {"PR-AUC": rule["PR-AUC"], "dolandırıcılık oranı": float(y.mean())},
    })
    valid_vs_test.index.name = "ölçü"
    by_month = monthly(test, p, alerts)
    fair = group_error_rates(test.assign(alert=alerts), test["gender"].astype(str)
                             .rename("cinsiyet"))

    stamp = datetime.now().isoformat(timespec="seconds")
    LOCK_PATH.write_text(f"{stamp}\n", encoding="utf-8")
    result = {"zaman": stamp, "basari_olcutu_gecti": bool(passed), "bootstrap": boot,
              "karar_kurali": decision["kural"], "kalibrasyon": decision["kalibrasyon"],
              "test": {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer))
                           else v) for k, v in rule.items()},
              "hic_alarm_vermemenin_maliyeti": no_alert_cost,
              "karsilastirma": summary.to_dict(orient="index")}
    REPORT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    METADATA_PATH.write_text(json.dumps({
        "model": MODEL_NAME, "egitim": "yalnızca eğitim bölmesi (2019-01-01 → 2020-03-31)",
        "ozellikler": bundle["features"], "kalibrasyon": decision["kalibrasyon"],
        "beta": decision["beta"], "karar_kurali": decision["kural"],
        "esik": decision.get("esik"), "inceleme_ucreti": REVIEW_COST,
        "test_pr_auc": rule["PR-AUC"], "test_maliyet": rule["maliyet"],
        "test_degerlendirme_zamani": stamp,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rule_tbl = pd.Series({k: rule[k] for k in (
        "alarm", "tp", "fp", "fn", "precision", "recall", "tutar_recall", "kacan_tutar",
        "maliyet", "patlama", "patlama_recall", "ilk_islemde_yakalanan", "kayip_tutar_orani")},
        name="değer")
    rule_tbl.index.name = f"karar kuralı: {decision['kural']} ({decision['kalibrasyon']})"
    boot_tbl = pd.Series(boot, name="değer")
    boot_tbl.index.name = "PR-AUC farkı: model − lojistik regresyon"
    REPORT_MD.write_text("\n".join([
        "# Test Sonuçları (Faz 3.5)",
        "",
        f"_Üreten: `python -m card_fraud_detection.models.final` · {stamp} · Test: "
        f"{test[TIME_COL].min():%Y-%m-%d} → {test[TIME_COL].max():%Y-%m-%d}, {len(test):,} "
        f"işlem, {int(y.sum()):,} dolandırıcılık · Test bir kez değerlendirildi; protokol "
        "önceden yazıldı (docs/YOL_HARITASI.md §3.5)_",
        "",
        f"## Başarı ölçütü: {'GEÇTİ' if passed else 'GEÇMEDİ'}",
        "",
        "Ölçüt: Test PR-AUC farkının (model − lojistik regresyon) %95 güven aralığı tamamen "
        f"sıfırın üstünde. Kart düzeyinde bootstrap, {boot['tekrar']} tekrar.",
        "",
        to_markdown(formatted(boot_tbl)),
        "",
        "## Modeller (eşikten bağımsız)",
        "",
        to_markdown(summary, ".4f"),
        "",
        "## Karar kuralıyla sonuç",
        "",
        f"Hiç alarm vermemenin maliyeti: ${no_alert_cost:,.0f}.",
        "",
        to_markdown(formatted(rule_tbl)),
        "",
        "## Doğrulama ve test",
        "",
        to_markdown(valid_vs_test, ".4f"),
        "",
        "## Aylara göre",
        "",
        to_markdown(formatted(by_month)),
        "",
        "## Cinsiyete göre hata oranları (izlenen ölçüt, Faz 3.4)",
        "",
        to_markdown(fair, ".3f"),
        "",
    ]) + "\n", encoding="utf-8")
    print(summary.round(4).to_string())
    print(f"Bootstrap fark {boot['fark']:.4f} [{boot['alt_sinir_95']:.4f}, "
          f"{boot['ust_sinir_95']:.4f}] → {'GEÇTİ' if passed else 'GEÇMEDİ'}")
    print(f"[ok] {REPORT_MD}")


if __name__ == "__main__":
    main()

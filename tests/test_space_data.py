"""Space demo kesiti: kişisel sütun yok, takma numaralar doğru, özellikler tam veriyle aynı."""

import numpy as np
import pandas as pd
import pytest
from conftest import TIME, synthetic_transactions

from card_fraud_detection.data.demo import DEMO_COLUMNS, EXCLUDED_COLUMNS
from card_fraud_detection.features.build import FEATURES, build_features, fit_stats
from card_fraud_detection.space.data import check, luhn_valid, make_slice, pseudonyms

RAW_EXTRA = {c: "x" for c in EXCLUDED_COLUMNS}


def raw_like(n=1500, seed=0):
    tx = synthetic_transactions(n=n, cards=40, seed=seed)
    tx["cc_num"] = 4_000_000_000_000_000 + tx["cc_num"] * 7_919     # gerçek kart uzunluğu
    return tx.assign(**RAW_EXTRA)


def test_luhn():
    assert luhn_valid(79927398713) and not luhn_valid(79927398710)


def test_pseudonyms_are_consistent_injective_and_not_card_like():
    cards = raw_like()["cc_num"]
    m = pseudonyms(cards)
    assert m == pseudonyms(cards.sample(frac=1, random_state=1))       # sıradan bağımsız
    assert len(set(m.values())) == len(m) == cards.nunique()          # birebir
    assert all(len(str(v)) == 7 and not luhn_valid(v) for v in m.values())


def test_slice_has_only_demo_columns_and_pseudonymous_cards():
    raw = raw_like()
    end = raw[TIME].iloc[1200]
    out = make_slice(raw, end)
    assert list(out.columns) == DEMO_COLUMNS
    assert set(EXCLUDED_COLUMNS).isdisjoint(out.columns)
    assert (out[TIME] < end).all() and len(out) == (raw[TIME] < end).sum()
    assert not out["cc_num"].isin(raw["cc_num"]).any()               # gerçek numara kalmadı
    m = pseudonyms(raw.loc[raw[TIME] < end, "cc_num"])
    merged = out.merge(raw[["tx_id", "cc_num"]], on="tx_id", suffixes=("", "_real"))
    assert (merged["cc_num"] == merged["cc_num_real"].map(m)).all()  # aynı kart → aynı numara


def test_slice_features_equal_full_data_features():
    raw = raw_like()
    real = raw.drop(columns=list(RAW_EXTRA))       # yer tutucu kişisel sütunlar olmadan
    stats = fit_stats(real)
    full = build_features(real, stats).set_index("tx_id")[FEATURES]
    sliced = make_slice(raw, raw[TIME].iloc[1200])
    part = build_features(sliced, stats).set_index("tx_id")[FEATURES]
    pd.testing.assert_frame_equal(part, full.loc[part.index], check_exact=True)


def test_check_passes_on_consistent_slice_and_fails_on_trimmed_history(serving_setup,
                                                                        make_service):
    tx, stats, _, model, cal = serving_setup
    raw = tx.assign(**RAW_EXTRA)
    sliced = make_slice(raw, raw[TIME].iloc[-1] + pd.Timedelta("1s"))
    feats = build_features(tx, stats).set_index("tx_id")
    p = cal.transform(model.predict_proba(feats[FEATURES])[:, 1])
    scores = pd.DataFrame({"p": p}, index=feats.index)
    cut = len(sliced) - 200
    stream = sliced.iloc[cut:].reset_index(drop=True)
    presets = {"baş": None, "orta": str(stream[TIME].iloc[80])}

    service = make_service(sliced.iloc[:cut])
    service.transactions, service.num_threads = sliced, 1
    report = check(service, feats, scores, stream, presets, n=40)
    assert (report["işlem"] == 40).all()
    assert (report["özellik farkı"] == 0).all() and (report["olasılık farkı"] < 1e-12).all()

    # Geçmişi yalnızca son 7 güne kırpmak özellikleri bozar: kontrol bunu yakalamalı
    recent = sliced.iloc[:cut]
    recent = recent[recent[TIME] >= recent[TIME].max() - pd.Timedelta("7D")]
    trimmed = make_service(recent)
    trimmed.transactions, trimmed.num_threads = sliced, 1
    bad = check(trimmed, feats, scores, stream, {"baş": None}, n=40)
    assert bad["özellik farkı"].iloc[0] > 0


def test_pseudonyms_reject_overflow():
    with pytest.raises(ValueError):
        pseudonyms(np.arange(10_000_000))

"""Demo modu: oturum yalıtımı, paylaşılan taban, bellek sınırları ve oturum zaman aşımı."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import pytest
from conftest import TIME

from card_fraud_detection.features.build import FEATURES
from card_fraud_detection.models.explain import explainer, shap_values
from card_fraud_detection.serving.history import CardHistoryStore, OverlayHistoryStore
from card_fraud_detection.ui.client import ApiError
from card_fraud_detection.ui.demo_backend import (
    PRESETS,
    DemoBackend,
    DemoBusy,
    SessionRegistry,
    SharedBases,
    StreamLimitReached,
)

COLS = ["tx_id", TIME, "cc_num", "amt", "category", "merchant"]


def split(tx, n_stream=80):
    start = len(tx) - n_stream
    stream = tx.iloc[start:].reset_index(drop=True)
    return tx.iloc[:start], [r[COLS[1:]].to_dict() for _, r in stream.iterrows()]


@pytest.fixture
def setup(serving_setup, make_service):
    history, inputs = split(serving_setup[0])
    service = make_service(history)
    service.transactions = serving_setup[0][COLS]
    clock = [0.0]
    registry = SessionRegistry(SharedBases(service), max_sessions=3, ttl=100,
                               clock=lambda: clock[0])
    return service, registry, inputs, clock, history


def backend(service, registry, sid, **kw):
    state, _ = registry.session(sid)
    return DemoBackend(service, registry, state, **kw)


def test_overlay_scores_exactly_like_saving_into_plain_history(serving_setup, make_service):
    """Katmanla skorlama = aynı işlemleri düz geçmişe ekleyerek skorlama (özellikler tutarlı)."""
    history, inputs = split(serving_setup[0])
    plain = make_service(history)
    expected = [plain.score(t)["olasilik"] for t in inputs]
    shared = make_service(history)
    overlay = OverlayHistoryStore(shared.store, max_per_card=1000, max_total=1000)
    got = [shared.score(t, store=overlay)["olasilik"] for t in inputs]
    np.testing.assert_allclose(got, expected, rtol=1e-12)


def test_sessions_do_not_affect_each_other(setup):
    service, registry, inputs, _, _ = setup
    a, b = backend(service, registry, "a"), backend(service, registry, "b")
    probe = inputs[-1]

    def n_prev(s):                       # kartın geçmiş işlem sayısı: oturumun gördüğü geçmiş
        return service.features_for(probe, s.state.store)["card_n_prev"].iloc[0]
    before_b, p_before_b = n_prev(b), b.score(probe, save=False)["olasilik"]
    added = sum(t["cc_num"] == probe["cc_num"] for t in inputs[:-1])
    for t in inputs[:-1]:
        a.score(t)
    assert added > 0
    assert a.health()["islem"] == b.health()["islem"] + len(inputs) - 1
    assert n_prev(b) == before_b and b.score(probe, save=False)["olasilik"] == p_before_b
    assert n_prev(a) == before_b + added                               # a kendi geçmişini görür


def test_shared_history_is_not_copied_per_session(setup):
    service, registry, inputs, _, _ = setup
    frames_before = dict(service.store._cards)
    n_before = service.store.n_transactions
    sessions = [backend(service, registry, s) for s in "abc"]
    for s in sessions:
        for t in inputs[:20]:
            s.score(t)
        assert s.state.store.base is service.store                     # tek taban, kopya yok
    assert service.store.n_transactions == n_before
    assert all(service.store._cards[c] is f for c, f in frames_before.items())
    assert all(s.state.store.n_added == 20 for s in sessions)


def test_overlay_caps_drop_oldest_added_only(setup):
    service, _, inputs, _, _ = setup
    base_n = service.store.n_transactions
    o = OverlayHistoryStore(service.store, max_per_card=3, max_total=10)
    card = inputs[0]["cc_num"]
    same = [{**inputs[0], TIME: inputs[0][TIME] + np.timedelta64(i, "m")} for i in range(5)]
    ids = [o.add(t) for t in same]
    kept = o.history(card)["tx_id"].tolist()
    assert kept[-3:] == ids[-3:] and ids[0] not in kept and ids[1] not in kept   # kart sınırı
    for t in inputs[:30]:
        o.add(t)
    assert o.n_added == 10 and o.n_transactions == base_n + 10                   # toplam sınır
    assert sum(len(f) for f in o._added.values()) == 10
    assert service.store.n_transactions == base_n                                 # taban aynen


def test_stream_limit_per_session(setup):
    service, registry, inputs, _, _ = setup
    a = backend(service, registry, "a", stream_limit=5)
    for t in inputs[:5]:
        a.score(t)
    with pytest.raises(StreamLimitReached):
        a.score(inputs[5])
    assert a.score(inputs[5], save=False)["islem_no"] is None          # inceleme serbest
    a.reset()
    assert a.remaining == 0                                            # sıfırlama sınırı açmaz
    assert a.state.store.n_added == 0


def test_session_timeout_and_session_limit(setup):
    service, registry, _, clock, _ = setup
    for sid in "abc":
        registry.session(sid)
    clock[0] = 10
    with pytest.raises(DemoBusy):                                      # hepsi yeni etkin
        registry.session("d")
    clock[0] = 300                                                     # ttl=100: hepsi düştü
    registry.session("d")
    assert registry.n_sessions == 1
    state, new = registry.session("a")
    assert new and state.store.n_added == 0                            # süresi dolan baştan


def test_full_registry_evicts_longest_idle_session(setup):
    service, registry, _, clock, _ = setup
    registry.session("a")
    clock[0] = 50
    registry.session("b")
    registry.session("c")
    clock[0] = 99                                                      # a 99 sn boşta (< 2 dk)
    with pytest.raises(DemoBusy):
        registry.session("d")
    registry.ttl = 1_000
    clock[0] = 200                                                     # a 200 sn boşta: yer açılır
    registry.session("d")
    assert registry.n_sessions == 3 and registry.session("a")[1]


def test_backend_rejects_unknown_cards_and_free_reset(setup):
    service, registry, inputs, _, _ = setup
    a = backend(service, registry, "a")
    with pytest.raises(ApiError, match="sentetik"):
        a.score({**inputs[0], "cc_num": 4613314721966}, save=False)
    with pytest.raises(ApiError):
        a.reset(until="2020-01-10")


def test_presets_are_layers_built_once_and_shared(setup):
    service, _, inputs, _, _ = setup
    mid = str(inputs[40][TIME])
    bases = SharedBases(service, {"baş": None, "orta": mid})
    assert bases("baş") is service.store
    layer = bases("orta")
    assert layer is bases("orta") and bases.builds == 1
    assert layer.base is service.store                                # tam kopya değil, katman
    assert layer.n_transactions == service.store.n_transactions + 40
    reg = SessionRegistry(bases)
    a, b = backend(service, reg, "a"), backend(service, reg, "b")
    a.start("orta")
    assert a.state.store.base is layer and b.state.store.base is service.store


def test_build_all_prebuilds_presets_and_releases_raw_copy(setup):
    service, _, inputs, _, _ = setup
    bases = SharedBases(service, {"baş": None, "x": str(inputs[40][TIME])})
    bases.build_all(release=True)
    assert bases.builds == 1 and service.transactions is None
    assert bases("x").n_added == 40 and bases.builds == 1           # kurulu olan kullanılır


def test_loaded_history_is_compact_but_features_unchanged(setup):
    """Yüklenmiş geçmişte kategori/satıcı kategorik tipte (bellek); özellikler aynı kalır."""
    service, _, inputs, _, history = setup
    frame = next(iter(service.store._cards.values()))
    assert str(frame["category"].dtype) == "category" and str(frame["merchant"].dtype) == "category"
    plain = {c: g.reset_index(drop=True) for c, g in history.assign(
        category=history["category"].astype(str), merchant=history["merchant"].astype(str))
        [COLS].groupby("cc_num")}
    for t in inputs[:30]:
        a = service.features_for(t)[FEATURES].reset_index(drop=True)
        store = CardHistoryStore()
        store._cards = {int(t["cc_num"]): plain.get(t["cc_num"], pd.DataFrame(columns=COLS))}
        store._next_id = service.store._next_id
        b = service.features_for(t, store)[FEATURES].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)


def test_preset_layer_equals_history_rebuilt_from_scratch(setup):
    """Başlangıç katmanı + oturum = o ana kadar baştan kurulan geçmiş (özellikler birebir)."""
    service, _, inputs, _, _ = setup
    until = str(inputs[40][TIME])
    layer = SharedBases(service, {"x": until})("x")
    rebuilt = CardHistoryStore.from_transactions(service.transactions, until)
    for t in inputs[40:70]:
        a = service.features_for(t, OverlayHistoryStore(layer))[FEATURES]
        b = service.features_for(t, CardHistoryStore(rebuilt.history(t["cc_num"])))[FEATURES]
        pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True))


def test_concurrent_preset_selection_builds_once(setup, monkeypatch):
    service, _, inputs, _, _ = setup
    bases = SharedBases(service, {"x": str(inputs[40][TIME])})
    real, barrier = bases._build, threading.Barrier(8)

    def slow_build(until):                       # yarışı zorla: kurulum sürerken herkes gelsin
        time.sleep(0.2)
        return real(until)
    monkeypatch.setattr(bases, "_build", slow_build)

    def pick():
        barrier.wait()
        return bases("x")
    with ThreadPoolExecutor(8) as pool:
        got = list(pool.map(lambda _: pick(), range(8)))
    assert bases.builds == 1 and all(g is got[0] for g in got)
    assert got[0].n_added == 40                                      # yarım katman yok


def test_threaded_shap_equals_shap_library(serving_setup):
    _, _, feats, model, _ = serving_setup
    expl = explainer(model)
    x = feats[FEATURES].iloc[:50]
    pd.testing.assert_frame_equal(shap_values(expl, x, num_threads=1), shap_values(expl, x),
                                  check_exact=True)


def test_single_thread_prediction_is_requested(setup, monkeypatch):
    service, _, inputs, _, _ = setup
    service.num_threads = 1
    seen = []
    real_predict = service.model.booster_.predict

    def spy(*args, **kwargs):
        seen.append(kwargs.get("num_threads"))
        return real_predict(*args, **kwargs)
    monkeypatch.setattr(service.model.booster_, "predict", spy)
    service.decision.review_cost = 0.0                               # alarm → SHAP de çağrılır
    service.score(inputs[0], save=False)
    assert seen and all(n == 1 for n in seen) and len(seen) == 2     # tahmin + katkılar


@pytest.mark.parametrize("shared_lock", [True, False])
def test_concurrent_sessions_equal_single_thread_run(setup, shared_lock):
    """8 oturum aynı anda (her biri kendi katmanında) skorlarken sonuçlar, tek iş parçacığında
    sırayla skorlamayla birebir aynı olmalı: olasılık ve nedenler (LightGBM + SHAP). Hem ortak
    kilitle (varsayılan) hem oturum başına kilitle."""
    service, registry, inputs, _, _ = setup
    service.num_threads, service.decision.review_cost = 1, 0.0       # hepsi alarm: SHAP çalışır
    service.shared_lock = shared_lock
    registry.max_sessions = 10
    seq = inputs[:40]
    ref = [backend(service, registry, "ref").score(t) for t in seq]
    ref = [(r["olasilik"], r["karar"], r["nedenler"]) for r in ref]
    assert sum(bool(n) for _, _, n in ref) >= 20            # SHAP gerçekten çalıştı
    sessions = [backend(service, registry, f"s{i}") for i in range(8)]
    barrier = threading.Barrier(8)

    def run(s):
        barrier.wait()
        return [(r["olasilik"], r["karar"], r["nedenler"]) for r in (s.score(t) for t in seq)]
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(run, sessions))
    assert all(r == ref for r in results)


def test_demo_sessions_queue_on_shared_lock_by_default(setup):
    """Varsayılan: özellik hesabı tek ortak kilitle sırayla (ölçümde 2 CPU'da 2,2 kat hızlı).
    Ayar kapatılınca her oturum kendi kilidini kullanır ve ötekini beklemez."""
    service, registry, inputs, _, _ = setup
    a, b = backend(service, registry, "a"), backend(service, registry, "b")
    assert service.shared_lock is True
    with ThreadPoolExecutor(1) as pool:
        with service._lock:                      # başka bir oturum hesap yapıyor gibi
            waiting = pool.submit(b.score, inputs[0])
            time.sleep(0.5)
            assert not waiting.done()            # b sırasını bekliyor
        assert waiting.result(timeout=30)["olasilik"] >= 0          # kilit bırakılınca biter

        service.shared_lock = False
        with a.state.store.lock:                 # a'nın hesabı sürüyor gibi
            assert pool.submit(b.score, inputs[1]).result(timeout=30)["olasilik"] >= 0


def test_default_presets_are_valid_times():
    assert next(iter(PRESETS.values())) is None
    assert all(pd.Timestamp(v) for v in list(PRESETS.values())[1:])

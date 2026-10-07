"""Demo modu: oturum yalıtımı, paylaşılan taban, bellek sınırları ve oturum zaman aşımı."""

import numpy as np
import pytest
from conftest import TIME

from card_fraud_detection.serving.history import OverlayHistoryStore
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


def test_presets_are_built_once_and_shared(setup):
    service, _, inputs, _, history = setup
    bases = SharedBases(service, {"baş": None, "orta": str(history[TIME].iloc[len(history) // 2])})
    assert bases("baş") is service.store
    assert bases("orta") is bases("orta")
    assert bases("orta").n_transactions < service.store.n_transactions
    reg = SessionRegistry(bases)
    a, b = backend(service, reg, "a"), backend(service, reg, "b")
    a.start("orta")
    assert a.state.store.base is bases("orta") and b.state.store.base is service.store


def test_default_presets_are_valid_times():
    import pandas as pd
    assert next(iter(PRESETS.values())) is None
    assert all(pd.Timestamp(v) for v in list(PRESETS.values())[1:])

"""Demo modu (herkese açık yayın): API sertleştirmesi ve demo kapalıyken eski davranış."""

import logging

import pytest
from fastapi.testclient import TestClient

from card_fraud_detection.config import DEMO_MAX_BODY_BYTES, DEMO_RATE_LIMIT
from card_fraud_detection.serving import consistency
from card_fraud_detection.serving.app import create_app
from card_fraud_detection.serving.guard import (
    MaskCardNumbers,
    RateLimiter,
    client_ip,
    install_log_masking,
    mask_digits,
)

KNOWN = 1001                     # sentetik geçmişte bulunan kart (1000-1011)
TX = {"cc_num": KNOWN, "trans_date_trans_time": "2020-02-01T23:30:00", "amt": 900.0,
      "category": "shopping_net", "merchant": "a"}


@pytest.fixture
def demo(serving_setup, make_service):
    app = create_app(demo=True)
    app.state.service = make_service(serving_setup[0])
    with TestClient(app) as http:
        yield http, app.state.service


@pytest.fixture
def local(serving_setup, make_service):
    app = create_app(demo=False)
    app.state.service = make_service(serving_setup[0])
    with TestClient(app) as http:
        yield http, app.state.service


# --- Demo kapalı: eski davranış aynen ----------------------------------------------------------

def test_local_mode_keeps_reset_and_saving(local):
    http, service = local
    n0 = http.get("/health").json()["islem"]
    assert http.post("/score", json=TX).json()["islem_no"] is not None
    assert http.post("/score", json={**TX, "cc_num": 4613314721966}).status_code == 200  # yeni kart
    assert http.get("/health").json()["islem"] == n0 + 2
    assert http.post("/reset").json()["islem"] == n0
    paths = http.get("/openapi.json").json()["paths"]
    assert "/reset" in paths and "kaydet" in str(paths["/score"])
    for _ in range(DEMO_RATE_LIMIT + 5):                     # yerelde hız sınırı yok
        assert http.get("/health").status_code == 200


def test_default_app_follows_env(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    assert create_app().state.demo is False
    monkeypatch.setenv("DEMO_MODE", "1")
    assert create_app().state.demo is True


def test_consistency_check_passes_on_synthetic_data(serving_setup, make_service):
    """`make consistency`'nin kullandığı kontrol: servis, eğitimdeki özellik ve olasılıkları
    birebir üretmeli (gerçek veriyle `make consistency` ayrıca çalıştırılır)."""
    tx, _, feats, _, _ = serving_setup
    cut = len(tx) - 200
    diffs, p_diff, _, ok = consistency.check(make_service(tx.iloc[:cut]), tx.iloc[cut:],
                                             feats.iloc[cut:])
    assert ok and diffs.max() == 0 and p_diff < 1e-12


# --- 1. /reset ----------------------------------------------------------------------------------

def test_demo_has_no_reset(demo):
    http, service = demo
    assert http.post("/reset").status_code in (404, 405)
    assert http.post("/reset", params={"until": "2020-02-01T00:00:00"}).status_code in (404, 405)
    assert "/reset" not in http.get("/openapi.json").json()["paths"]


# --- 2. /score: kayıt yok, hız ve gövde sınırı ---

def test_demo_score_never_saves(demo):
    http, service = demo
    n0 = service.store.n_transactions
    for params in ({}, {"kaydet": "true"}):
        r = http.post("/score", json=TX, params=params)
        assert r.status_code == 200 and r.json()["islem_no"] is None
    assert service.store.n_transactions == n0
    assert "kaydet" not in str(http.get("/openapi.json").json()["paths"]["/score"])


def test_demo_rate_limit_returns_429(demo):
    http, _ = demo
    codes = [http.get("/health").status_code for _ in range(DEMO_RATE_LIMIT + 1)]
    assert codes[:-1] == [200] * DEMO_RATE_LIMIT and codes[-1] == 429
    r = http.get("/health")
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1


def test_spoofed_forwarded_for_does_not_bypass_limit(demo):
    """İstemci X-Forwarded-For'un soluna her istekte farklı bir IP yazsa da, vekilin eklediği
    (sağdaki) gerçek IP sayılır."""
    http, _ = demo
    codes = [http.get("/health", headers={"x-forwarded-for": f"10.0.0.{i}, 203.0.113.7"})
             .status_code for i in range(DEMO_RATE_LIMIT + 1)]
    assert codes[-1] == 429
    other = http.get("/health", headers={"x-forwarded-for": "203.0.113.8"})
    assert other.status_code == 200                          # başka ziyaretçi etkilenmez


def test_client_ip_uses_trusted_hop():
    scope = {"client": ("172.16.0.1", 1), "headers": [(b"x-forwarded-for", b"6.6.6.6, 1.2.3.4")]}
    assert client_ip(scope, 0) == "172.16.0.1"
    assert client_ip(scope, 1) == "1.2.3.4"
    assert client_ip(scope, 2) == "6.6.6.6"
    assert client_ip({**scope, "headers": []}, 1) == "172.16.0.1"


def test_rate_limiter_window_and_memory_bound():
    now = [0.0]
    lim = RateLimiter(limit=2, window=10, max_clients=3, clock=lambda: now[0])
    assert lim.allow("a")[0] and lim.allow("a")[0] and not lim.allow("a")[0]
    now[0] = 10.5                                            # pencere kaydı
    assert lim.allow("a")[0]
    for k in "bcdef":
        lim.allow(k)
    assert lim.n_clients == 3


def test_demo_body_limit_returns_413(demo):
    http, _ = demo
    big = {**TX, "merchant": "x" * (DEMO_MAX_BODY_BYTES + 1)}
    assert http.post("/score", json=big).status_code == 413

    def chunks():                                            # Content-Length olmadan parça parça
        yield b'{"merchant": "'
        for _ in range(20):
            yield b"x" * 1024
        yield b'"}'
    r = http.post("/score", content=chunks(), headers={"content-type": "application/json"})
    assert r.status_code == 413


# --- 3. Kart numaraları ---------------------------------------------------------------------------

def test_demo_rejects_unknown_card_without_echo(demo):
    http, _ = demo
    r = http.post("/score", json={**TX, "cc_num": 4613314721966})
    assert r.status_code == 422 and "4613314721966" not in r.text


def test_mask_digits():
    assert mask_digits("kart 4613314721966 ve 12") == "kart ••••1966 ve 12"
    assert mask_digits("2020-06-21 23:15:00") == "2020-06-21 23:15:00"


def test_card_numbers_never_reach_logs(caplog):
    install_log_masking()
    with caplog.at_level(logging.INFO):
        # uvicorn erişim logu biçimi: argümanlar demet olarak kalmalı
        logging.getLogger("uvicorn.access").info(
            '%s - "%s %s HTTP/%s" %d', "1.2.3.4:5", "POST", "/score?cc_num=4613314721966", "1.1",
            200)
        logging.getLogger("card_fraud_detection.x").info("kart %d", 4613314721966)
        logging.getLogger("card_fraud_detection.x").info("kart %s", {"cc_num": 4613314721966})
    assert "4613314721966" not in caplog.text and caplog.text.count("••••1966") == 3
    record = next(r for r in caplog.records if r.name == "uvicorn.access")
    assert isinstance(record.args, tuple) and len(record.args) == 5


def test_demo_request_with_card_is_not_logged(demo, caplog):
    http, _ = demo
    with caplog.at_level(logging.DEBUG):
        http.post("/score", json={**TX, "cc_num": 4613314721966})
        http.post("/score", json={**TX, "amt": 1e12})             # 422: girdi yansıtılmaz
    assert "4613314721966" not in caplog.text


# --- 5. Hata yanıtları ----------------------------------------------------------------------------

def test_demo_server_error_hides_details(serving_setup, make_service, monkeypatch):
    app = create_app(demo=True)
    app.state.service = make_service(serving_setup[0])

    def boom(*a, **k):
        raise RuntimeError("/gizli/yol/model.joblib patladı")
    monkeypatch.setattr(app.state.service, "score", boom)
    with TestClient(app, raise_server_exceptions=False) as http:
        r = http.post("/score", json=TX)
    assert r.status_code == 500 and r.json() == {"detail": "Sunucu hatası"}
    assert "gizli" not in r.text and "Traceback" not in r.text


def test_mask_filter_is_idempotent():
    install_log_masking()
    install_log_masking()
    assert sum(isinstance(f, MaskCardNumbers) for f in logging.getLogger("uvicorn").filters) == 1


def test_demo_scores_known_card_like_local(demo, local):
    """Demo, bilinen kartı yerel modla aynı olasılıkla skorlar (yalnızca kayıt yapmaz)."""
    d, _ = demo
    loc, _ = local
    assert d.post("/score", json=TX).json()["olasilik"] == pytest.approx(
        loc.post("/score", json=TX, params={"kaydet": "false"}).json()["olasilik"], rel=1e-12)

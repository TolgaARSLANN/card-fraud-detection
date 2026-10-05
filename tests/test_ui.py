from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from card_fraud_detection.serving.app import app
from card_fraud_detection.ui import theme
from card_fraud_detection.ui.client import ApiClient, ApiError
from card_fraud_detection.ui.logic import (
    alert_queue,
    mask_card,
    money,
    review_cost_curve,
    review_cost_point,
    stream_kpis,
)

APP_PATH = Path(__file__).parents[1] / "src/card_fraud_detection/ui/app.py"


def test_money_formats():
    assert money(1078.4) == "$1.078"


def test_theme_escapes_html_and_dollar():
    """Dış metin (API'nin nedenleri, satıcı adı) HTML'e kaçışlı girmeli; '$' formüle
    dönüşmesin diye HTML varlığı olmalı."""
    out = theme.note("<script>x</script> olasılık × tutar ($912) ≥ ücret ($10)")
    assert "<script>" not in out and "&lt;script&gt;" in out
    assert "$" not in out and out.count("&#36;") == 2
    kp = theme.kpis([("Kaçan tutar", "$1.078", "signal"), ("İşlem", "150", None)])
    assert kp.count('class="gn-kpi"') == 2 and "&#36;1.078" in kp
    assert kp.count("gn-tick") == 1
    assert "--n:2" in kp                                     # varsayılan: hepsi tek satırda
    assert "--n:3" in theme.kpis([("a", "1", None)] * 6, cols=3)


def test_theme_reason_bars_scale_to_strongest():
    out = theme.reasons([{"aciklama": "Tutar: $912", "katki": 10.0},
                         {"aciklama": "Gece", "katki": 2.5}])
    assert "width:100%" in out and "width:25%" in out
    assert theme.reasons([]) == ""


def test_theme_verdict_accent_follows_decision():
    assert theme.SIGNAL in theme.verdict(True, "%99", "$1.070", "yüksek")
    assert theme.CALM in theme.verdict(False, "%0", "$0", "düşük")


def test_mask_card():
    assert mask_card(4613314721966) == "•••• 1966"


def test_stream_kpis():
    r = pd.DataFrame({"karar": ["alarm", "alarm", "onay", "onay"], "is_fraud": [1, 0, 1, 0],
                      "amt": [500.0, 80.0, 30.0, 10.0]})
    k = stream_kpis(r, review_cost=10)
    assert (k["yakalanan"], k["yanlış alarm"], k["kaçan"]) == (1, 1, 1)
    assert k["kaçan tutar"] == 30.0 and k["maliyet"] == 30.0 + 10 * 2
    assert stream_kpis(pd.DataFrame())["işlem"] == 0


def test_review_cost_curve_is_monotone_and_matches_point():
    rng = np.random.default_rng(0)
    y = (rng.random(2000) < 0.05).astype(int)
    p = np.clip(y * 0.6 + rng.random(2000) * 0.3, 0, 1)
    amt = rng.gamma(2, 80, 2000)
    curve = review_cost_curve(p, amt, y, range(1, 51))
    assert (np.diff(curve["alarm"]) <= 0).all()           # ücret arttıkça alarm azalır
    assert (np.diff(curve["tutar recall"]) <= 1e-12).all()
    assert curve.iloc[9].to_dict() == pytest.approx(review_cost_point(p, amt, y, 10))


def test_alert_queue_newest_first():
    r = pd.DataFrame({
        "islem_no": [1, 2, 3], "karar": ["alarm", "onay", "alarm"],
        "trans_date_trans_time": pd.to_datetime(["2020-07-01 10:00", "2020-07-01 11:00",
                                                 "2020-07-01 12:00"]),
        "cc_num": [1111, 2222, 3333], "amt": [100.0, 5.0, 900.0],
        "category": ["a", "b", "c"], "olasilik": [0.2, 0.0, 0.9],
        "beklenen_kayip": [20.0, 0.0, 810.0], "is_fraud": [0, 0, 1],
        "nedenler": [[{"aciklama": "x"}], [], [{"aciklama": "Tutar: $900,00"}]],
    })
    q = alert_queue(r)
    assert q["işlem no"].tolist() == [3, 1]
    assert q.loc[0, "en güçlü neden"] == "Tutar: $900,00"
    assert q.loc[0, "kart"] == "•••• 3333" and q.loc[0, "gerçek etiket"] == "dolandırıcılık"


def test_client_against_api(serving_setup, make_service):
    app.state.service = make_service(serving_setup[0], review_cost=0.0)
    with TestClient(app) as http:
        client = ApiClient(base_url="test", http=http)
        n0 = client.health()["islem"]
        tx = {"trans_date_trans_time": datetime(2020, 2, 1, 23, 30), "cc_num": 1001,
              "amt": 900.0, "category": "shopping_net", "merchant": "a"}
        assert client.score(tx, save=False)["karar"] == "alarm"
        client.score(tx)
        assert client.health()["islem"] == n0 + 1
        assert client.reset()["islem"] == n0
        with pytest.raises(ApiError, match="Bilinmeyen kategori"):
            client.score({**tx, "category": "yok"})
    app.state.service = None


def test_client_unreachable_raises_api_error():
    with pytest.raises(ApiError, match="ulaşılamadı"):
        ApiClient(base_url="http://127.0.0.1:9", timeout=1).health()


def test_app_shows_error_when_api_is_down(monkeypatch):
    """API çalışmıyorsa panel çökmemeli, ne yapılacağını söyleyen bir hata göstermeli."""
    monkeypatch.setenv("API_URL", "http://127.0.0.1:9")
    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    assert not at.exception
    assert any("make api" in e.value for e in at.error)

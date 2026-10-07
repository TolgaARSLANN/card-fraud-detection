"""Space duman testi: paneli demo modunda açar ve üç sekmeyi sırayla dener.

Kullanım (konteyner içinde; dışarıdan: make space-smoke):
    python -m card_fraud_detection.space.smoke

Adımlar: açılış (uyarı notu, veri kaynağı), Canlı akış (bir adım skorlama, sabit başlangıç),
İşlem incele (listeden kart seçip skorlama), Eşik ve maliyet (ücret kaydırıcısı). Hiçbir
adımda istisna olmamalı. Sonuç tek satır JSON olarak yazılır; sorun varsa çıkış kodu 1.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "ui" / "app.py"


def run(app: Path = APP) -> dict:
    from streamlit.testing.v1 import AppTest

    if os.environ.get("DEMO_MODE") != "1":
        raise SystemExit("DEMO_MODE=1 bekleniyordu")
    out, t0 = {"adimlar": {}}, time.perf_counter()

    def step(name, at):
        out["adimlar"][name] = [e.value for e in at.exception]

    def button(at, label):
        return next(b for b in at.button if label in b.label)

    at = AppTest.from_file(str(app), default_timeout=600).run()
    out["acilis_sn"] = round(time.perf_counter() - t0, 1)
    step("açılış", at)
    text = " ".join(m.value for m in at.markdown)
    out["uyari_notu"] = "tamamen sentetik" in text
    out["veri_kaynagi"] = "CC0" in text and "Sparkov" in text and "MIT" in text

    button(at, "Sonraki").click().run()
    step("canlı akış", at)
    start = next(s for s in at.selectbox if s.label == "Başlangıç")
    start.set_value(start.options[1]).run()
    button(at, "Bu andan başlat").click().run()
    button(at, "Sonraki").click().run()
    step("sabit başlangıç", at)

    at.radio[0].set_value("Elle işlem gir").run()
    next(s for s in at.selectbox if s.label == "Kategori").set_value("shopping_net")
    button(at, "Skorla").click().run()
    step("işlem incele", at)
    out["karar_gosterildi"] = any("Karar" in m.value for m in at.markdown)

    at.slider[0].set_value(25).run()
    step("eşik ve maliyet", at)
    out["maliyet_sekmesi"] = any("Toplam maliyet" in m.value for m in at.markdown)

    out["toplam_sn"] = round(time.perf_counter() - t0, 1)
    out["ok"] = (all(not v for v in out["adimlar"].values()) and out["uyari_notu"]
                 and out["veri_kaynagi"] and out["karar_gosterildi"] and out["maliyet_sekmesi"])
    return out


def main() -> None:
    result = run()
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()

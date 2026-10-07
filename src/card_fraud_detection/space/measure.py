"""Space ölçümü: panelin demo arka ucunu (aynı nesneler, aynı kod yolu) konteynerde ölçer.

Kullanım (konteyner içinde; dışarıdan: make space-measure):
    python -m card_fraud_detection.space.measure [--sessions 10] [--per-session 2000]

Ölçülenler: model + geçmiş yükleme süresi ve belleği, sabit başlangıç katmanlarının kurulumu,
tek oturumda işlem başına süre ve 2.000 işlemlik akış, N eşzamanlı oturumda toplam süre,
işlem başına süre ve en yüksek bellek. Karşılaştırma için aynı eşzamanlı yük, tüm oturumlar
tek ortak kilidi paylaşacak biçimde de çalıştırılır (`--shared-lock`, eski davranış).
Streamlit'in kendi yükü (oturum başına birkaç MB) bu süreçte yoktur; sunucunun belleği
`docker stats` ile ayrıca ölçülür.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from card_fraud_detection.config import TIME_COL


def rss_mb() -> tuple[float, float]:
    """(şu anki, en yüksek) yerleşik bellek, MB (Linux /proc)."""
    fields = dict(line.split(":", 1) for line in open("/proc/self/status", encoding="utf-8"))
    kb = {k: float(fields[k].split()[0]) for k in ("VmRSS", "VmHWM")}
    return round(kb["VmRSS"] / 1024, 1), round(kb["VmHWM"] / 1024, 1)


def stream_rows(stream: pd.DataFrame, until: str | None, n: int) -> list[dict]:
    start = stream[TIME_COL].searchsorted(pd.Timestamp(until)) if until else 0
    cols = [TIME_COL, "cc_num", "amt", "category", "merchant"]
    return [r[cols].to_dict() for _, r in stream.iloc[start:start + n].iterrows()]


def timed_run(backend, rows) -> list[float]:
    out = []
    for tx in rows:
        t0 = time.perf_counter()
        backend.score(tx)
        out.append(1000 * (time.perf_counter() - t0))
    return out


def concurrent(service, registry, presets, stream, sessions, per_session, shared_lock):
    from card_fraud_detection.ui.demo_backend import DemoBackend

    keys, lock = list(presets), threading.RLock()
    backends = []
    for i in range(sessions):
        state, _ = registry.session(f"{'k' if shared_lock else 'o'}{i}")
        backend = DemoBackend(service, registry, state, stream_limit=per_session)
        backend.start(keys[i % len(keys)])
        if shared_lock:
            backend.state.store.lock = lock                    # eski davranış: tek ortak kilit
        backends.append((backend, stream_rows(stream, presets[keys[i % len(keys)]], per_session)))
    barrier = threading.Barrier(sessions)

    def run(item):
        backend, rows = item
        barrier.wait()
        return timed_run(backend, rows)
    t0 = time.perf_counter()
    with ThreadPoolExecutor(sessions) as pool:
        lat = np.concatenate(list(pool.map(run, backends)))
    wall = time.perf_counter() - t0
    return {"oturum": sessions, "oturum_basina_islem": per_session,
            "toplam_sn": round(wall, 1), "islem_per_sn": round(len(lat) / wall, 1),
            "islem_ms_medyan": round(float(np.median(lat)), 1),
            "islem_ms_p95": round(float(np.percentile(lat, 95)), 1),
            "rss_mb_sonra": rss_mb()[0], "rss_mb_en_yuksek": rss_mb()[1]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sessions", type=int, default=10)
    parser.add_argument("--per-session", type=int, default=2000)
    parser.add_argument("--skip-shared-lock", action="store_true")
    parser.add_argument("--shared-first", action="store_true",
                        help="sıra etkisini görmek için önce ortak kilitle ölç")
    args = parser.parse_args()

    from card_fraud_detection.data.clean import OUT_PATH
    from card_fraud_detection.serving.service import ScoringService
    from card_fraud_detection.ui.demo_backend import (
        PRESETS,
        DemoBackend,
        SessionRegistry,
        SharedBases,
    )

    out = {"rss_mb_baslangic": rss_mb()[0]}
    t0 = time.perf_counter()
    service = ScoringService.load()
    service.num_threads = 1
    out["yukleme_sn"] = round(time.perf_counter() - t0, 1)
    out["rss_mb_yukleme_sonrasi"] = rss_mb()[0]
    bases = SharedBases(service)
    registry = SessionRegistry(bases, max_sessions=4 * args.sessions + 10)
    layer_sn = {}
    for key in PRESETS:
        t0 = time.perf_counter()
        bases(key)
        layer_sn[key] = round(time.perf_counter() - t0, 1)
    out["baslangic_katmani_sn"] = layer_sn
    out["rss_mb_katmanlar_sonrasi"] = rss_mb()[0]

    stream = pd.read_parquet(OUT_PATH, filters=[("split", "==", "test")]).sort_values("tx_id")
    stream = stream.reset_index(drop=True)
    state, _ = registry.session("tek")
    single = DemoBackend(service, registry, state, stream_limit=args.per_session)
    t0 = time.perf_counter()
    lat = timed_run(single, stream_rows(stream, None, args.per_session))
    out["tek_oturum"] = {"islem": len(lat), "akis_sn": round(time.perf_counter() - t0, 1),
                         "islem_ms_medyan": round(float(np.median(lat)), 1),
                         "islem_ms_p95": round(float(np.percentile(lat, 95)), 1),
                         "rss_mb_sonra": rss_mb()[0]}
    print(json.dumps(out, ensure_ascii=False), flush=True)
    modes = [("eszamanli_oturum_kilidi", False)]
    if not args.skip_shared_lock:
        modes.append(("eszamanli_ortak_kilit", True))
    for name, shared in (modes[::-1] if args.shared_first else modes):
        out[name] = concurrent(service, registry, PRESETS, stream, args.sessions,
                               args.per_session, shared)
        print(json.dumps(out, ensure_ascii=False), flush=True)
    out["rss_mb_en_yuksek"] = rss_mb()[1]
    print("SONUC" + json.dumps(out, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

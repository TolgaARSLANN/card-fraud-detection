"""Demo modunda API'yi koruyan katman: IP başına hız sınırı, gövde sınırı, logda kart maskeleme.

Yeni bağımlılık yoktur. Hız sınırı süreç içi bir kayan penceredir; birden çok süreç ya da sunucu
çalışırsa her biri kendi sayacını tutar (demo için yeterli, gerçek sistemde ortak bir depo gerekir).
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable

CARD_PATTERN = re.compile(r"(?<!\d)\d{12,19}(?!\d)")


def mask_digits(text: str) -> str:
    """12-19 haneli sayıları (kart numarası olabilecek) son 4 hane dışında gizler."""
    return CARD_PATTERN.sub(lambda m: "••••" + m.group()[-4:], text)


class RateLimiter:
    """Anahtar (IP) başına `limit` istek / `window` saniye. İzlenen anahtar sayısı sınırlıdır;
    sınır aşılınca en uzun süredir istek gelmeyen anahtar unutulur."""

    def __init__(self, limit: int, window: float, max_clients: int = 10_000,
                 clock: Callable[[], float] = time.monotonic):
        self.limit, self.window, self.max_clients, self.clock = limit, window, max_clients, clock
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, float]:
        """(izin var mı, kaç saniye sonra yeniden denenebilir)."""
        now = self.clock()
        with self._lock:
            hits = self._hits.pop(key, None) or deque()
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            self._hits[key] = hits                      # en sona: en son görülen
            while len(self._hits) > self.max_clients:
                self._hits.popitem(last=False)
            if len(hits) >= self.limit:
                return False, max(hits[0] + self.window - now, 0.0)
            hits.append(now)
            return True, 0.0

    @property
    def n_clients(self) -> int:
        return len(self._hits)


def client_ip(scope: dict, trusted_hops: int) -> str:
    """İstemci IP'si. Vekil arkasında X-Forwarded-For'un sağdan `trusted_hops`'uncu değeri
    kullanılır: o değeri güvenilen vekil yazar. En soldaki değer istemcinin kendi yazabildiği
    değerdir, sınırı aşmak için kullanılabilir. Başlık yoksa ya da kısaysa doğrudan bağlantı."""
    direct = (scope.get("client") or ("bilinmiyor", 0))[0]
    if trusted_hops <= 0:
        return direct
    values = [v.decode("latin-1") for k, v in scope.get("headers", [])
              if k.lower() == b"x-forwarded-for"]
    parts = [p.strip() for p in ",".join(values).split(",") if p.strip()]
    return parts[-trusted_hops] if len(parts) >= trusted_hops else direct


async def _send_json(send, status: int, body: dict, headers: list | None = None) -> None:
    data = json.dumps(body, ensure_ascii=False).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"),
                            (b"content-length", str(len(data)).encode()), *(headers or [])]})
    await send({"type": "http.response.body", "body": data})


class DemoGuard:
    """Saf ASGI ara katmanı: önce hız sınırı (429), sonra gövde boyutu (413).

    Gövde en fazla `max_body` bayta kadar okunup uygulamaya tek parça olarak verilir; böylece
    Content-Length yazmadan parça parça gönderilen büyük gövdeler de yakalanır."""

    def __init__(self, app, limiter: RateLimiter, max_body: int, trusted_hops: int):
        self.app, self.limiter, self.max_body, self.hops = app, limiter, max_body, trusted_hops

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        ok, retry = self.limiter.allow(client_ip(scope, self.hops))
        if not ok:
            return await _send_json(send, 429, {"detail": "Çok fazla istek; biraz sonra deneyin."},
                                    [(b"retry-after", str(int(retry) + 1).encode())])
        too_big = {"detail": f"İstek gövdesi en fazla {self.max_body} bayt olabilir."}
        length = dict(scope.get("headers", [])).get(b"content-length")
        if length is not None and (not length.isdigit() or int(length) > self.max_body):
            return await _send_json(send, 413, too_big)
        body, more = b"", True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body += message.get("body", b"")
            more = message.get("more_body", False)
            if len(body) > self.max_body:
                return await _send_json(send, 413, too_big)
        delivered = False

        async def replay():
            nonlocal delivered
            if delivered:
                return await receive()                  # bağlantı kapanışını bekleyenler için
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}

        return await self.app(scope, replay, send)


class MaskCardNumbers(logging.Filter):
    """Log kaydındaki kart numarası olabilecek sayıları maskeler (uvicorn erişim logu dahil)."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Yapı korunur: uvicorn'un erişim biçimlendiricisi `args`'ı demet olarak açar
        if isinstance(record.msg, str):
            record.msg = mask_digits(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(mask_digits(a) if isinstance(a, str) else a for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: mask_digits(v) if isinstance(v, str) else v
                           for k, v in record.args.items()}
        # Sayı olarak verilen bir kart numarası (%d) hâlâ görünüyorsa mesaj düz metne çevrilir
        try:
            message = record.getMessage()
        except (TypeError, ValueError):
            return True
        if CARD_PATTERN.search(message):
            record.msg, record.args = mask_digits(message), None
        return True


LOGGERS = ("uvicorn", "uvicorn.access", "uvicorn.error", "card_fraud_detection", "")


def install_log_masking() -> None:
    """Maskeleme süzgecini ilgili log kaydedicilerine ve kök işleyicilere ekler (tekrar
    çağrılırsa ikinci kez eklemez)."""
    targets = [logging.getLogger(name) for name in LOGGERS]
    targets += logging.getLogger().handlers
    for target in targets:
        if not any(isinstance(f, MaskCardNumbers) for f in target.filters):
            target.addFilter(MaskCardNumbers())

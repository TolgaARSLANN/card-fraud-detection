"""Kart dolandırıcılığı skorlama API'si.

Çalıştırma:
    uvicorn card_fraud_detection.serving.app:app      # make api
    DEMO_MODE=1 uvicorn card_fraud_detection.serving.app:app      # herkese açık demo

Başlangıçta model ve kart geçmişi (varsayılan: test dönemi başlangıcına kadarki işlemler)
yüklenir. `POST /score` her işlemi skorlar ve varsayılan olarak kartın geçmişine ekler.

Demo modunda (DEMO_MODE): `/reset` hiç tanımlanmaz; `/score` geçmişe kayıt yapmaz ve yalnızca
geçmişte bulunan (sentetik) kartları kabul eder; IP başına hız sınırı ve gövde sınırı vardır;
loglarda kart numarası maskelenir; beklenmeyen hatalarda iç ayrıntı dönmez.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from card_fraud_detection.config import (
    DEMO_MAX_BODY_BYTES,
    DEMO_RATE_LIMIT,
    DEMO_RATE_MAX_CLIENTS,
    DEMO_RATE_WINDOW,
    DEMO_TRUSTED_PROXY_HOPS,
    demo_mode,
)
from card_fraud_detection.serving.guard import DemoGuard, RateLimiter, install_log_masking
from card_fraud_detection.serving.schemas import Health, ScoreResponse, Transaction
from card_fraud_detection.serving.service import ScoringService

log = logging.getLogger("card_fraud_detection.serving")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if getattr(app.state, "service", None) is None:     # testler kendi servisini verebilir
        app.state.service = ScoringService.load()
    yield


async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """422 yanıtında ham girdi geri gönderilmez. FastAPI varsayılanı girdiyi aynen koyar;
    `Infinity` gibi JSON'a yazılamayan bir değer gelince 422 yerine 500 dönüyordu. Ayrıca
    gönderilen veriyi yanıtta yansıtmamak daha güvenli."""
    errors = [{k: e[k] for k in ("type", "loc", "msg") if k in e} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


async def server_error(request: Request, exc: Exception) -> JSONResponse:
    """Demo: beklenmeyen hatada yanıtta iç ayrıntı (yığın izi, dosya yolu) olmaz; log'a yazılır."""
    log.exception("Beklenmeyen hata: %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Sunucu hatası"})


def get_service(request: Request) -> ScoringService:
    return request.app.state.service


Service = Annotated[ScoringService, Depends(get_service)]


def check_category(tx: Transaction, service: ScoringService) -> None:
    if tx.category not in service.stats.categories:
        raise HTTPException(422, f"Bilinmeyen kategori: {tx.category}. Geçerli: "
                                 f"{', '.join(service.stats.categories)}")


def create_app(demo: bool | None = None) -> FastAPI:
    """`demo` verilmezse DEMO_MODE ortam değişkeninden okunur."""
    demo = demo_mode() if demo is None else demo
    app = FastAPI(title="Kart Dolandırıcılığı Skorlama API'si", version="1.0", lifespan=lifespan)
    app.state.demo = demo
    app.add_exception_handler(RequestValidationError, validation_error)

    @app.get("/health", response_model=Health)
    def health(service: Service) -> Health:
        return Health(durum="hazır", kart=service.store.n_cards,
                      islem=service.store.n_transactions)

    @app.get("/model")
    def model_info(service: Service) -> dict:
        return {**service.metadata, "ozellikler": service.features}

    if not demo:
        @app.post("/reset", response_model=Health)
        def reset(service: Service, until: datetime | None = None) -> Health:
            """Kart geçmişini başlangıç durumuna döndürür; skorlanıp kaydedilen işlemler silinir.
            `until` verilirse geçmiş, veri setinde o ana kadarki tüm işlemlerle yeniden kurulur."""
            try:
                service.reset(until)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            return health(service)

        @app.post("/score", response_model=ScoreResponse)
        def score(tx: Transaction, service: Service, kaydet: bool = True) -> dict:
            """İşlemi skorlar. `kaydet=false` ile kartın geçmişine eklenmeden yalnızca skorlanır."""
            check_category(tx, service)
            return service.score(tx.model_dump(), save=kaydet)
    else:
        @app.post("/score", response_model=ScoreResponse)
        def score_demo(tx: Transaction, service: Service) -> dict:
            """İşlemi kartın o anki geçmişine göre skorlar; geçmişe kayıt yapılmaz. Yalnızca veri
            setindeki sentetik kartlar kabul edilir (numara yanıtta ya da logda tekrarlanmaz)."""
            if not service.store.has_card(tx.cc_num):
                raise HTTPException(422, "Bu demo yalnızca veri setindeki sentetik kartları "
                                         "kabul eder.")
            check_category(tx, service)
            return service.score(tx.model_dump(), save=False)

        app.add_exception_handler(Exception, server_error)
        app.add_middleware(DemoGuard, limiter=RateLimiter(
            DEMO_RATE_LIMIT, DEMO_RATE_WINDOW, DEMO_RATE_MAX_CLIENTS),
            max_body=DEMO_MAX_BODY_BYTES, trusted_hops=DEMO_TRUSTED_PROXY_HOPS)
        install_log_masking()
    return app


app = create_app()

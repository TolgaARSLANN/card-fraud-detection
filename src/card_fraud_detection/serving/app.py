"""Kart dolandırıcılığı skorlama API'si.

Çalıştırma:
    uvicorn card_fraud_detection.serving.app:app      # make api

Başlangıçta model ve kart geçmişi (varsayılan: test dönemi başlangıcına kadarki işlemler)
yüklenir. `POST /score` her işlemi skorlar ve varsayılan olarak kartın geçmişine ekler.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request

from card_fraud_detection.serving.schemas import Health, ScoreResponse, Transaction
from card_fraud_detection.serving.service import ScoringService


@asynccontextmanager
async def lifespan(app: FastAPI):
    if getattr(app.state, "service", None) is None:     # testler kendi servisini verebilir
        app.state.service = ScoringService.load()
    yield


app = FastAPI(title="Kart Dolandırıcılığı Skorlama API'si", version="1.0", lifespan=lifespan)


def get_service(request: Request) -> ScoringService:
    return request.app.state.service


Service = Annotated[ScoringService, Depends(get_service)]


@app.get("/health", response_model=Health)
def health(service: Service) -> Health:
    return Health(durum="hazır", kart=service.store.n_cards, islem=service.store.n_transactions)


@app.get("/model")
def model_info(service: Service) -> dict:
    return {**service.metadata, "ozellikler": service.features}


@app.post("/score", response_model=ScoreResponse)
def score(tx: Transaction, service: Service, kaydet: bool = True) -> dict:
    """İşlemi skorlar. `kaydet=false` ile kartın geçmişine eklenmeden yalnızca skorlanır."""
    if tx.category not in service.stats.categories:
        raise HTTPException(422, f"Bilinmeyen kategori: {tx.category}. Geçerli: "
                                 f"{', '.join(service.stats.categories)}")
    return service.score(tx.model_dump(), save=kaydet)

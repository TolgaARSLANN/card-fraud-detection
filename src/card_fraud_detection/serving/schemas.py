"""API istek ve yanıt şemaları."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Transaction(BaseModel):
    cc_num: int = Field(description="Kart numarası (kartın geçmişini bulmak için)")
    trans_date_trans_time: datetime = Field(description="İşlem zamanı")
    amt: float = Field(gt=0, description="İşlem tutarı ($)")
    category: str = Field(description="Satıcı kategorisi (ör. shopping_net)")
    merchant: str = Field(description="Satıcı adı")

    model_config = {"json_schema_extra": {"examples": [{
        "cc_num": 4613314721966, "trans_date_trans_time": "2020-06-21T23:15:00",
        "amt": 912.40, "category": "shopping_net", "merchant": "Kutch, Hermiston and Farrell",
    }]}}


class Reason(BaseModel):
    grup: str
    katki: float = Field(description="SHAP katkısı (log-oran); büyük = daha güçlü neden")
    aciklama: str


class ScoreResponse(BaseModel):
    islem_no: int | None = Field(description="Geçmişe kaydedildiyse verilen işlem numarası")
    olasilik: float = Field(description="Kalibre edilmiş dolandırıcılık olasılığı")
    beklenen_kayip: float = Field(description="Olasılık × tutar ($)")
    karar: Literal["alarm", "onay"]
    risk_seviyesi: Literal["düşük", "orta", "yüksek"]
    nedenler: list[Reason] = Field(description="Yalnızca alarmda: skoru en çok artıran 3 neden")


class Health(BaseModel):
    durum: Literal["hazır"]
    kart: int
    islem: int

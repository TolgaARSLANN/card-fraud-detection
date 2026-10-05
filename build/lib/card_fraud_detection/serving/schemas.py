"""API istek ve yanıt şemaları."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MAX_CARD = 2**63 - 1          # kart numarası int64 olarak saklanır
MAX_AMOUNT = 1e9


class Transaction(BaseModel):
    cc_num: int = Field(ge=1, le=MAX_CARD,
                        description="Kart numarası (kartın geçmişini bulmak için)")
    trans_date_trans_time: datetime = Field(
        description="İşlem zamanı, kartın yerel saatiyle ve saat dilimi olmadan "
                    "(ör. 2020-06-21T23:15:00)")
    amt: float = Field(gt=0, le=MAX_AMOUNT, allow_inf_nan=False, description="İşlem tutarı ($)")
    category: str = Field(min_length=1, max_length=64,
                          description="Satıcı kategorisi (ör. shopping_net)")
    merchant: str = Field(min_length=1, max_length=200, description="Satıcı adı")

    @field_validator("trans_date_trans_time")
    @classmethod
    def naive_local_time(cls, v: datetime) -> datetime:
        """Veri setindeki zamanlar saat dilimsiz yerel saattir; saat dilimli bir zamanı sessizce
        çevirmek saat ve gece özelliklerini yanlış hesaplatır, bu yüzden açıkça reddedilir."""
        if v.tzinfo is not None:
            raise ValueError("Zaman saat dilimi içermemeli; kartın yerel saatini saat dilimi "
                             "olmadan gönderin (ör. 2020-06-21T23:15:00)")
        return v

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

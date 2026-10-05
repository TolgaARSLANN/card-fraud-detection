"""Panelin API istemcisi. Panel modeli doğrudan yüklemez; skorlama API'ye HTTP ile yapılır."""

from __future__ import annotations

import os
from datetime import datetime

import httpx

DEFAULT_URL = "http://localhost:8000"


class ApiError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, base_url: str | None = None, http: httpx.Client | None = None,
                 timeout: float = 30.0):
        """`http` verilirse onu kullanır (testlerde FastAPI TestClient)."""
        self.base_url = base_url or os.environ.get("API_URL", DEFAULT_URL)
        self._http = http or httpx.Client(base_url=self.base_url, timeout=timeout)

    def _call(self, method: str, path: str, **kwargs) -> dict:
        try:
            r = self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ApiError(f"API'ye ulaşılamadı ({self.base_url}): {exc}") from exc
        if r.status_code >= 400:
            detail = r.json().get("detail", r.text) if r.headers.get(
                "content-type", "").startswith("application/json") else r.text
            raise ApiError(f"API hatası {r.status_code}: {detail}")
        return r.json()

    def health(self) -> dict:
        return self._call("GET", "/health")

    def model(self) -> dict:
        return self._call("GET", "/model")

    def reset(self, until: datetime | None = None) -> dict:
        params = {"until": until.isoformat()} if until else None
        return self._call("POST", "/reset", params=params)

    def score(self, tx: dict, save: bool = True) -> dict:
        body = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in tx.items()}
        return self._call("POST", "/score", json=body, params={"kaydet": save})

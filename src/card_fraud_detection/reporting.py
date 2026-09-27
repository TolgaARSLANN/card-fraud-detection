"""Raporlar için küçük yardımcılar (ek bağımlılık gerektirmeyen Markdown tablo üretimi)."""

from __future__ import annotations

import pandas as pd


def to_markdown(df: pd.DataFrame | pd.Series, floatfmt: str = ".1f") -> str:
    """DataFrame'i GitHub uyumlu Markdown tablosuna çevirir. İndeks ilk sütun olur."""
    if isinstance(df, pd.Series):
        df = df.to_frame()
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_float_dtype(df[c]):
            df[c] = df[c].map(lambda v: "" if pd.isna(v) else format(v, floatfmt))
    header = "| " + " | ".join([str(df.index.name or "")] + [str(c) for c in df.columns]) + " |"
    sep = "|" + "---|" * (len(df.columns) + 1)
    rows = [
        "| " + " | ".join([str(i)] + [str(v) for v in r]) + " |"
        for i, r in zip(df.index, df.values, strict=True)
    ]
    return "\n".join([header, sep, *rows])

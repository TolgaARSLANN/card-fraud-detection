"""Gece Nöbeti — Pl. 01. Test dönemi işlemlerinden çizilen tasarım tuvali.

Çalıştırma (proje kökünden): python docs/tasarim/gece_nobeti_tuval.py
Gerekenler: data/processed/transactions.parquet (make process) ve yazı tipleri
(Instrument Serif, Geist Mono; aşağıdaki FONTS klasörü, OFL lisanslı). Çıktı: gece-nobeti.png
"""

import math

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = "/home/tlgar/projects/card-fraud-detection/docs/tasarim/gece-nobeti.png"
FONTS = "/mnt/c/Users/tlgar/.claude/skills/canvas-design/canvas-fonts/"
S = 2                                   # süper örnekleme
W, H = 1800, 2400
M = 120

INK = (11, 16, 26)
PAPER = (235, 231, 222)
MUTED = (112, 120, 136)
FAINT = (30, 38, 54)
HAIR = (44, 54, 74)
SLATE = (70, 86, 114)
SIGNAL = (255, 92, 56)

_tx = pd.read_parquet("/home/tlgar/projects/card-fraud-detection/data/processed/transactions.parquet",
                      columns=["trans_date_trans_time", "is_fraud", "split"],
                      filters=[("split", "==", "test")])
_t = _tx["trans_date_trans_time"]
pts = pd.DataFrame({"minute": _t.dt.hour * 60 + _t.dt.minute,
                    "day": (_t.dt.normalize() - _t.dt.normalize().min()).dt.days,
                    "is_fraud": _tx["is_fraud"]})
fraud = pts[pts["is_fraud"] == 1]
n_days = int(pts["day"].max()) + 1


def f(name, size):
    return ImageFont.truetype(FONTS + name, size * S)


serif = f("InstrumentSerif-Regular.ttf", 132)
serif_it = f("InstrumentSerif-Italic.ttf", 44)
serif_mid = f("InstrumentSerif-Regular.ttf", 64)
mono = f("GeistMono-Regular.ttf", 15)
mono_s = f("GeistMono-Regular.ttf", 12)


def P(x, y):
    return (x * S, y * S)


img = Image.new("RGB", (W * S, H * S), INK)
d = ImageDraw.Draw(img)


def tracked(xy, s, font, fill, track=2.0, anchor="l"):
    """Harf aralıklı büyük harf etiket; anchor: l (sol), c (orta), r (sağ)."""
    widths = [d.textlength(ch, font=font) for ch in s]
    total = sum(widths) + track * S * (len(s) - 1)
    x = xy[0] * S - {"l": 0, "c": total / 2, "r": total}[anchor]
    for ch, w in zip(s, widths, strict=True):
        d.text((x, xy[1] * S), ch, font=font, fill=fill, anchor="ls")
        x += w + track * S


# --- Köşe işaretleri ---------------------------------------------------------------------
for cx, cy in [(M - 40, M - 40), (W - M + 40, M - 40), (M - 40, H - M + 40), (W - M + 40, H - M + 40)]:
    d.line([P(cx - 9, cy), P(cx + 9, cy)], fill=HAIR, width=S)
    d.line([P(cx, cy - 9), P(cx, cy + 9)], fill=HAIR, width=S)

# --- Başlık ------------------------------------------------------------------------------
tracked((M, M + 10), "PL. 01  —  NÖBET DEFTERİ", mono, MUTED, 2.4)
tracked((W - M, M + 10), "21.06 — 31.12.2020", mono, MUTED, 2.4, anchor="r")
d.line([P(M, M + 32), P(W - M, M + 32)], fill=HAIR, width=S)
d.text(P(M - 6, M + 70), "Gece Nöbeti", font=serif, fill=PAPER, anchor="lt")
d.text(P(M, M + 232), "sessiz bir akışta nadir olanın haritası", font=serif_it, fill=MUTED,
       anchor="lt")

# --- Kadran ------------------------------------------------------------------------------
CX, CY = W / 2, 1175
R0, R1 = 225, 560


def ang(minute):
    return math.radians(-90 + minute / 1440 * 360)


def polar(r, a):
    return CX + r * math.cos(a), CY + r * math.sin(a)


# Gün halkaları: her hafta soluk, her ay belirgin
day0 = pd.Timestamp("2020-06-21")
for day in range(0, n_days, 7):
    r = R0 + (R1 - R0) * day / (n_days - 1)
    d.ellipse([P(CX - r, CY - r), P(CX + r, CY + r)], outline=FAINT, width=S)
months = pd.date_range("2020-07-01", "2020-12-01", freq="MS")
labels = ["TEM", "AĞU", "EYL", "EKİ", "KAS", "ARA"]
for m, lab in zip(months, labels, strict=True):
    day = (m - day0).days
    r = R0 + (R1 - R0) * day / (n_days - 1)
    d.ellipse([P(CX - r, CY - r), P(CX + r, CY + r)], outline=HAIR, width=S)
    # Etiketler öğle tarafında (altta): izlerin seyrek olduğu yer, okunur kalsın
    d.text(P(CX + 7, CY + r + 3), lab, font=mono_s, fill=MUTED, anchor="lt")
for r in (R0, R1):
    d.ellipse([P(CX - r, CY - r), P(CX + r, CY + r)], outline=SLATE, width=S)

# Saat kolları
for h in range(24):
    a = ang(h * 60)
    x0, y0 = polar(R0 - 14, a)
    x1, y1 = polar(R1, a)
    d.line([P(x0, y0), P(x1, y1)], fill=FAINT if h % 6 else HAIR, width=S)

# Dış çeper: 10 dakikalık dilimlerde normal işlem hacmi
normal = pts[pts["is_fraud"] == 0]
vol = np.bincount(normal["minute"] // 10, minlength=144)
RB = R1 + 26
for i, v in enumerate(vol):
    a = ang(i * 10 + 5)
    L = 70 * v / vol.max()
    x0, y0 = polar(RB, a)
    x1, y1 = polar(RB + L, a)
    d.line([P(x0, y0), P(x1, y1)], fill=SLATE, width=int(2.2 * S))

# Dakika çentikleri
RT = RB + 92
for mnt in range(0, 1440, 5):
    a = ang(mnt)
    L = 16 if mnt % 360 == 0 else 9 if mnt % 60 == 0 else 3
    x0, y0 = polar(RT, a)
    x1, y1 = polar(RT + L, a)
    d.line([P(x0, y0), P(x1, y1)], fill=MUTED if mnt % 60 == 0 else HAIR, width=S)
for h in (0, 6, 12, 18):
    x, y = polar(RT + 44, ang(h * 60))
    d.text(P(x, y), f"{h:02d}", font=mono, fill=PAPER, anchor="mm")

# Gece yayı: 22:00 — 04:00
RN = RT - 16
box = [P(CX - RN, CY - RN), P(CX + RN, CY + RN)]
d.arc(box, start=-90 + 22 * 15, end=-90 + 28 * 15, fill=SIGNAL, width=int(1.6 * S))
x, y = polar(RN - 22, ang(1 * 60))
d.text(P(x, y), "22 — 04", font=mono_s, fill=SIGNAL, anchor="mm")

# Dolandırıcılık izleri: önce hale (bulanık), sonra çekirdek
glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
g = ImageDraw.Draw(glow)
core = []
for _, row in fraud.iterrows():
    r = R0 + (R1 - R0) * row["day"] / (n_days - 1)
    x, y = polar(r, ang(row["minute"]))
    g.ellipse([P(x - 5, y - 5), P(x + 5, y + 5)], fill=SIGNAL + (70,))
    core.append((x, y))
glow = glow.filter(ImageFilter.GaussianBlur(6 * S))
img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
d = ImageDraw.Draw(img)
for x, y in core:
    d.ellipse([P(x - 1.9, y - 1.9), P(x + 1.9, y + 1.9)], fill=SIGNAL)

# Merkez
d.line([P(CX - 10, CY), P(CX + 10, CY)], fill=HAIR, width=S)
d.line([P(CX, CY - 10), P(CX, CY + 10)], fill=HAIR, width=S)
d.text(P(CX, CY - 46), "1 / 259", font=serif_mid, fill=PAPER, anchor="mm")
tracked((CX, CY + 40), "TABAN ORANI", mono_s, MUTED, 2.0, anchor="c")

# --- Alt şerit: günlük iz sayısı ---------------------------------------------------------
BY = 2125
BH = 105
per_day = np.bincount(fraud["day"], minlength=n_days)
x0, x1 = M, W - M
step = (x1 - x0) / n_days
d.line([P(x0, BY), P(x1, BY)], fill=HAIR, width=S)
for day, c in enumerate(per_day):
    if c == 0:
        continue
    x = x0 + step * (day + 0.5)
    d.line([P(x, BY - 2), P(x, BY - 2 - BH * c / per_day.max())], fill=SIGNAL,
           width=int(2 * S))
for m, lab in zip(months, labels, strict=True):
    x = x0 + step * (m - day0).days
    d.line([P(x, BY + 4), P(x, BY + 12)], fill=MUTED, width=S)
    d.text(P(x + 5, BY + 28), lab, font=mono_s, fill=MUTED, anchor="lb")
tracked((M, BY - BH - 22), "GÜNLÜK İZ", mono_s, MUTED, 2.0)
tracked((W - M, BY - BH - 22), f"EN YOĞUN GÜN  {per_day.max()}", mono_s, MUTED, 2.0, anchor="r")

# --- Alt bilgi ---------------------------------------------------------------------------
d.line([P(M, H - M - 34), P(W - M, H - M - 34)], fill=HAIR, width=S)
tracked((M, H - M - 8), "AÇI  SAAT    ·    HALKA  GÜN    ·    KIZIL  DOLANDIRICILIK",
        mono_s, MUTED, 1.8)
tracked((W - M, H - M - 8), "555.719 İŞLEM  ·  2.145 İZ", mono_s, MUTED, 1.8, anchor="r")

img = img.resize((W, H), Image.LANCZOS)
img.save(OUT, optimize=True)
print("[ok]", OUT)

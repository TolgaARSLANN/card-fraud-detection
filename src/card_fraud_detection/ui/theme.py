"""Panelin tasarım sistemi (v3): "Gece Nöbeti" izleme konsolu.

Kaynak: ui-ux-pro-max önerileri (Swiss / minimal ızgara disiplini, IBM Plex ailesi, amber
"güven" rengi), bu panele uyarlanmış hâli; gerekçeler docs/tasarim/arayuz-v3.md.

İmza öğesi: 24 saatlik "nöbet saati". Gece dilimi (22:00–04:00) vurgulanır; dolandırıcılığın
bu saatlere düşen payı veriden hesaplanır. Canlı akıştaki kadran aynı görsel dili kullanır.

Renk rolleri (her biri tek bir anlam taşır, anlam yalnızca renkle verilmez):
- LAMP (amber, "nöbetçinin feneri"): marka, eylem düğmeleri, seçili sekme, odak.
- SIGNAL (kırmızı): yalnızca alarm ve dolandırıcılık; yanında her zaman simge + yazı.
- OK (yeşil): yalnızca "onay" kararı.
- CALM (mavi): grafiklerde normal işlem.
Risk seviyesi renkle değil üç dilimli göstergeyle verilir. Metin kontrastları WCAG AA üstü.

Bileşenler HTML üretir; içlerine giren tüm metinler `esc` ile kaçışlanır. HTML tek satırda
üretilir (Markdown, 4 boşlukla başlayan satırları kod bloğu sayar).
"""

from __future__ import annotations

import math
from html import escape

import plotly.graph_objects as go
import plotly.io as pio


def esc(s) -> str:
    """HTML kaçışı + '$' → '&#36;': Streamlit markdown, HTML içinde bile iki '$' arasını
    matematik formülü sayar (ör. "$912 ... $10")."""
    return escape(str(s)).replace("$", "&#36;")


# --- Tasarım belirteçleri ------------------------------------------------------------------------
INK = "#0a0f1c"          # zemin: gece laciverti
SURFACE = "#101828"      # kart
SURFACE_2 = "#172235"    # vurgulu yüzey
HAIR = "#22304a"         # kenarlık, ızgara
PAPER = "#f1f5f9"        # birincil metin (zemin üzerinde ~17:1)
MUTED = "#9aa8bd"        # ikincil metin (kart üzerinde ~7:1)
LAMP = "#f5b544"         # marka / eylem (koyu yazıyla ~10:1)
ON_LAMP = "#111827"
LAMP_SOFT = "#fcd58a"    # odak halkası, seçili metin
SIGNAL = "#f87171"       # alarm / dolandırıcılık (kart üzerinde ~6:1)
OK = "#4ade80"           # onay
CALM = "#7aa2f7"         # normal işlem
PRIMARY, PRIMARY_SOFT, WARN = LAMP, LAMP_SOFT, LAMP   # eski adlar (geriye uyum)

SANS = "'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', sans-serif"
MONO = "'IBM Plex Mono', ui-monospace, 'SFMono-Regular', monospace"
RADIUS = "8px"
NIGHT = (22, 4)          # gece dilimi: 22:00–04:00

# Lucide çizgi simgeleri (24×24, 2 px çizgi). Metnin yanında süs olarak kullanıldıklarında
# ekran okuyuculardan gizlenir (aria-hidden).
ICONS = {
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
    "activity": '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "sliders": '<line x1="21" x2="14" y1="4" y2="4"/><line x1="10" x2="3" y1="4" y2="4"/><line x1="21" x2="12" y1="12" y2="12"/><line x1="8" x2="3" y1="12" y2="12"/><line x1="21" x2="16" y1="20" y2="20"/><line x1="12" x2="3" y1="20" y2="20"/><line x1="14" x2="14" y1="2" y2="6"/><line x1="8" x2="8" y1="10" y2="14"/><line x1="16" x2="16" y1="18" y2="22"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5V19A9 3 0 0 0 21 19V5"/><path d="M3 12A9 3 0 0 0 21 12"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "lock": '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "cpu": '<rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/>',
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    "arrow": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
}


def icon(name: str, size: int = 20, color: str = "currentColor") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
            f'{ICONS[name]}</svg>')


CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, button, input, select, textarea {{ font-family: {SANS}; }}
.stApp {{ background: {INK}; color: {PAPER}; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stAppDeployButton"], [data-testid="stMainMenu"], #MainMenu, footer {{ display: none; }}
.block-container {{ max-width: 1180px; padding-top: 1.75rem; padding-bottom: 4rem; }}
[data-testid="stHeaderActionElements"], .gn-section h3 a {{ display: none !important; }}

/* Hareket: 150-200 ms, yalnızca durum değişiminde; "hareketi azalt" tercihinde kapalı */
.gn-card, .stButton > button, .stFormSubmitButton > button, .stTabs [data-testid="stTab"] {{
  transition: border-color .18s ease, background-color .18s ease, color .18s ease; }}
@media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ transition: none !important; animation: none !important; }} }}

/* Odak: klavye kullanıcıları için her zaman görünür (amber halka) */
a:focus-visible, button:focus-visible, [role="tab"]:focus-visible, input:focus-visible, [tabindex]:focus-visible {{
  outline: 2px solid {LAMP_SOFT} !important; outline-offset: 2px; border-radius: 6px; }}
a {{ color: {LAMP_SOFT}; }}

/* Sekmeler: segmentli kontrol */
.stTabs [role="tablist"] {{ gap: 4px; padding: 4px; border: 1px solid {HAIR}; border-radius: 10px;
  background: {SURFACE}; width: fit-content; max-width: 100%; }}
.stTabs .react-aria-SelectionIndicator, .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none !important; }}
.stTabs [data-testid="stTab"] {{ padding: 0.55rem 1rem; border-radius: 7px; background: transparent; min-height: 40px; }}
.stTabs [data-testid="stTab"]:hover {{ background: {SURFACE_2}; }}
.stTabs [data-testid="stTab"] p {{ font-size: 0.92rem; font-weight: 500; color: {MUTED}; }}
.stTabs [data-testid="stTab"][aria-selected="true"] {{ background: {SURFACE_2}; box-shadow: inset 0 0 0 1px {HAIR}, inset 0 -2px 0 {LAMP}; }}
.stTabs [data-testid="stTab"][aria-selected="true"] p {{ color: {PAPER}; font-weight: 600; }}
.stTabs [data-baseweb="tab-panel"], .stTabs [role="tabpanel"] {{ padding-top: 0.5rem; }}
/* Dar ekran: dört sekme kaydırmasız sığsın (dokunma hedefi en az 40 px kalır) */
@media (max-width: 560px) {{ .stTabs [role="tablist"] {{ gap: 2px; padding: 3px; width: 100%; }}
  .stTabs [data-testid="stTab"] {{ padding: 0.5rem 0.45rem; flex: 1 1 auto; }}
  .stTabs [data-testid="stTab"] p {{ font-size: 0.8rem; }} }}

/* Düğmeler: en az 44 px; birincil eylem amber üstüne koyu yazı */
.stButton > button, .stFormSubmitButton > button {{ min-height: 44px; border-radius: {RADIUS}; font-weight: 600;
  font-size: 0.92rem; border: 1px solid {HAIR}; background: {SURFACE}; color: {PAPER}; cursor: pointer; }}
.stButton > button p, .stFormSubmitButton > button p {{ font-weight: 600; font-size: 0.92rem; }}
.stButton > button:hover, .stFormSubmitButton > button:hover {{ border-color: {LAMP}; color: {PAPER}; }}
.stButton > button[kind="primary"], .stFormSubmitButton button {{ background: {LAMP}; color: {ON_LAMP}; border-color: {LAMP}; }}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton button:hover {{ background: #f8c766; border-color: #f8c766; color: {ON_LAMP}; }}
.stButton > button[kind="primary"] p, .stFormSubmitButton button p {{ color: {ON_LAMP}; }}
.stButton > button:disabled {{ opacity: 0.45; cursor: not-allowed; }}

/* Form öğeleri, genişletici, tablo */
[data-testid="stWidgetLabel"] p {{ font-size: 0.85rem; font-weight: 500; color: {MUTED}; }}
[data-baseweb="select"] > div, [data-baseweb="input"], .stDateInput input, .stTimeInput input {{ border-radius: {RADIUS} !important; }}
[data-testid="stExpander"] details {{ border: 1px solid {HAIR}; border-radius: {RADIUS}; background: {SURFACE}; }}
[data-testid="stExpander"] summary p {{ font-weight: 500; color: {PAPER}; }}
[data-testid="stCaptionContainer"] {{ color: {MUTED}; }}
[data-testid="stDataFrame"] {{ border: 1px solid {HAIR}; border-radius: {RADIUS}; overflow: hidden; }}
[data-testid="stAlert"] {{ border-radius: {RADIUS}; }}
[data-testid="stPlotlyChart"] {{ border: 1px solid {HAIR}; border-radius: {RADIUS}; background: {SURFACE}; padding: 0.25rem; }}

/* Başlık */
.gn-mast {{ display: flex; justify-content: space-between; align-items: center; gap: 1.25rem; flex-wrap: wrap;
  padding-bottom: 1.1rem; margin-bottom: 0.9rem; border-bottom: 1px solid {HAIR}; }}
.gn-brand {{ display: flex; align-items: center; gap: 0.85rem; min-width: 0; }}
.gn-logo {{ display: grid; place-items: center; width: 44px; height: 44px; border-radius: 10px; flex: none;
  background: {LAMP}; color: {ON_LAMP}; box-shadow: 0 0 0 4px rgba(245,181,68,.12); }}
.gn-overline {{ font-family: {MONO}; font-size: 0.72rem; letter-spacing: 0.1em; text-transform: uppercase; color: {MUTED}; }}
.gn-title {{ font-family: {SANS}; font-weight: 700; font-size: clamp(1.45rem, 3vw, 1.9rem); line-height: 1.15;
  color: {PAPER}; margin: 0.05rem 0 0 0; letter-spacing: -0.015em; }}
h1.gn-title, .stMarkdown h1.gn-title {{ font-family: {SANS} !important; padding: 0 !important; }}
.gn-sub {{ font-size: 0.92rem; color: {MUTED}; margin-top: 0.1rem; }}
.gn-status {{ display: flex; align-items: center; gap: 0.7rem; padding: 0.55rem 1.1rem 0.55rem 0.9rem;
  border: 1px solid {HAIR}; border-radius: 999px; background: {SURFACE}; font-size: 0.82rem; line-height: 1.5;
  color: {MUTED}; max-width: 100%; }}
.gn-status b {{ color: {PAPER}; font-weight: 600; }}
.gn-dot {{ width: 8px; height: 8px; border-radius: 50%; background: {OK}; box-shadow: 0 0 0 4px rgba(74,222,128,.14); flex: none; }}

/* Bölüm başlığı: numaralı, Swiss düzen */
.gn-section {{ margin: 1.9rem 0 0.8rem 0; }}
.gn-section .gn-overline b {{ color: {LAMP}; font-weight: 500; }}
.gn-section h3 {{ font-family: {SANS}; font-weight: 700; font-size: 1.4rem; letter-spacing: -0.01em; color: {PAPER}; margin: 0.3rem 0 0 0; padding: 0; }}
.gn-lede {{ color: {MUTED}; font-size: 0.98rem; max-width: 70ch; line-height: 1.6; margin: 0.35rem 0 0 0; }}

/* Metrik kartları */
.gn-kpis {{ display: grid; grid-template-columns: repeat(var(--n), minmax(0, 1fr)); gap: 0.6rem; margin: 0.9rem 0 0.5rem 0; }}
@media (max-width: 980px) {{ .gn-kpis {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }} }}
@media (max-width: 560px) {{ .gn-kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
.gn-kpi {{ padding: 0.9rem 1rem; background: {SURFACE}; border: 1px solid {HAIR}; border-radius: {RADIUS}; min-width: 0;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.03); }}
/* Metrik etiketleri büyük harf değil: Türkçe büyük harf kuralı İngilizce terimleri bozuyordu */
.gn-kpi .gn-overline {{ display: flex; align-items: center; gap: 0.45rem; font-family: {SANS}; font-size: 0.8rem;
  font-weight: 500; letter-spacing: 0; text-transform: none; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.gn-kpi .gn-val {{ font-family: {MONO}; font-size: 1.6rem; font-weight: 500; line-height: 1.1; color: {PAPER};
  margin-top: 0.5rem; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }}
.gn-tick {{ display: inline-block; width: 8px; height: 8px; background: {SIGNAL}; border-radius: 2px; flex: none; }}
.gn-tick.calm {{ background: {CALM}; }}

/* Karar */
.gn-verdict {{ border: 1px solid {HAIR}; border-radius: {RADIUS}; background: {SURFACE}; display: grid;
  grid-template-columns: minmax(220px, 1.3fr) repeat(3, minmax(120px, 1fr)); margin: 1rem 0; overflow: hidden; }}
.gn-verdict > div {{ padding: 1.05rem 1.2rem; border-left: 1px solid {HAIR}; }}
.gn-verdict > div:first-child {{ border-left: 3px solid var(--accent); background: var(--tint); }}
.gn-verdict .gn-big {{ display: flex; align-items: center; gap: 0.55rem; font-size: 1.75rem; font-weight: 700;
  line-height: 1.1; color: var(--accent); margin-top: 0.45rem; }}
.gn-verdict .gn-mid {{ font-family: {MONO}; font-size: 1.3rem; font-weight: 500; line-height: 1.2; color: {PAPER};
  margin-top: 0.5rem; font-variant-numeric: tabular-nums; }}
.gn-meter {{ display: flex; gap: 4px; margin-top: 0.55rem; }}
.gn-meter span {{ width: 22px; height: 6px; border-radius: 2px; background: {HAIR}; }}
.gn-meter span.on {{ background: {PAPER}; }}
.gn-meter.high span.on {{ background: {SIGNAL}; }}
@media (max-width: 760px) {{ .gn-verdict {{ grid-template-columns: 1fr 1fr; }}
  .gn-verdict > div {{ border-left: none; border-top: 1px solid {HAIR}; }}
  .gn-verdict > div:first-child {{ border-left: 3px solid var(--accent); border-top: none; }} }}

/* Nedenler */
.gn-reasons {{ margin: 0.5rem 0; border: 1px solid {HAIR}; border-radius: {RADIUS}; background: {SURFACE}; overflow: hidden; }}
.gn-reason {{ display: grid; grid-template-columns: 2rem minmax(0, 1fr) 4.5rem; align-items: center; gap: 0.9rem;
  padding: 0.85rem 1.1rem; border-top: 1px solid {HAIR}; }}
.gn-reason:first-child {{ border-top: none; }}
.gn-reason .gn-n {{ font-family: {MONO}; font-size: 0.85rem; color: {LAMP}; }}
.gn-reason .gn-txt {{ color: {PAPER}; font-size: 0.98rem; line-height: 1.45; }}
.gn-reason .gn-bar {{ height: 4px; border-radius: 2px; background: {SIGNAL}; margin-top: 0.5rem; }}
.gn-reason .gn-w {{ font-family: {MONO}; font-size: 0.8rem; color: {MUTED}; text-align: right; font-variant-numeric: tabular-nums; }}

.gn-note-line {{ font-size: 0.82rem; color: {MUTED}; line-height: 1.6; margin-top: 0.5rem; }}

/* Bilgi bandı */
.gn-banner {{ display: flex; gap: 0.7rem; align-items: flex-start; padding: 0.75rem 1rem; margin: 0 0 1rem 0;
  border: 1px solid {HAIR}; border-left: 3px solid {LAMP}; border-radius: {RADIUS}; background: {SURFACE};
  color: {PAPER}; font-size: 0.88rem; line-height: 1.55; }}
.gn-banner svg {{ flex: none; margin-top: 2px; color: {LAMP}; }}

/* Karşılama: kahraman + nöbet saati */
.gn-hero {{ display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr); gap: 0; margin: 0.6rem 0 0.4rem 0;
  border: 1px solid {HAIR}; border-radius: 12px; background: {SURFACE}; overflow: hidden; }}
@media (max-width: 860px) {{ .gn-hero {{ grid-template-columns: 1fr; }} }}
.gn-hero-main {{ padding: 1.75rem 1.75rem 1.5rem 1.75rem; }}
.gn-hero h2 {{ font-family: {SANS}; font-size: clamp(1.45rem, 3vw, 2.05rem); font-weight: 700; line-height: 1.18;
  letter-spacing: -0.02em; color: {PAPER}; margin: 0.45rem 0 0.7rem 0; padding: 0; max-width: 22ch; }}
.gn-hero h2 em {{ font-style: normal; color: {LAMP}; }}
.gn-hero p {{ color: {MUTED}; font-size: 0.98rem; line-height: 1.65; max-width: 58ch; margin: 0; }}
.gn-hero-side {{ display: grid; place-items: center; padding: 1.25rem; border-left: 1px solid {HAIR};
  background: radial-gradient(70% 70% at 50% 45%, rgba(245,181,68,.07) 0%, transparent 70%); }}
@media (max-width: 860px) {{ .gn-hero-side {{ border-left: none; border-top: 1px solid {HAIR}; }} }}
.gn-ring {{ display: block; width: 100%; max-width: 230px; height: auto; }}
.gn-ring-cap {{ font-size: 0.82rem; color: {MUTED}; text-align: center; margin-top: 0.4rem; max-width: 30ch; }}
.gn-stats {{ display: grid; grid-template-columns: repeat(var(--n), minmax(0, 1fr)); border-top: 1px solid {HAIR}; grid-column: 1 / -1; }}
@media (max-width: 680px) {{ .gn-stats {{ grid-template-columns: 1fr; }} }}
.gn-stat {{ padding: 1rem 1.25rem; border-left: 1px solid {HAIR}; }}
.gn-stat:first-child {{ border-left: none; }}
@media (max-width: 680px) {{ .gn-stat {{ border-left: none; border-top: 1px solid {HAIR}; }} .gn-stat:first-child {{ border-top: none; }} }}
.gn-stat b {{ display: block; font-family: {MONO}; font-size: 1.45rem; font-weight: 500; color: {PAPER};
  font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }}
.gn-stat span {{ font-size: 0.82rem; color: {MUTED}; line-height: 1.45; }}

/* Kartlar: Bento ızgarası */
.gn-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 0.75rem; margin: 0.7rem 0 0.4rem 0; }}
.gn-card {{ padding: 1.1rem 1.15rem; border: 1px solid {HAIR}; border-radius: {RADIUS}; background: {SURFACE};
  box-shadow: inset 0 1px 0 rgba(255,255,255,.03); }}
.gn-card:hover {{ border-color: #33456a; }}
.gn-card-head {{ display: flex; align-items: center; gap: 0.65rem; margin-bottom: 0.55rem; }}
.gn-card-icon {{ display: grid; place-items: center; width: 34px; height: 34px; border-radius: 8px; background: {SURFACE_2};
  color: var(--ic, {LAMP}); flex: none; }}
.gn-card h4 {{ font-family: {SANS}; font-size: 1.02rem; font-weight: 600; color: {PAPER}; margin: 0; padding: 0; }}
.gn-card p, .gn-card li {{ color: {MUTED}; font-size: 0.92rem; line-height: 1.6; margin: 0; }}
.gn-card ul {{ margin: 0.15rem 0 0 0; padding-left: 1.1rem; }}
.gn-card li + li {{ margin-top: 0.3rem; }}
.gn-card li b, .gn-card p b {{ color: {PAPER}; font-weight: 600; }}
.gn-step {{ font-family: {MONO}; font-size: 0.78rem; color: {LAMP}; letter-spacing: 0.04em; }}
.gn-cta {{ display: flex; gap: 0.7rem; align-items: center; padding: 0.85rem 1.1rem; margin-top: 0.75rem;
  border: 1px solid {HAIR}; border-left: 3px solid {LAMP}; border-radius: {RADIUS}; background: {SURFACE};
  color: {MUTED}; font-size: 0.93rem; }}
.gn-cta b {{ color: {PAPER}; }}
.gn-cta svg {{ color: {LAMP}; flex: none; }}
</style>
"""


# --- Plotly şablonu ------------------------------------------------------------------------------

pio.templates["gece"] = go.layout.Template(layout=go.Layout(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    separators=",.",                       # Türkçe sayı biçimi: ondalık virgül, binlik nokta
    font=dict(family=MONO, size=12, color=MUTED),
    xaxis=dict(gridcolor=HAIR, linecolor=HAIR, zerolinecolor=HAIR, tickcolor=HAIR),
    yaxis=dict(gridcolor=HAIR, linecolor=HAIR, zerolinecolor=HAIR, tickcolor=HAIR),
    polar=dict(bgcolor="rgba(0,0,0,0)"),
    hoverlabel=dict(bgcolor=SURFACE_2, bordercolor=HAIR, font=dict(family=MONO, color=PAPER)),
    legend=dict(font=dict(color=MUTED)),
    margin=dict(l=10, r=10, t=10, b=10),
))


# --- Bileşenler ----------------------------------------------------------------------------------

def masthead(status_html: str) -> str:
    return (f'<div class="gn-mast" lang="tr"><div class="gn-brand"><div class="gn-logo">'
            f'{icon("moon", 22)}</div><div><div class="gn-overline">Kart dolandırıcılığı · '
            f'izleme paneli</div><h1 class="gn-title">Gece Nöbeti</h1><div class="gn-sub">'
            f'Sessiz bir akışta nadir olanı, işlem anında yakalamak</div></div></div>'
            f'<div class="gn-status" role="status">{status_html}</div></div>')


def status_line(base_url: str, cards: int, transactions: str, label: str = "API bağlı") -> str:
    return (f'<span class="gn-dot"></span><span><b>{esc(label)}</b> · {esc(base_url)}<br>'
            f'{cards} kart · {esc(transactions)} işlem geçmişi</span>')


def section(overline: str, title: str, lede: str = "", index: int | None = None) -> str:
    num = f"<b>{index:02d}</b> · " if index is not None else ""
    lede_html = f'<p class="gn-lede">{esc(lede)}</p>' if lede else ""
    return (f'<div class="gn-section" lang="tr"><div class="gn-overline">{num}{esc(overline)}</div>'
            f'<h3>{esc(title)}</h3>{lede_html}</div>')


def kpis(items: list[tuple[str, str, str | None]], cols: int | None = None) -> str:
    """items: (etiket, değer, işaret) — işaret: 'signal', 'calm' ya da None.
    cols: geniş ekranda sütun sayısı (varsayılan: hepsi tek satırda). Dar bir sütuna
    yerleştirilen ızgarada etiketler kırpılmasın diye daha az sütun verilir."""
    cells = []
    for label, value, mark in items:
        tick = f'<span class="gn-tick {"calm" if mark == "calm" else ""}"></span>' if mark else ""
        cells.append(f'<div class="gn-kpi"><div class="gn-overline">{tick}{esc(label)}</div>'
                     f'<div class="gn-val">{esc(value)}</div></div>')
    return (f'<div class="gn-kpis" lang="tr" style="--n:{cols or len(cells)}">'
            f'{"".join(cells)}</div>')


RISK_STEPS = {"düşük": 1, "orta": 2, "yüksek": 3}


def risk_meter(risk: str) -> str:
    """Üç dilimli risk göstergesi: seviye dolu dilim sayısıyla ve yazıyla verilir (renge bağlı
    değil; yüksek riskte dilimler ayrıca kırmızı)."""
    n = RISK_STEPS.get(risk, 0)
    spans = "".join(f'<span class="{"on" if i < n else ""}"></span>' for i in range(3))
    high = " high" if n == 3 else ""
    return (f'<div class="gn-meter{high}" role="img" aria-label="Risk: {esc(risk)} '
            f'({n}/3)">{spans}</div>')


def verdict(alert: bool, probability: str, expected_loss: str, risk: str) -> str:
    """Karar kartı: renk + simge + yazı (anlam yalnızca renkle verilmez)."""
    accent, tint, mark = ((SIGNAL, "rgba(248,113,113,.08)", "alert") if alert
                          else (OK, "rgba(74,222,128,.06)", "check"))
    return (f'<div class="gn-verdict" lang="tr" style="--accent:{accent};--tint:{tint}">'
            f'<div><div class="gn-overline">Karar</div>'
            f'<div class="gn-big">{icon(mark, 26, accent)}{"Alarm" if alert else "Onay"}</div></div>'
            f'<div><div class="gn-overline">Olasılık</div><div class="gn-mid">{esc(probability)}'
            f'</div></div>'
            f'<div><div class="gn-overline">Beklenen kayıp</div><div class="gn-mid">'
            f'{esc(expected_loss)}</div></div>'
            f'<div><div class="gn-overline">Risk</div><div class="gn-mid">{esc(risk)}</div>'
            f'{risk_meter(risk)}</div></div>')


def reasons(items: list[dict]) -> str:
    """İlk 3 neden; çubuk uzunluğu en güçlü nedene göre."""
    if not items:
        return ""
    top = max(r["katki"] for r in items) or 1.0
    rows = [f'<div class="gn-reason"><div class="gn-n">{i:02d}</div><div><div class="gn-txt">'
            f'{esc(r["aciklama"])}</div><div class="gn-bar" style="width:{100 * r["katki"] / top:.0f}%">'
            f'</div></div><div class="gn-w">{r["katki"]:+.2f}</div></div>'
            for i, r in enumerate(items, start=1)]
    return f'<div class="gn-reasons" role="list">{"".join(rows)}</div>'


def note(text: str) -> str:
    return f'<div class="gn-note-line" lang="tr">{esc(text)}</div>'


DEMO_NOTICE = ("Herkese açık demo · Veriler tamamen sentetiktir (Sparkov simülatörü); gerçek kişi "
               "ya da kart yoktur. Bu proje eğitim ve portföy amaçlıdır. Gerçek kart numarası "
               "ya da kişisel bilgi girmeyin.")


def demo_notice() -> str:
    """Demo modunda sayfanın üstünde kalıcı bilgilendirme bandı (alarm değil: sakin vurgu)."""
    return (f'<div class="gn-banner" lang="tr" role="note">{icon("info", 18)}'
            f'<div>{esc(DEMO_NOTICE)}</div></div>')


def footer() -> str:
    """Alt bilgi: veri kaynağı ve lisanslar (her iki modda)."""
    kaggle = "https://www.kaggle.com/datasets/kartik2112/fraud-detection"
    sparkov = "https://github.com/namebrandon/Sparkov_Data_Generation"
    link = f'style="color:{MUTED};text-decoration:underline"'
    return (f'<div class="gn-note-line" lang="tr" role="contentinfo" style="margin-top:2.4rem;'
            f'padding-top:0.9rem;border-top:1px solid {HAIR}">Veri: <a {link} href="{kaggle}" '
            f'target="_blank" rel="noopener">Credit Card Transactions Fraud Detection</a> (Kaggle, '
            f'CC0: Public Domain) · <a {link} href="{sparkov}" target="_blank" rel="noopener">'
            f'Sparkov Data Generation</a> simülatörüyle üretilmiş sentetik veri (MIT) · Kod: MIT, '
            f'© 2026 Tolga Arslan</div>')


# --- Nöbet saati (imza öğesi) ---------------------------------------------------------------------

def _xy(hour: float, r: float, c: float = 100.0) -> tuple[float, float]:
    """Saat → SVG koordinatı (00 tepede, saat yönünde)."""
    a = math.radians(hour / 24 * 360 - 90)
    return c + r * math.cos(a), c + r * math.sin(a)


def night_ring(share: float | None, label: str = "gece") -> str:
    """24 saatlik kadran: 24 çentik, gece dilimi (22:00–04:00) amber yay; ortada dolandırıcılığın
    gece payı. `share` None ise yalnızca kadran çizilir (rakam uydurulmaz)."""
    start, end = NIGHT
    span = (end - start) % 24
    x1, y1 = _xy(start, 78)
    x2, y2 = _xy(end, 78)
    large = 1 if span > 12 else 0
    ticks = []
    for h in range(24):
        major = h % 6 == 0
        xa, ya = _xy(h, 88)
        xb, yb = _xy(h, 82 if major else 85)
        ticks.append(f'<line x1="{xa:.1f}" y1="{ya:.1f}" x2="{xb:.1f}" y2="{yb:.1f}" stroke="'
                     f'{MUTED if major else HAIR}" stroke-width="{2 if major else 1.2}"/>')
    labels = "".join(
        f'<text x="{_xy(h, 66)[0]:.1f}" y="{_xy(h, 66)[1] + 4:.1f}" text-anchor="middle" '
        f'font-family="IBM Plex Mono, monospace" font-size="10" fill="{MUTED}">{h:02d}</text>'
        for h in (0, 6, 12, 18))
    center = (f'<text x="100" y="98" text-anchor="middle" font-family="IBM Plex Mono, monospace" '
              f'font-size="30" font-weight="500" fill="{PAPER}">%{round(100 * share)}</text>'
              f'<text x="100" y="118" text-anchor="middle" font-family="IBM Plex Sans, sans-serif" '
              f'font-size="11" fill="{MUTED}">{esc(label)}</text>') if share is not None else ""
    desc = (f"24 saatlik kadran; 22:00-04:00 gece dilimi vurgulu. Dolandırıcılığın yüzde "
            f"{round(100 * share)}'i bu saatlerde." if share is not None
            else "24 saatlik kadran; 22:00-04:00 gece dilimi vurgulu.")
    return (f'<svg class="gn-ring" viewBox="0 0 200 200" role="img" aria-label="{esc(desc)}">'
            f'<circle cx="100" cy="100" r="78" fill="none" stroke="{HAIR}" stroke-width="10"/>'
            f'<path d="M {x1:.1f} {y1:.1f} A 78 78 0 {large} 1 {x2:.1f} {y2:.1f}" fill="none" '
            f'stroke="{LAMP}" stroke-width="10" stroke-linecap="round"/>{"".join(ticks)}{labels}'
            f'{center}</svg>')


# --- Karşılama ekranı ------------------------------------------------------------------------------

def card(icon_name: str, title: str, body_html: str, icon_color: str | None = None) -> str:
    """Bilgi kartı. `body_html` çağıran tarafından kaçışlanmış HTML olmalıdır."""
    style = f' style="--ic:{icon_color}"' if icon_color else ""
    return (f'<article class="gn-card" lang="tr"><div class="gn-card-head"><div class="gn-card-icon"'
            f'{style}>{icon(icon_name)}</div><h4>{esc(title)}</h4></div>{body_html}</article>')


def step_card(n: int, title: str, items: list[str], icon_name: str) -> str:
    """Numaralı kullanım adımı. `items` düz metindir (kaçışlanır); **kalın** desteklenir."""
    def fmt(s: str) -> str:
        parts = esc(s).split("**")
        return "".join(f"<b>{p}</b>" if i % 2 else p for i, p in enumerate(parts))
    lis = "".join(f"<li>{fmt(s)}</li>" for s in items)
    return (f'<article class="gn-card" lang="tr"><div class="gn-card-head"><div class="gn-card-icon">'
            f'{icon(icon_name)}</div><div><div class="gn-step">ADIM {n:02d}</div><h4>{esc(title)}'
            f'</h4></div></div><ul>{lis}</ul></article>')


def grid(cards: list[str]) -> str:
    return f'<div class="gn-grid">{"".join(cards)}</div>'


def hero(title: str, text: str, stats: list[tuple[str, str]], night_share: float | None = None,
         accent: str | None = None) -> str:
    """Karşılama başlığı, nöbet saati ve öne çıkan sonuçlar (değer, açıklama). `accent`,
    başlıkta amber vurgulanacak ifade. Rakam yoksa boş alan bırakılmaz."""
    t = esc(title)
    if accent and accent in title:
        t = t.replace(esc(accent), f"<em>{esc(accent)}</em>", 1)
    side = ""
    if night_share is not None:
        side = (f'<div class="gn-hero-side">{night_ring(night_share)}<div class="gn-ring-cap">'
                f'Test dönemindeki dolandırıcılığın gece 22:00–04:00 arasına düşen payı</div></div>')
    layout = "" if side else ' style="grid-template-columns:1fr"'
    stat_html = ""
    if stats:
        cells = "".join(f'<div class="gn-stat"><b>{esc(v)}</b><span>{esc(label)}</span></div>'
                        for v, label in stats)
        stat_html = f'<div class="gn-stats" style="--n:{len(stats)}">{cells}</div>'
    return (f'<section class="gn-hero" lang="tr" aria-label="Proje özeti"{layout}>'
            f'<div class="gn-hero-main"><div class="gn-overline">Proje hakkında</div><h2>{t}</h2>'
            f'<p>{esc(text)}</p></div>{side}{stat_html}</section>')


def cta(text_html: str) -> str:
    return f'<div class="gn-cta" lang="tr">{icon("arrow", 18)}<div>{text_html}</div></div>'

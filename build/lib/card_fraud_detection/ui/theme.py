"""Panelin tasarım sistemi: "Gece Nöbeti" (docs/tasarim/gece-nobeti.md).

Koyu mürekkep zemin, ince çizgiler, tek bir sinyal rengi. Sinyal (kızıl-turuncu) yalnızca
alarm ve dolandırıcılık içindir; başka hiçbir şey bu rengi kullanmaz. Renkler dataviz
doğrulayıcısından geçti (koyu yüzey #121a28: açıklık bandı, renk körlüğü ayrımı, kontrast).

Bileşenler HTML üretir; içlerine giren tüm metinler `esc` ile kaçışlanır.
"""

from __future__ import annotations

from html import escape

import plotly.graph_objects as go
import plotly.io as pio


def esc(s) -> str:
    """HTML kaçışı + '$' → '&#36;': Streamlit markdown, HTML içinde bile iki '$' arasını
    matematik formülü sayar (ör. "$912 ... $10")."""
    return escape(str(s)).replace("$", "&#36;")

INK = "#0b101a"          # zemin
SURFACE = "#121a28"      # kart / panel
SURFACE_2 = "#172133"    # vurgulu yüzey
HAIR = "#26324a"         # ince çizgi
PAPER = "#ebe7de"        # birincil metin
MUTED = "#8b93a5"        # ikincil metin
SIGNAL = "#f05a36"       # yalnızca alarm / dolandırıcılık
CALM = "#6f8fd1"         # normal işlem, sakin eylem

SERIF = "'Instrument Serif', 'Iowan Old Style', Georgia, serif"
SANS = "'Instrument Sans', system-ui, -apple-system, 'Segoe UI', sans-serif"
MONO = "'Geist Mono', 'JetBrains Mono', ui-monospace, monospace"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Geist+Mono:wght@400;500&family=Instrument+Sans:wght@400;500;600&family=Instrument+Serif:ital@0;1&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, button, input, select, textarea {{ font-family: {SANS}; }}
.stApp {{ background: {INK}; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stAppDeployButton"], [data-testid="stMainMenu"], #MainMenu, footer {{ display: none; }}
.block-container {{ max-width: 1240px; padding-top: 2.2rem; padding-bottom: 4rem; }}

/* Sekmeler: eş aralıklı, büyük harf, ince alt çizgi (büyük harf Türkçe kurallarla: lang=tr) */
.stTabs [role="tablist"] {{ gap: 2.2rem; border-bottom: 1px solid {HAIR}; }}
.stTabs [data-testid="stTab"] {{ padding: 0.9rem 0; background: transparent; }}
.stTabs [data-testid="stTab"] p {{ font-family: {MONO}; font-size: 0.72rem; letter-spacing: 0.16em;
  text-transform: uppercase; color: {MUTED}; }}
.stTabs [data-testid="stTab"][aria-selected="true"] p {{ color: {PAPER}; }}
.stTabs .react-aria-SelectionIndicator {{ background: {PAPER}; height: 1px; }}

/* Başlık: Streamlit'in kendi h1 stili ezmesin */
h1.gn-title, .stMarkdown h1.gn-title {{ font-family: {SERIF} !important; font-weight: 400 !important; }}

/* Düğmeler: köşeli, eş aralıklı */
.stButton > button, .stFormSubmitButton > button {{ border-radius: 2px; font-family: {MONO};
  font-size: 0.7rem; letter-spacing: 0.08em; text-transform: uppercase; border: 1px solid {HAIR};
  background: {SURFACE}; color: {PAPER}; padding: 0.6rem 0.9rem; white-space: nowrap; }}
.stButton > button p, .stFormSubmitButton > button p {{ font-family: {MONO}; font-size: 0.7rem; }}
.stButton > button:hover, .stFormSubmitButton > button:hover {{ border-color: {MUTED}; color: {PAPER}; }}
/* Birincil eylem: kâğıt rengi. Form düğmesinin kind değeri farklı ("primaryFormSubmit"),
   bu yüzden form gönderme düğmesi doğrudan hedeflenir. */
.stButton > button[kind="primary"], .stFormSubmitButton button {{
  background: {PAPER}; color: {INK}; border-color: {PAPER}; }}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton button:hover {{
  background: #ffffff; color: {INK}; border-color: #ffffff; }}
.stButton > button[kind="primary"] p, .stFormSubmitButton button p {{ color: {INK}; }}

/* Form öğeleri ve genişletici */
[data-testid="stExpander"] details {{ border: 1px solid {HAIR}; border-radius: 2px; background: {SURFACE}; }}
[data-testid="stExpander"] summary p {{ font-family: {MONO}; font-size: 0.72rem; letter-spacing: 0.14em;
  text-transform: uppercase; color: {MUTED}; }}
[data-testid="stWidgetLabel"] p {{ font-family: {MONO}; font-size: 0.68rem; letter-spacing: 0.14em;
  text-transform: uppercase; color: {MUTED}; }}
[data-testid="stCaptionContainer"] {{ color: {MUTED}; }}
[data-testid="stDataFrame"] {{ border: 1px solid {HAIR}; border-radius: 2px; }}

/* Bileşenler */
.gn-overline {{ font-family: {MONO}; font-size: 0.7rem; letter-spacing: 0.2em; text-transform: uppercase;
  color: {MUTED}; }}
.gn-mast {{ display: flex; justify-content: space-between; align-items: flex-end; gap: 2rem;
  flex-wrap: wrap; padding-bottom: 1.4rem; margin-bottom: 0.6rem; border-bottom: 1px solid {HAIR}; }}
.gn-title {{ font-family: {SERIF}; font-weight: 400; font-size: clamp(2.6rem, 6vw, 4.4rem);
  line-height: 0.95; color: {PAPER}; margin: 0.5rem 0 0.4rem 0; letter-spacing: -0.01em; }}
.gn-sub {{ font-family: {SERIF}; font-style: italic; font-size: 1.25rem; color: {MUTED}; }}
.gn-status {{ font-family: {MONO}; font-size: 0.72rem; letter-spacing: 0.08em; color: {MUTED};
  text-align: right; line-height: 1.8; }}
.gn-status b {{ color: {PAPER}; font-weight: 500; }}
.gn-dot {{ display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: {CALM};
  margin-right: 0.5rem; box-shadow: 0 0 0 3px rgba(111,143,209,0.18); vertical-align: 1px; }}

.gn-section {{ margin: 2.2rem 0 0.9rem 0; }}
.gn-section h3 {{ font-family: {SERIF}; font-weight: 400; font-size: 1.9rem; color: {PAPER}; margin: 0.3rem 0 0 0; }}
.gn-lede {{ color: {MUTED}; font-size: 0.98rem; max-width: 62ch; line-height: 1.6; }}

/* Metrik ızgarası: geniş ekranda tek satır, ortada 3, darda 2 sütun. Ayırıcılar hücrelerin
   gölgesi; kapsayıcı taşanı kırpar. Boş kalan hücreler yüzeyle aynı renkte, göze batmaz. */
.gn-kpis {{ display: grid; grid-template-columns: repeat(var(--n), minmax(0, 1fr));
  background: {SURFACE}; border: 1px solid {HAIR}; overflow: hidden; margin: 1.2rem 0 0.6rem 0; }}
@media (max-width: 980px) {{ .gn-kpis {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }} }}
@media (max-width: 560px) {{ .gn-kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
.gn-kpi {{ padding: 1.1rem 1.2rem 1.2rem 1.2rem; box-shadow: 1px 0 0 {HAIR}, 0 1px 0 {HAIR}; }}
.gn-kpi .gn-overline {{ display: flex; align-items: center; gap: 0.5rem; font-size: 0.64rem;
  letter-spacing: 0.14em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
/* Streamlit'in başlıklara eklediği bağlantı simgesi tasarıma yabancı */
[data-testid="stHeaderActionElements"], .gn-section h3 a {{ display: none !important; }}
.gn-kpi .gn-val {{ font-family: {SERIF}; font-size: 2.5rem; line-height: 1; color: {PAPER};
  margin-top: 0.7rem; font-variant-numeric: lining-nums; }}
.gn-kpi .gn-note {{ font-family: {MONO}; font-size: 0.66rem; color: {MUTED}; margin-top: 0.5rem; }}
.gn-tick {{ display: inline-block; width: 6px; height: 6px; background: {SIGNAL}; border-radius: 50%; }}
.gn-tick.calm {{ background: {CALM}; }}

.gn-verdict {{ border: 1px solid {HAIR}; background: {SURFACE}; display: grid;
  grid-template-columns: minmax(200px, 1.2fr) repeat(3, minmax(120px, 1fr)); margin: 1rem 0; }}
.gn-verdict > div {{ padding: 1.3rem 1.4rem; border-left: 1px solid {HAIR}; }}
.gn-verdict > div:first-child {{ border-left: 3px solid var(--accent); }}
.gn-verdict .gn-big {{ font-family: {SERIF}; font-size: 2.6rem; line-height: 1; color: {PAPER}; margin-top: 0.6rem; }}
.gn-verdict .gn-mid {{ font-family: {SERIF}; font-size: 1.8rem; line-height: 1; color: {PAPER}; margin-top: 0.7rem; }}
@media (max-width: 760px) {{ .gn-verdict {{ grid-template-columns: 1fr 1fr; }}
  .gn-verdict > div {{ border-left: none; border-top: 1px solid {HAIR}; }} }}

.gn-reasons {{ margin: 0.6rem 0 0.4rem 0; }}
.gn-reason {{ display: grid; grid-template-columns: 1.6rem minmax(0, 1fr) 4.5rem; align-items: center;
  gap: 0.9rem; padding: 0.85rem 0; border-top: 1px solid {HAIR}; }}
.gn-reason:last-child {{ border-bottom: 1px solid {HAIR}; }}
.gn-reason .gn-n {{ font-family: {SERIF}; font-size: 1.4rem; color: {MUTED}; }}
.gn-reason .gn-txt {{ color: {PAPER}; font-size: 0.98rem; }}
.gn-reason .gn-bar {{ height: 2px; background: {SIGNAL}; margin-top: 0.55rem; }}
.gn-reason .gn-w {{ font-family: {MONO}; font-size: 0.72rem; color: {MUTED}; text-align: right; }}
.gn-note-line {{ font-family: {MONO}; font-size: 0.68rem; letter-spacing: 0.04em; color: {MUTED};
  line-height: 1.7; margin-top: 0.6rem; }}
</style>
"""


# --- Plotly şablonu ------------------------------------------------------------------------------

pio.templates["gece"] = go.layout.Template(layout=go.Layout(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    separators=",.",                       # Türkçe sayı biçimi: ondalık virgül, binlik nokta
    font=dict(family=MONO, size=11, color=MUTED),
    xaxis=dict(gridcolor=HAIR, linecolor=HAIR, zerolinecolor=HAIR, tickcolor=HAIR),
    yaxis=dict(gridcolor=HAIR, linecolor=HAIR, zerolinecolor=HAIR, tickcolor=HAIR),
    polar=dict(bgcolor="rgba(0,0,0,0)"),
    hoverlabel=dict(bgcolor=SURFACE_2, bordercolor=HAIR, font=dict(family=MONO, color=PAPER)),
    legend=dict(font=dict(color=MUTED)),
    margin=dict(l=10, r=10, t=10, b=10),
))


# --- Bileşenler ----------------------------------------------------------------------------------

def masthead(status_html: str) -> str:
    return (f'<div class="gn-mast" lang="tr"><div><div class="gn-overline">Kart dolandırıcılığı · izleme '
            f'paneli</div><h1 class="gn-title">Gece Nöbeti</h1><div class="gn-sub">sessiz bir '
            f'akışta nadir olanı yakalamak</div></div><div class="gn-status">{status_html}</div>'
            f'</div>')


def status_line(base_url: str, cards: int, transactions: str) -> str:
    return (f'<span class="gn-dot"></span><b>API bağlı</b><br>{esc(base_url)}<br>'
            f'{cards} kart · {esc(transactions)} işlem geçmişi')


def section(overline: str, title: str, lede: str = "") -> str:
    lede_html = f'<p class="gn-lede">{esc(lede)}</p>' if lede else ""
    return (f'<div class="gn-section" lang="tr"><div class="gn-overline">{esc(overline)}</div>'
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


def verdict(alert: bool, probability: str, expected_loss: str, risk: str) -> str:
    accent = SIGNAL if alert else CALM
    return (f'<div class="gn-verdict" lang="tr" style="--accent:{accent}">'
            f'<div><div class="gn-overline">Karar</div>'
            f'<div class="gn-big">{"Alarm" if alert else "Onay"}</div></div>'
            f'<div><div class="gn-overline">Olasılık</div><div class="gn-mid">{esc(probability)}'
            f'</div></div>'
            f'<div><div class="gn-overline">Beklenen kayıp</div><div class="gn-mid">'
            f'{esc(expected_loss)}</div></div>'
            f'<div><div class="gn-overline">Risk</div><div class="gn-mid">{esc(risk)}</div></div>'
            f'</div>')


def reasons(items: list[dict]) -> str:
    """İlk 3 neden; çubuk uzunluğu en güçlü nedene göre."""
    if not items:
        return ""
    top = max(r["katki"] for r in items) or 1.0
    rows = [f'<div class="gn-reason"><div class="gn-n">{i}</div><div><div class="gn-txt">'
            f'{esc(r["aciklama"])}</div><div class="gn-bar" style="width:{100 * r["katki"] / top:.0f}%">'
            f'</div></div><div class="gn-w">{r["katki"]:+.2f}</div></div>'
            for i, r in enumerate(items, start=1)]
    return f'<div class="gn-reasons">{"".join(rows)}</div>'


def note(text: str) -> str:
    return f'<div class="gn-note-line" lang="tr">{esc(text)}</div>'

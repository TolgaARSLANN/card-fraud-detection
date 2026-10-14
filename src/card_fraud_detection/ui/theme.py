"""Panelin tasarım sistemi (v2): koyu, veri yoğun bir izleme konsolu.

Kaynak: ui-ux-pro-max tasarım sistemi önerisi ("Dark Mode (OLED)", Fira Sans + Fira Code),
bu panele uyarlanmış hâli; gerekçeler docs/tasarim/arayuz-v2.md.

Renk rolleri (her biri tek bir anlam taşır, anlam yalnızca renkle verilmez):
- PRIMARY (mavi): eylem düğmeleri, seçili sekme, odak.
- SIGNAL (kırmızı): yalnızca alarm ve dolandırıcılık; yanında her zaman simge + yazı.
- OK (yeşil): yalnızca "onay" kararı.
- WARN (kehribar): orta risk.
- CALM (gök mavisi): normal işlem noktaları ve sakin vurgular (grafiklerde).
Metin/zemin kontrastları WCAG AA (4,5:1) üzerindedir.

Bileşenler HTML üretir; içlerine giren tüm metinler `esc` ile kaçışlanır. HTML tek satırda
üretilir (Markdown, 4 boşlukla başlayan satırları kod bloğu sayar).
"""

from __future__ import annotations

from html import escape

import plotly.graph_objects as go
import plotly.io as pio


def esc(s) -> str:
    """HTML kaçışı + '$' → '&#36;': Streamlit markdown, HTML içinde bile iki '$' arasını
    matematik formülü sayar (ör. "$912 ... $10")."""
    return escape(str(s)).replace("$", "&#36;")


# --- Tasarım belirteçleri ------------------------------------------------------------------------
INK = "#020617"          # zemin (slate-950)
SURFACE = "#0e1223"      # kart
SURFACE_2 = "#151b30"    # vurgulu yüzey, ipucu kutusu
HAIR = "#26314a"         # kenarlık, ızgara
PAPER = "#f8fafc"        # birincil metin (zemin üzerinde 19:1)
MUTED = "#94a3b8"        # ikincil metin (kart üzerinde 7:1)
PRIMARY = "#2563eb"      # eylem düğmesi (beyaz yazıyla 5,2:1)
PRIMARY_SOFT = "#93c5fd"  # bağlantı, odak halkası, seçili sekme
SIGNAL = "#f87171"       # alarm / dolandırıcılık (kart üzerinde 6:1)
OK = "#4ade80"           # onay
WARN = "#fbbf24"         # orta risk
CALM = "#60a5fa"         # normal işlem, sakin vurgu

SANS = "'Fira Sans', system-ui, -apple-system, 'Segoe UI', sans-serif"
MONO = "'Fira Code', ui-monospace, 'SFMono-Regular', monospace"
RADIUS = "12px"

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
}


def icon(name: str, size: int = 20, color: str = "currentColor") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
            f'{ICONS[name]}</svg>')


CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&family=Fira+Sans:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, button, input, select, textarea {{ font-family: {SANS}; }}
.stApp {{ background: {INK}; color: {PAPER}; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stAppDeployButton"], [data-testid="stMainMenu"], #MainMenu, footer {{ display: none; }}
.block-container {{ max-width: 1200px; padding-top: 2rem; padding-bottom: 4rem; }}
[data-testid="stHeaderActionElements"], .gn-section h3 a {{ display: none !important; }}

/* Hareket: kısa, anlamlı; "hareketi azalt" tercihinde kapalı */
.gn-card, .stButton > button, .stFormSubmitButton > button {{ transition: border-color .2s ease, background-color .2s ease, transform .2s ease; }}
@media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ transition: none !important; animation: none !important; }} }}

/* Odak: klavye kullanıcıları için her zaman görünür */
a:focus-visible, button:focus-visible, [role="tab"]:focus-visible, input:focus-visible, [tabindex]:focus-visible {{
  outline: 2px solid {PRIMARY_SOFT} !important; outline-offset: 2px; border-radius: 6px; }}
a {{ color: {PRIMARY_SOFT}; }}

/* Sekmeler */
.stTabs [role="tablist"] {{ gap: 0.4rem; border-bottom: 1px solid {HAIR}; }}
.stTabs [data-testid="stTab"] {{ padding: 0.75rem 1rem; background: transparent; border-radius: 8px 8px 0 0; }}
.stTabs [data-testid="stTab"]:hover {{ background: {SURFACE}; }}
.stTabs [data-testid="stTab"] p {{ font-size: 0.95rem; font-weight: 500; color: {MUTED}; }}
.stTabs [data-testid="stTab"][aria-selected="true"] p {{ color: {PAPER}; font-weight: 600; }}
.stTabs .react-aria-SelectionIndicator {{ background: {PRIMARY_SOFT}; height: 2px; }}

/* Düğmeler: en az 44 px yükseklik; birincil eylem mavi */
.stButton > button, .stFormSubmitButton > button {{ min-height: 44px; border-radius: 8px; font-weight: 600;
  font-size: 0.92rem; border: 1px solid {HAIR}; background: {SURFACE}; color: {PAPER}; cursor: pointer; }}
.stButton > button p, .stFormSubmitButton > button p {{ font-weight: 600; font-size: 0.92rem; }}
.stButton > button:hover, .stFormSubmitButton > button:hover {{ border-color: {PRIMARY_SOFT}; color: {PAPER}; }}
.stButton > button[kind="primary"], .stFormSubmitButton button {{ background: {PRIMARY}; color: #fff; border-color: {PRIMARY}; }}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton button:hover {{ background: #1d4ed8; border-color: #1d4ed8; color: #fff; }}
.stButton > button[kind="primary"] p, .stFormSubmitButton button p {{ color: #fff; }}
.stButton > button:disabled {{ opacity: 0.45; cursor: not-allowed; }}

/* Form öğeleri, genişletici, tablo */
[data-testid="stWidgetLabel"] p {{ font-size: 0.85rem; font-weight: 500; color: {MUTED}; }}
[data-baseweb="select"] > div, [data-baseweb="input"], .stDateInput input, .stTimeInput input {{ border-radius: 8px !important; }}
[data-testid="stExpander"] details {{ border: 1px solid {HAIR}; border-radius: {RADIUS}; background: {SURFACE}; }}
[data-testid="stExpander"] summary p {{ font-weight: 500; color: {PAPER}; }}
[data-testid="stCaptionContainer"] {{ color: {MUTED}; }}
[data-testid="stDataFrame"] {{ border: 1px solid {HAIR}; border-radius: {RADIUS}; overflow: hidden; }}
[data-testid="stAlert"] {{ border-radius: {RADIUS}; }}

/* Başlık */
.gn-mast {{ display: flex; justify-content: space-between; align-items: center; gap: 1.5rem; flex-wrap: wrap;
  padding-bottom: 1.25rem; margin-bottom: 0.75rem; border-bottom: 1px solid {HAIR}; }}
.gn-brand {{ display: flex; align-items: center; gap: 0.9rem; }}
.gn-logo {{ display: grid; place-items: center; width: 48px; height: 48px; border-radius: 12px;
  background: linear-gradient(135deg, #1e3a8a, {PRIMARY}); color: #fff; }}
.gn-overline {{ font-family: {MONO}; font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase; color: {MUTED}; }}
.gn-title {{ font-family: {SANS}; font-weight: 700; font-size: clamp(1.6rem, 3.5vw, 2.2rem); line-height: 1.15;
  color: {PAPER}; margin: 0.1rem 0 0 0; letter-spacing: -0.01em; }}
h1.gn-title, .stMarkdown h1.gn-title {{ font-family: {SANS} !important; padding: 0 !important; }}
.gn-sub {{ font-size: 0.95rem; color: {MUTED}; margin-top: 0.15rem; }}
.gn-status {{ display: flex; align-items: center; gap: 0.75rem; padding: 0.65rem 1.25rem 0.65rem 1rem;
  border: 1px solid {HAIR}; border-radius: 999px; background: {SURFACE}; font-size: 0.82rem; line-height: 1.5;
  color: {MUTED}; max-width: 100%; }}
.gn-status b {{ color: {PAPER}; font-weight: 600; }}
.gn-dot {{ width: 8px; height: 8px; border-radius: 50%; background: {OK}; box-shadow: 0 0 0 4px rgba(74,222,128,.15); flex: none; }}

/* Bölüm başlığı */
.gn-section {{ margin: 2rem 0 0.75rem 0; }}
.gn-section h3 {{ font-family: {SANS}; font-weight: 700; font-size: 1.5rem; color: {PAPER}; margin: 0.25rem 0 0 0; padding: 0; }}
.gn-lede {{ color: {MUTED}; font-size: 1rem; max-width: 68ch; line-height: 1.6; margin: 0.4rem 0 0 0; }}

/* Metrik kartları */
.gn-kpis {{ display: grid; grid-template-columns: repeat(var(--n), minmax(0, 1fr)); gap: 0.75rem; margin: 1rem 0 0.5rem 0; }}
@media (max-width: 980px) {{ .gn-kpis {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }} }}
@media (max-width: 560px) {{ .gn-kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
.gn-kpi {{ padding: 1rem 1.1rem; background: {SURFACE}; border: 1px solid {HAIR}; border-radius: {RADIUS}; min-width: 0; }}
/* Metrik etiketleri büyük harf değil: Türkçe büyük harf kuralı İngilizce terimleri bozuyordu
   ("Precision" → "PRECİSİON"); normal yazım daha okunaklı */
.gn-kpi .gn-overline {{ display: flex; align-items: center; gap: 0.45rem; font-family: {SANS}; font-size: 0.82rem;
  font-weight: 500; letter-spacing: 0; text-transform: none; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.gn-kpi .gn-val {{ font-family: {MONO}; font-size: 1.7rem; font-weight: 500; line-height: 1.1; color: {PAPER};
  margin-top: 0.55rem; font-variant-numeric: tabular-nums; }}
.gn-tick {{ display: inline-block; width: 8px; height: 8px; background: {SIGNAL}; border-radius: 50%; flex: none; }}
.gn-tick.calm {{ background: {CALM}; }}

/* Karar */
.gn-verdict {{ border: 1px solid {HAIR}; border-left: 4px solid var(--accent); border-radius: {RADIUS};
  background: {SURFACE}; display: grid; grid-template-columns: minmax(220px, 1.3fr) repeat(3, minmax(120px, 1fr)); margin: 1rem 0; overflow: hidden; }}
.gn-verdict > div {{ padding: 1.1rem 1.25rem; border-left: 1px solid {HAIR}; }}
.gn-verdict > div:first-child {{ border-left: none; background: var(--tint); }}
.gn-verdict .gn-big {{ display: flex; align-items: center; gap: 0.6rem; font-size: 1.9rem; font-weight: 700;
  line-height: 1.1; color: var(--accent); margin-top: 0.4rem; }}
.gn-verdict .gn-mid {{ font-family: {MONO}; font-size: 1.35rem; font-weight: 500; line-height: 1.2; color: {PAPER};
  margin-top: 0.5rem; font-variant-numeric: tabular-nums; }}
@media (max-width: 760px) {{ .gn-verdict {{ grid-template-columns: 1fr 1fr; }}
  .gn-verdict > div {{ border-left: none; border-top: 1px solid {HAIR}; }} }}

/* Nedenler */
.gn-reasons {{ margin: 0.5rem 0; border: 1px solid {HAIR}; border-radius: {RADIUS}; background: {SURFACE}; overflow: hidden; }}
.gn-reason {{ display: grid; grid-template-columns: 2rem minmax(0, 1fr) 4.5rem; align-items: center; gap: 0.9rem;
  padding: 0.9rem 1.1rem; border-top: 1px solid {HAIR}; }}
.gn-reason:first-child {{ border-top: none; }}
.gn-reason .gn-n {{ display: grid; place-items: center; width: 28px; height: 28px; border-radius: 50%;
  background: {SURFACE_2}; font-family: {MONO}; font-size: 0.85rem; color: {PAPER}; }}
.gn-reason .gn-txt {{ color: {PAPER}; font-size: 1rem; line-height: 1.45; }}
.gn-reason .gn-bar {{ height: 4px; border-radius: 4px; background: {SIGNAL}; margin-top: 0.5rem; }}
.gn-reason .gn-w {{ font-family: {MONO}; font-size: 0.8rem; color: {MUTED}; text-align: right; font-variant-numeric: tabular-nums; }}

.gn-note-line {{ font-size: 0.82rem; color: {MUTED}; line-height: 1.6; margin-top: 0.5rem; }}

/* Bilgi bandı */
.gn-banner {{ display: flex; gap: 0.75rem; align-items: flex-start; padding: 0.85rem 1rem; margin: 0.25rem 0 1rem 0;
  border: 1px solid #1e3a8a; border-radius: {RADIUS}; background: #0b1a3a; color: {PAPER}; font-size: 0.9rem; line-height: 1.55; }}
.gn-banner svg {{ flex: none; margin-top: 2px; color: {PRIMARY_SOFT}; }}

/* Karşılama */
.gn-hero {{ display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 1.5rem; align-items: stretch;
  padding: 1.75rem; margin: 1.25rem 0 0.5rem 0; border: 1px solid {HAIR}; border-radius: 16px;
  background: radial-gradient(120% 140% at 0% 0%, #10224a 0%, {SURFACE} 55%); }}
@media (max-width: 860px) {{ .gn-hero {{ grid-template-columns: 1fr; padding: 1.25rem; }} }}
.gn-hero h2 {{ font-family: {SANS}; font-size: clamp(1.5rem, 3vw, 2rem); font-weight: 700; line-height: 1.2; color: {PAPER}; margin: 0.4rem 0 0.6rem 0; padding: 0; }}
.gn-hero p {{ color: {MUTED}; font-size: 1rem; line-height: 1.65; max-width: 60ch; margin: 0; }}
.gn-stats {{ display: grid; gap: 0.6rem; }}
.gn-stat {{ padding: 0.8rem 1rem; border: 1px solid {HAIR}; border-radius: 10px; background: rgba(2,6,23,.55); }}
.gn-stat b {{ display: block; font-family: {MONO}; font-size: 1.35rem; font-weight: 500; color: {PAPER}; font-variant-numeric: tabular-nums; }}
.gn-stat span {{ font-size: 0.82rem; color: {MUTED}; }}
.gn-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 0.9rem; margin: 0.75rem 0 0.5rem 0; }}
.gn-card {{ padding: 1.15rem 1.2rem; border: 1px solid {HAIR}; border-radius: {RADIUS}; background: {SURFACE}; }}
.gn-card:hover {{ border-color: #3b4a6b; }}
.gn-card-head {{ display: flex; align-items: center; gap: 0.7rem; margin-bottom: 0.6rem; }}
.gn-card-icon {{ display: grid; place-items: center; width: 38px; height: 38px; border-radius: 10px; background: {SURFACE_2}; color: var(--ic, {PRIMARY_SOFT}); flex: none; }}
.gn-card h4 {{ font-family: {SANS}; font-size: 1.05rem; font-weight: 600; color: {PAPER}; margin: 0; padding: 0; }}
.gn-card p, .gn-card li {{ color: {MUTED}; font-size: 0.93rem; line-height: 1.6; margin: 0; }}
.gn-card ul, .gn-card ol {{ margin: 0.2rem 0 0 0; padding-left: 1.15rem; }}
.gn-card li + li {{ margin-top: 0.3rem; }}
.gn-card li b, .gn-card p b {{ color: {PAPER}; font-weight: 600; }}
.gn-step {{ display: inline-grid; place-items: center; width: 26px; height: 26px; border-radius: 50%; background: {PRIMARY};
  color: #fff; font-family: {MONO}; font-size: 0.8rem; font-weight: 500; flex: none; }}
.gn-cta {{ display: flex; gap: 0.75rem; align-items: center; padding: 0.9rem 1.1rem; margin-top: 0.9rem;
  border: 1px dashed #3b4a6b; border-radius: {RADIUS}; color: {MUTED}; font-size: 0.93rem; }}
.gn-cta b {{ color: {PAPER}; }}
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
            f'{icon("shield", 26)}</div><div><div class="gn-overline">Kart dolandırıcılığı · '
            f'izleme paneli</div><h1 class="gn-title">Gece Nöbeti</h1><div class="gn-sub">'
            f'Sessiz bir akışta nadir olanı, işlem anında yakalamak</div></div></div>'
            f'<div class="gn-status" role="status">{status_html}</div></div>')


def status_line(base_url: str, cards: int, transactions: str, label: str = "API bağlı") -> str:
    return (f'<span class="gn-dot"></span><span><b>{esc(label)}</b> · {esc(base_url)}<br>'
            f'{cards} kart · {esc(transactions)} işlem geçmişi</span>')


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
    """Karar kartı: renk + simge + yazı (anlam yalnızca renkle verilmez)."""
    accent, tint, mark = ((SIGNAL, "rgba(248,113,113,.10)", "alert") if alert
                          else (OK, "rgba(74,222,128,.08)", "check"))
    risk_color = {"yüksek": SIGNAL, "orta": WARN}.get(risk, PAPER)
    return (f'<div class="gn-verdict" lang="tr" style="--accent:{accent};--tint:{tint}">'
            f'<div><div class="gn-overline">Karar</div>'
            f'<div class="gn-big">{icon(mark, 28, accent)}{"Alarm" if alert else "Onay"}</div></div>'
            f'<div><div class="gn-overline">Olasılık</div><div class="gn-mid">{esc(probability)}'
            f'</div></div>'
            f'<div><div class="gn-overline">Beklenen kayıp</div><div class="gn-mid">'
            f'{esc(expected_loss)}</div></div>'
            f'<div><div class="gn-overline">Risk</div><div class="gn-mid" style="color:{risk_color}">'
            f'{esc(risk)}</div></div></div>')


def reasons(items: list[dict]) -> str:
    """İlk 3 neden; çubuk uzunluğu en güçlü nedene göre."""
    if not items:
        return ""
    top = max(r["katki"] for r in items) or 1.0
    rows = [f'<div class="gn-reason"><div class="gn-n">{i}</div><div><div class="gn-txt">'
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
    return (f'<div class="gn-banner" lang="tr" role="note">{icon("info", 20)}'
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
    return (f'<article class="gn-card" lang="tr"><div class="gn-card-head"><span class="gn-step">'
            f'{n}</span><div class="gn-card-icon">{icon(icon_name)}</div><h4>{esc(title)}</h4>'
            f'</div><ul>{lis}</ul></article>')


def grid(cards: list[str]) -> str:
    return f'<div class="gn-grid">{"".join(cards)}</div>'


def hero(title: str, text: str, stats: list[tuple[str, str]]) -> str:
    """Karşılama başlığı ve öne çıkan sonuçlar (değer, açıklama)."""
    stat_html = "".join(f'<div class="gn-stat"><b>{esc(v)}</b><span>{esc(label)}</span></div>'
                        for v, label in stats)
    # Rakam yoksa boş sütun bırakılmaz: başlık tam genişlik
    side = f'<div class="gn-stats">{stat_html}</div>' if stats else ""
    layout = "" if stats else ' style="grid-template-columns:1fr"'
    return (f'<section class="gn-hero" lang="tr" aria-label="Proje özeti"{layout}><div>'
            f'<div class="gn-overline">Proje hakkında</div><h2>{esc(title)}</h2><p>{esc(text)}</p>'
            f'</div>{side}</section>')


def cta(text_html: str) -> str:
    return f'<div class="gn-cta" lang="tr">{icon("activity", 20, PRIMARY_SOFT)}<div>{text_html}</div></div>'

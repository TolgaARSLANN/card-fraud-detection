"""Panelin tasarım sistemi (v4): "Gece Bülteni", editoryal bir finans gazetesi ön sayfası.

Kaynak: ui-ux-pro-max önerileri (Editorial Grid / Magazine, Exaggerated Minimalism, "Magazine
Style" yazı eşleşmesi: Libre Bodoni + Public Sans), bu panele uyarlanmış hâli; gerekçeler
docs/tasarim/arayuz-v4.md.

Fikir: sayfa gündüzün gazete kâğıdıdır; tek koyu alan "gece"dir (nöbet saati). Kutu kart yok:
ızgara, kalın ve ince siyah çizgiler, sütunlar, iri serif rakamlar.

Renk rolleri (her biri tek bir anlam taşır, anlam yalnızca renkle verilmez):
- PAPER: birincil metin (mürekkep), INK: zemin (kâğıt). Adlar geriye uyum için korunur.
- SIGNAL (gazete kırmızısı): yalnızca alarm ve dolandırıcılık; yanında simge + yazı.
- OK (koyu yeşil): yalnızca "onay".
- GOLD: gece kadranı ve numaralar (yalnızca büyük metinde ya da koyu zeminde).
Metin kontrastları WCAG AA üstüdür (kâğıt üzerinde mürekkep ~17:1, ikincil ~7:1).

Bileşenler HTML üretir; içlerine giren tüm metinler `esc` ile kaçışlanır. HTML tek satırda
üretilir (Markdown, 4 boşlukla başlayan satırları kod bloğu sayar).
"""

from __future__ import annotations

import math
from datetime import date
from html import escape

import plotly.graph_objects as go
import plotly.io as pio


def esc(s) -> str:
    """HTML kaçışı + '$' → '&#36;': Streamlit markdown, HTML içinde bile iki '$' arasını
    matematik formülü sayar (ör. "$912 ... $10")."""
    return escape(str(s)).replace("$", "&#36;")


# --- Tasarım belirteçleri ------------------------------------------------------------------------
INK = "#f4efe4"          # zemin: gazete kâğıdı
SURFACE = "#fbf8f1"      # açık yüzey (alıntı, not)
SURFACE_2 = "#ebe4d4"    # vurgulu yüzey
HAIR = "#d3cbbb"         # ince çizgi
RULE = "#16130f"         # kalın çizgi (mürekkep)
PAPER = "#16130f"        # birincil metin: mürekkep (kâğıt üzerinde ~17:1)
MUTED = "#57514a"        # ikincil metin (kâğıt üzerinde ~7:1)
SIGNAL = "#b42318"       # alarm / dolandırıcılık (kâğıt üzerinde ~6:1)
OK = "#16643a"           # onay (kâğıt üzerinde ~6,6:1)
GOLD = "#e0b44c"         # gece kadranı (koyu zeminde)
CALM = "#7d7468"         # grafiklerde normal işlem
NIGHT_BG = "#0f1016"     # tek koyu alan: gece
NIGHT_FILL = "rgba(22,19,15,0.07)"   # canlı kadranda gece dilimi
PRIMARY = PRIMARY_SOFT = LAMP = WARN = RULE           # eski adlar (geriye uyum)

SERIF = "'Libre Bodoni', 'Bodoni Moda', Didot, Georgia, serif"
SANS = "'Public Sans', system-ui, -apple-system, 'Segoe UI', sans-serif"
MONO = "'JetBrains Mono', ui-monospace, 'SFMono-Regular', monospace"
NIGHT = (22, 4)          # gece dilimi: 22:00–04:00
MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül",
          "Ekim", "Kasım", "Aralık"]

# Lucide çizgi simgeleri (24×24, 2 px çizgi); metnin yanında süs olarak `aria-hidden`.
ICONS = {
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "arrow": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
}


def icon(name: str, size: int = 20, color: str = "currentColor", stroke: float = 2) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke}" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
            f'{ICONS[name]}</svg>')


CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Libre+Bodoni:ital,wght@0,400;0,600;0,700;1,400&family=Public+Sans:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, button, input, select, textarea {{ font-family: {SANS}; }}
.stApp {{ background: {INK}; color: {PAPER}; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stAppDeployButton"], [data-testid="stMainMenu"], #MainMenu, footer {{ display: none; }}
.block-container {{ max-width: 1160px; padding-top: 1.25rem; padding-bottom: 4rem; }}
[data-testid="stHeaderActionElements"], .gn-section h3 a {{ display: none !important; }}
::selection {{ background: {SIGNAL}; color: #fff; }}

/* Hareket: yalnızca durum değişiminde; "hareketi azalt" tercihinde kapalı */
.stButton > button, .stFormSubmitButton > button, .stTabs [data-testid="stTab"] {{
  transition: background-color .18s ease, color .18s ease, box-shadow .18s ease; }}
@media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ transition: none !important; animation: none !important; }} }}

/* Odak: her zaman görünür (mürekkep halka) */
a:focus-visible, button:focus-visible, [role="tab"]:focus-visible, input:focus-visible, [tabindex]:focus-visible {{
  outline: 2px solid {RULE} !important; outline-offset: 3px; }}
a, .stMarkdown a {{ color: {PAPER} !important; text-decoration-thickness: 1px; text-underline-offset: 3px; }}
.stMarkdown a:hover {{ color: {SIGNAL} !important; }}

/* Sekmeler: gazete bölüm çubuğu */
.stTabs [role="tablist"] {{ gap: 0; border-top: 1px solid {RULE}; border-bottom: 1px solid {RULE}; flex-wrap: wrap; }}
.stTabs .react-aria-SelectionIndicator, .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none !important; }}
.stTabs [data-testid="stTab"] {{ padding: 0.7rem 1.1rem; min-height: 44px; background: transparent; border-radius: 0;
  border-right: 1px solid {HAIR}; }}
.stTabs [data-testid="stTab"] p {{ font-size: 0.78rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: {MUTED}; }}
.stTabs [data-testid="stTab"]:hover p {{ color: {PAPER}; }}
.stTabs [data-testid="stTab"][aria-selected="true"] {{ box-shadow: inset 0 -4px 0 {SIGNAL}; }}
.stTabs [data-testid="stTab"][aria-selected="true"] p {{ color: {PAPER}; }}
.stTabs [data-baseweb="tab-panel"], .stTabs [role="tabpanel"] {{ padding-top: 0.25rem; }}
@media (max-width: 560px) {{ .stTabs [data-testid="stTab"] {{ padding: 0.6rem 0.55rem; flex: 1 1 auto; }}
  .stTabs [data-testid="stTab"] p {{ font-size: 0.68rem; letter-spacing: 0.06em; }} }}

/* Düğmeler: köşeli, büyük harf; birincil eylem mürekkep üstüne kâğıt */
.stButton > button, .stFormSubmitButton > button {{ min-height: 44px; border-radius: 2px; font-weight: 700;
  font-size: 0.8rem; letter-spacing: 0.1em; text-transform: uppercase; border: 1.5px solid {RULE};
  background: transparent; color: {PAPER}; cursor: pointer; }}
.stButton > button p, .stFormSubmitButton > button p {{ font-weight: 700; font-size: 0.8rem; letter-spacing: 0.1em; }}
.stButton > button:hover, .stFormSubmitButton > button:hover {{ background: {SURFACE_2}; color: {PAPER}; border-color: {RULE}; }}
.stButton > button[kind="primary"], .stFormSubmitButton button {{ background: {RULE}; color: {INK}; border-color: {RULE}; }}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton button:hover {{ background: {SIGNAL}; border-color: {SIGNAL}; color: #fff; }}
.stButton > button[kind="primary"] p, .stFormSubmitButton button p {{ color: inherit; }}
.stButton > button:disabled {{ opacity: 0.4; cursor: not-allowed; }}

/* Form öğeleri, genişletici, tablo, grafik */
[data-testid="stWidgetLabel"] p {{ font-size: 0.72rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: {MUTED}; }}
[data-baseweb="select"] > div, [data-baseweb="input"], .stDateInput input, .stTimeInput input {{ border-radius: 2px !important; }}
[data-testid="stExpander"] details {{ border: none; border-top: 1px solid {RULE}; border-bottom: 1px solid {HAIR}; border-radius: 0; background: transparent; }}
[data-testid="stExpander"] summary p {{ font-weight: 700; font-size: 0.8rem; letter-spacing: 0.1em; text-transform: uppercase; }}
[data-testid="stCaptionContainer"] {{ color: {MUTED}; }}
[data-testid="stDataFrame"] {{ border-top: 2px solid {RULE}; }}
[data-testid="stAlert"] {{ border-radius: 2px; }}

/* Künye */
.gn-mast {{ margin-bottom: 0.9rem; }}
.gn-dateline {{ display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap;
  padding: 0.45rem 0; border-top: 1px solid {RULE}; border-bottom: 1px solid {HAIR};
  font-size: 0.72rem; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: {MUTED}; }}
.gn-dateline b {{ color: {PAPER}; font-weight: 700; }}
.gn-status {{ display: inline-flex; align-items: center; gap: 0.5rem; letter-spacing: 0.06em; }}
.gn-dot {{ width: 7px; height: 7px; border-radius: 50%; background: {OK}; flex: none; }}
.gn-title {{ font-family: {SERIF}; font-weight: 700; font-size: clamp(2.8rem, 9vw, 6.2rem); line-height: 0.95;
  letter-spacing: -0.035em; color: {PAPER}; text-align: center; margin: 0.9rem 0 0.35rem 0; }}
/* Streamlit'in kendi h1-h4 stilleri (yazı tipi, boyut, satır aralığı) editoryal başlıkları ezmesin */
.stMarkdown h1.gn-title {{ font-family: {SERIF} !important; font-size: clamp(2.8rem, 9vw, 6.2rem) !important;
  font-weight: 700 !important; line-height: 0.95 !important; letter-spacing: -0.035em !important; padding: 0 !important;
  margin: 1rem 0 0.4rem 0 !important; }}
/* Dar ekran: künye sadeleşir (orta öğe gizlenir, durum tek satır), sekmeler 2×2 */
@media (max-width: 560px) {{ .gn-dateline {{ font-size: 0.66rem; letter-spacing: 0.06em; row-gap: 0.25rem; }}
  .gn-dateline > span:nth-child(2) {{ display: none; }}
  .gn-status {{ width: 100%; }}
  .stTabs [role="tablist"] {{ display: grid !important; grid-template-columns: 1fr 1fr; }}
  .stTabs [data-testid="stTab"] {{ border-bottom: 1px solid {HAIR}; justify-content: center; }}
  .stTabs [data-testid="stTab"]:nth-child(even) {{ border-right: none; }} }}
.stMarkdown h2.gn-headline {{ font-family: {SERIF} !important; font-size: clamp(2.3rem, 6vw, 4.4rem) !important;
  font-weight: 700 !important; line-height: 0.98 !important; letter-spacing: -0.035em !important; padding: 0 !important;
  margin: 0.6rem 0 1.25rem 0 !important; }}
.stMarkdown p.gn-dek {{ font-weight: 400; }}
.stMarkdown .gn-section h3 {{ font-family: {SERIF} !important; font-size: clamp(1.6rem, 3.2vw, 2.3rem) !important;
  font-weight: 600 !important; line-height: 1.1 !important; letter-spacing: -0.02em !important; }}
.stMarkdown .gn-col h4 {{ font-family: {SERIF} !important; font-size: 1.35rem !important; font-weight: 600 !important;
  line-height: 1.2 !important; }}
.gn-tagline {{ text-align: center; font-family: {SERIF}; font-style: italic; font-size: clamp(1rem, 2vw, 1.2rem);
  color: {MUTED}; padding-bottom: 0.8rem; border-bottom: 4px double {RULE}; }}

/* Bölüm başlığı */
.gn-section {{ margin: 2.2rem 0 0.9rem 0; padding-top: 0.6rem; border-top: 2px solid {RULE}; }}
.gn-overline {{ font-size: 0.72rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: {MUTED}; }}
.gn-overline b {{ color: {SIGNAL}; }}
.gn-section h3 {{ font-family: {SERIF}; font-weight: 600; font-size: clamp(1.6rem, 3.2vw, 2.3rem); line-height: 1.1;
  letter-spacing: -0.02em; color: {PAPER}; margin: 0.35rem 0 0 0; padding: 0; }}
.gn-lede {{ font-family: {SERIF}; font-size: 1.08rem; line-height: 1.55; color: {MUTED}; max-width: 62ch; margin: 0.45rem 0 0 0; }}

/* Rakam şeridi (metrikler) */
.gn-kpis {{ display: grid; grid-template-columns: repeat(var(--n), minmax(0, 1fr)); border-top: 2px solid {RULE};
  border-bottom: 1px solid {RULE}; margin: 1rem 0 0.6rem 0; }}
@media (max-width: 980px) {{ .gn-kpis {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }} }}
@media (max-width: 560px) {{ .gn-kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
.gn-kpi {{ padding: 0.85rem 1rem 0.95rem 1rem; border-left: 1px solid {HAIR}; min-width: 0; }}
/* Satır başı ve alt satırlar Python'da işaretlenir (sütun sayısı orada bilinir); dar
   ekranda ızgara 3 ya da 2 sütuna düştüğünde satır başları CSS ile yeniden belirlenir */
.gn-kpi.row-start {{ border-left: none; padding-left: 0; }}
.gn-kpi.lower {{ border-top: 1px solid {HAIR}; }}
@media (max-width: 980px) {{ .gn-kpi, .gn-kpi.row-start {{ border-left: 1px solid {HAIR}; padding-left: 1rem; }}
  .gn-kpi:nth-child(3n+1) {{ border-left: none; padding-left: 0; }} }}
@media (max-width: 560px) {{ .gn-kpi:nth-child(3n+1) {{ border-left: 1px solid {HAIR}; padding-left: 1rem; }}
  .gn-kpi:nth-child(2n+1) {{ border-left: none; padding-left: 0; }} }}
.gn-kpi .gn-overline {{ display: flex; align-items: center; gap: 0.45rem; font-size: 0.7rem; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; text-transform: none; letter-spacing: 0.02em; font-weight: 600; }}
.gn-kpi .gn-val {{ font-family: {SERIF}; font-size: clamp(1.8rem, 3.2vw, 2.6rem); font-weight: 600; line-height: 1.05;
  color: {PAPER}; margin-top: 0.4rem; font-variant-numeric: lining-nums tabular-nums; letter-spacing: -0.02em; }}
.gn-tick {{ display: inline-block; width: 9px; height: 9px; background: {SIGNAL}; flex: none; }}
.gn-tick.calm {{ background: {CALM}; }}

/* Karar: müfettiş damgası */
.gn-verdict {{ display: grid; grid-template-columns: minmax(230px, 1.3fr) repeat(3, minmax(120px, 1fr));
  border-top: 2px solid {RULE}; border-bottom: 1px solid {RULE}; margin: 1.1rem 0; }}
.gn-verdict > div {{ padding: 1rem 1.1rem; border-left: 1px solid {HAIR}; }}
.gn-verdict > div:first-child {{ border-left: none; padding-left: 0; display: flex; flex-direction: column; justify-content: center; }}
.gn-stamp {{ align-self: flex-start; display: inline-flex; align-items: center; gap: 0.55rem; margin-top: 0.45rem;
  padding: 0.35rem 1rem 0.35rem 0.8rem; border: 3px solid var(--accent); border-radius: 3px; color: var(--accent);
  font-size: 1.7rem; font-weight: 800; letter-spacing: 0.14em; text-transform: uppercase; transform: rotate(-3deg);
  box-shadow: inset 0 0 0 1px var(--accent); }}
.gn-verdict .gn-mid {{ font-family: {SERIF}; font-size: 2rem; font-weight: 600; line-height: 1.05; color: {PAPER};
  margin-top: 0.45rem; font-variant-numeric: lining-nums tabular-nums; }}
.gn-meter {{ display: flex; gap: 3px; margin-top: 0.6rem; }}
.gn-meter span {{ width: 24px; height: 7px; background: {HAIR}; }}
.gn-meter span.on {{ background: {PAPER}; }}
.gn-meter.high span.on {{ background: {SIGNAL}; }}
@media (max-width: 760px) {{ .gn-verdict {{ grid-template-columns: 1fr 1fr; }}
  .gn-verdict > div {{ border-left: none; border-top: 1px solid {HAIR}; padding-left: 0; }}
  .gn-verdict > div:first-child {{ grid-column: 1 / -1; border-top: none; padding-bottom: 1.2rem; }} }}

/* Nedenler: dipnot dizisi */
.gn-reasons {{ margin: 0.4rem 0; border-top: 2px solid {RULE}; }}
.gn-reason {{ display: grid; grid-template-columns: 2.6rem minmax(0, 1fr) 4.5rem; align-items: baseline; gap: 0.9rem;
  padding: 0.9rem 0; border-bottom: 1px solid {HAIR}; }}
.gn-reason .gn-n {{ font-family: {SERIF}; font-style: italic; font-size: 1.6rem; color: {SIGNAL}; line-height: 1; }}
.gn-reason .gn-txt {{ font-family: {SERIF}; color: {PAPER}; font-size: 1.15rem; line-height: 1.4; }}
.gn-reason .gn-bar {{ height: 3px; background: {SIGNAL}; margin-top: 0.55rem; }}
.gn-reason .gn-w {{ font-family: {MONO}; font-size: 0.8rem; color: {MUTED}; text-align: right; }}

.gn-note-line {{ font-size: 0.82rem; color: {MUTED}; line-height: 1.6; margin-top: 0.55rem; }}

/* Okur notu (demo bandı) */
.gn-banner {{ display: flex; gap: 0.75rem; align-items: baseline; padding: 0.7rem 0; margin: 0 0 1rem 0;
  border-bottom: 1px solid {HAIR}; font-size: 0.9rem; line-height: 1.55; color: {PAPER}; }}
.gn-banner .gn-label {{ flex: none; font-size: 0.7rem; font-weight: 800; letter-spacing: 0.14em; text-transform: uppercase;
  color: #fff; background: {SIGNAL}; padding: 0.2rem 0.5rem; }}

/* Ön sayfa: manşet + gece fotoğrafı */
.gn-front {{ display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(0, 1fr); gap: 2rem; margin: 1.2rem 0 0 0; }}
@media (max-width: 860px) {{ .gn-front {{ grid-template-columns: 1fr; gap: 1.2rem; }} }}
.gn-kicker {{ font-size: 0.72rem; font-weight: 800; letter-spacing: 0.16em; text-transform: uppercase; color: {SIGNAL}; }}
.gn-headline {{ font-family: {SERIF}; font-weight: 700; font-size: clamp(2.3rem, 6vw, 4.4rem); line-height: 0.98;
  letter-spacing: -0.035em; color: {PAPER}; margin: 0.5rem 0 0.9rem 0; padding: 0; }}
.gn-headline em {{ font-style: italic; color: {SIGNAL}; }}
.gn-dek {{ font-family: {SERIF}; font-size: clamp(1.1rem, 2vw, 1.35rem); line-height: 1.45; color: {PAPER};
  margin: 0 0 1rem 0; max-width: 46ch; }}
.gn-body {{ font-size: 0.98rem; line-height: 1.7; color: {MUTED}; max-width: 62ch; margin: 0; }}
.gn-body.drop::first-letter {{ font-family: {SERIF}; float: left; font-size: 3.6rem; line-height: 0.8; font-weight: 700;
  color: {PAPER}; padding: 0.35rem 0.5rem 0 0; }}
.gn-night {{ margin: 0; background: {NIGHT_BG}; color: #e9e4d8; padding: 1.4rem 1.4rem 1.1rem 1.4rem; display: flex;
  flex-direction: column; align-items: center; justify-content: center; border-top: 4px solid {GOLD}; }}
.gn-night figcaption {{ font-family: {SERIF}; font-style: italic; font-size: 0.98rem; line-height: 1.45; color: #cfc8b8;
  text-align: center; margin-top: 0.6rem; max-width: 32ch; }}
.gn-ring {{ display: block; width: 100%; max-width: 250px; height: auto; }}

/* İri rakam sütunları */
.gn-figures {{ display: grid; grid-template-columns: repeat(var(--n), minmax(0, 1fr)); border-top: 2px solid {RULE};
  border-bottom: 1px solid {RULE}; margin: 1.6rem 0 0.4rem 0; }}
@media (max-width: 720px) {{ .gn-figures {{ grid-template-columns: 1fr; }} }}
.gn-figure {{ padding: 1rem 1.2rem 1.1rem 1.2rem; border-left: 1px solid {HAIR}; }}
.gn-figure:first-child {{ border-left: none; padding-left: 0; }}
@media (max-width: 720px) {{ .gn-figure {{ border-left: none; padding-left: 0; border-top: 1px solid {HAIR}; }} .gn-figure:first-child {{ border-top: none; }} }}
.gn-figure b {{ display: block; font-family: {SERIF}; font-size: clamp(2.4rem, 5vw, 3.6rem); font-weight: 600; line-height: 1;
  letter-spacing: -0.03em; color: {PAPER}; font-variant-numeric: lining-nums; }}
.gn-figure span {{ display: block; margin-top: 0.45rem; font-size: 0.85rem; line-height: 1.45; color: {MUTED}; }}

/* Sütunlar (nasıl çalışır / nasıl kullanılır): kutu yok, ince çizgilerle ayrılan sütunlar */
.gn-cols {{ display: grid; grid-template-columns: repeat(var(--n), minmax(0, 1fr)); gap: 0; margin: 0.4rem 0; }}
@media (max-width: 860px) {{ .gn-cols {{ grid-template-columns: 1fr; }} }}
.gn-col {{ padding: 0.3rem 1.3rem 0.8rem 1.3rem; border-left: 1px solid {HAIR}; }}
.gn-col:first-child {{ border-left: none; padding-left: 0; }}
@media (max-width: 860px) {{ .gn-col {{ border-left: none; padding: 1rem 0; border-top: 1px solid {HAIR}; }} .gn-col:first-child {{ border-top: none; }} }}
.gn-col .gn-num {{ font-family: {SERIF}; font-size: 3rem; font-weight: 400; line-height: 1; color: {SIGNAL}; }}
.gn-col h4 {{ font-family: {SERIF}; font-size: 1.35rem; font-weight: 600; letter-spacing: -0.01em; color: {PAPER}; margin: 0.35rem 0 0.45rem 0; padding: 0; }}
.gn-col p, .gn-col li {{ font-size: 0.94rem; line-height: 1.65; color: {MUTED}; margin: 0; }}
.gn-col ul {{ margin: 0; padding-left: 1.05rem; }}
.gn-col li + li {{ margin-top: 0.3rem; }}
.gn-col b {{ color: {PAPER}; font-weight: 700; }}

/* Çağrı ve dipnotlar */
.gn-cta {{ display: flex; gap: 0.7rem; align-items: center; padding: 0.9rem 1.1rem; margin: 1rem 0 0 0; background: {RULE};
  color: {INK}; font-size: 0.95rem; }}
.gn-cta b {{ color: #fff; }}
.gn-cta svg {{ color: {GOLD}; flex: none; }}
.gn-notes {{ display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 2rem; margin-top: 0.4rem; }}
@media (max-width: 860px) {{ .gn-notes {{ grid-template-columns: 1fr; gap: 0.8rem; }} }}
.gn-notes ol {{ margin: 0; padding-left: 1.2rem; }}
.gn-notes li, .gn-notes p {{ font-size: 0.86rem; line-height: 1.6; color: {MUTED}; margin: 0 0 0.35rem 0; }}
</style>
"""


# --- Plotly şablonu ------------------------------------------------------------------------------

pio.templates["gece"] = go.layout.Template(layout=go.Layout(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    separators=",.",                       # Türkçe sayı biçimi: ondalık virgül, binlik nokta
    font=dict(family=SANS, size=12, color=MUTED),
    xaxis=dict(gridcolor=HAIR, linecolor=RULE, zerolinecolor=HAIR, tickcolor=RULE),
    yaxis=dict(gridcolor=HAIR, linecolor=RULE, zerolinecolor=HAIR, tickcolor=RULE),
    polar=dict(bgcolor="rgba(0,0,0,0)"),
    hoverlabel=dict(bgcolor=RULE, bordercolor=RULE, font=dict(family=SANS, color=INK)),
    legend=dict(font=dict(color=MUTED)),
    margin=dict(l=10, r=10, t=10, b=10),
))


# --- Bileşenler ----------------------------------------------------------------------------------

def tr_date(d: date | None = None) -> str:
    d = d or date.today()
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def masthead(status_html: str, today: date | None = None) -> str:
    """Gazete künyesi: tarih satırı, dev ad, çift çizgi."""
    return (f'<header class="gn-mast" lang="tr"><div class="gn-dateline"><span><b>Sayı 01</b> · '
            f'{esc(tr_date(today))}</span><span>Kart dolandırıcılığı izleme bülteni</span>'
            f'<span class="gn-status" role="status">{status_html}</span></div>'
            f'<h1 class="gn-title">Gece Nöbeti</h1><div class="gn-tagline">Sessiz bir akışta '
            f'nadir olanı, işlem anında yakalamak</div></header>')


def status_line(base_url: str, cards: int, transactions: str, label: str = "API bağlı") -> str:
    return (f'<span class="gn-dot"></span><span><b>{esc(label)}</b> · {cards} kart · '
            f'{esc(transactions)} işlem geçmişi</span>')


def section(overline: str, title: str, lede: str = "", index: int | None = None) -> str:
    num = f"<b>§ {index:02d}</b> · " if index is not None else ""
    lede_html = f'<p class="gn-lede">{esc(lede)}</p>' if lede else ""
    return (f'<div class="gn-section" lang="tr"><div class="gn-overline">{num}{esc(overline)}</div>'
            f'<h3>{esc(title)}</h3>{lede_html}</div>')


def kpis(items: list[tuple[str, str, str | None]], cols: int | None = None) -> str:
    """items: (etiket, değer, işaret) — işaret: 'signal', 'calm' ya da None.
    cols: geniş ekranda sütun sayısı (varsayılan: hepsi tek satırda)."""
    n = cols or len(items)
    cells = []
    for i, (label, value, mark) in enumerate(items):
        tick = f'<span class="gn-tick {"calm" if mark == "calm" else ""}"></span>' if mark else ""
        extra = (" row-start" if i % n == 0 else "") + (" lower" if i >= n else "")
        cells.append(f'<div class="gn-kpi{extra}"><div class="gn-overline">{tick}{esc(label)}'
                     f'</div><div class="gn-val">{esc(value)}</div></div>')
    return f'<div class="gn-kpis" lang="tr" style="--n:{n}">{"".join(cells)}</div>'


RISK_STEPS = {"düşük": 1, "orta": 2, "yüksek": 3}


def risk_meter(risk: str) -> str:
    """Üç dilimli risk göstergesi: seviye dolu dilim sayısıyla ve yazıyla verilir."""
    n = RISK_STEPS.get(risk, 0)
    spans = "".join(f'<span class="{"on" if i < n else ""}"></span>' for i in range(3))
    high = " high" if n == 3 else ""
    return (f'<div class="gn-meter{high}" role="img" aria-label="Risk: {esc(risk)} '
            f'({n}/3)">{spans}</div>')


def verdict(alert: bool, probability: str, expected_loss: str, risk: str) -> str:
    """Karar: müfettiş damgası (renk + simge + yazı) ve iri rakamlar."""
    accent, mark = (SIGNAL, "alert") if alert else (OK, "check")
    word = "Alarm" if alert else "Onay"
    return (f'<div class="gn-verdict" lang="tr" style="--accent:{accent}">'
            f'<div><div class="gn-overline">Karar</div><div class="gn-stamp" role="img" '
            f'aria-label="Karar: {word}">{icon(mark, 24, accent, 2.5)}{word}</div></div>'
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
    rows = [f'<div class="gn-reason"><div class="gn-n">{i}.</div><div><div class="gn-txt">'
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
    """Demo modunda sayfanın üstünde kalıcı okur notu."""
    return (f'<div class="gn-banner" lang="tr" role="note"><span class="gn-label">Okur notu</span>'
            f'<div>{esc(DEMO_NOTICE)}</div></div>')


def footer() -> str:
    """Künye altı: veri kaynağı ve lisanslar (her iki modda)."""
    kaggle = "https://www.kaggle.com/datasets/kartik2112/fraud-detection"
    sparkov = "https://github.com/namebrandon/Sparkov_Data_Generation"
    return (f'<div class="gn-note-line" lang="tr" role="contentinfo" style="margin-top:2.6rem;'
            f'padding-top:0.8rem;border-top:4px double {RULE}">Veri: <a href="{kaggle}" '
            f'target="_blank" rel="noopener">Credit Card Transactions Fraud Detection</a> (Kaggle, '
            f'CC0: Public Domain) · <a href="{sparkov}" target="_blank" rel="noopener">'
            f'Sparkov Data Generation</a> simülatörüyle üretilmiş sentetik veri (MIT) · Kod: MIT, '
            f'© 2026 Tolga Arslan</div>')


# --- Nöbet saati (imza öğesi, koyu "gece" zeminde) ---------------------------------------------------

def _xy(hour: float, r: float, c: float = 100.0) -> tuple[float, float]:
    """Saat → SVG koordinatı (00 tepede, saat yönünde)."""
    a = math.radians(hour / 24 * 360 - 90)
    return c + r * math.cos(a), c + r * math.sin(a)


def night_ring(share: float | None, label: str = "gece") -> str:
    """24 saatlik kadran (koyu zemin için): 24 çentik, gece dilimi (22:00–04:00) altın yay;
    ortada dolandırıcılığın gece payı. `share` None ise rakam çizilmez (uydurulmaz)."""
    start, end = NIGHT
    span = (end - start) % 24
    x1, y1 = _xy(start, 76)
    x2, y2 = _xy(end, 76)
    large = 1 if span > 12 else 0
    ticks = []
    for h in range(24):
        major = h % 6 == 0
        xa, ya = _xy(h, 94)
        xb, yb = _xy(h, 87 if major else 90)
        ticks.append(f'<line x1="{xa:.1f}" y1="{ya:.1f}" x2="{xb:.1f}" y2="{yb:.1f}" stroke="'
                     f'{"#cfc8b8" if major else "#5a5a66"}" stroke-width="{1.8 if major else 1}"/>')
    labels = "".join(
        f'<text x="{_xy(h, 62)[0]:.1f}" y="{_xy(h, 62)[1] + 4:.1f}" text-anchor="middle" '
        f'font-family="JetBrains Mono, monospace" font-size="9.5" fill="#9d978a">{h:02d}</text>'
        for h in (0, 6, 12, 18))
    center = (f'<text x="100" y="104" text-anchor="middle" font-family="Libre Bodoni, Georgia, '
              f'serif" font-size="40" font-weight="700" fill="#f4efe4">%{round(100 * share)}</text>'
              f'<text x="100" y="124" text-anchor="middle" font-family="Public Sans, sans-serif" '
              f'font-size="9" letter-spacing="2" fill="{GOLD}">{esc(label.upper())}</text>'
              ) if share is not None else ""
    desc = (f"24 saatlik kadran; 22:00-04:00 gece dilimi vurgulu. Dolandırıcılığın yüzde "
            f"{round(100 * share)}'i bu saatlerde." if share is not None
            else "24 saatlik kadran; 22:00-04:00 gece dilimi vurgulu.")
    return (f'<svg class="gn-ring" viewBox="0 0 200 200" role="img" aria-label="{esc(desc)}">'
            f'<circle cx="100" cy="100" r="76" fill="none" stroke="#24252e" stroke-width="12"/>'
            f'<path d="M {x1:.1f} {y1:.1f} A 76 76 0 {large} 1 {x2:.1f} {y2:.1f}" fill="none" '
            f'stroke="{GOLD}" stroke-width="12"/>{"".join(ticks)}{labels}{center}</svg>')


# --- Ön sayfa (karşılama) bileşenleri --------------------------------------------------------------

def rich(text: str) -> str:
    """Kaçışlı satır içi metin; **kalın** desteklenir."""
    parts = esc(text).split("**")
    return "".join(f"<b>{s}</b>" if i % 2 else s for i, s in enumerate(parts))


def front(kicker: str, headline_html: str, dek: str, body: str, night_share: float | None) -> str:
    """Manşet + gece fotoğrafı. `headline_html` çağıranca kaçışlanmış olmalıdır."""
    night = ""
    if night_share is not None:
        night = (f'<figure class="gn-night">{night_ring(night_share)}<figcaption>Test dönemindeki '
                 f'dolandırıcılığın gece 22:00–04:00 arasına düşen payı</figcaption></figure>')
    layout = "" if night else ' style="grid-template-columns:1fr"'
    return (f'<section class="gn-front" lang="tr" aria-label="Proje özeti"{layout}><div>'
            f'<div class="gn-kicker">{esc(kicker)}</div><h2 class="gn-headline">{headline_html}</h2>'
            f'<p class="gn-dek">{rich(dek)}</p><p class="gn-body drop">{rich(body)}</p></div>'
            f'{night}</section>')


def figures(stats: list[tuple[str, str]]) -> str:
    if not stats:
        return ""
    cells = "".join(f'<div class="gn-figure"><b>{esc(v)}</b><span>{esc(label)}</span></div>'
                    for v, label in stats)
    return f'<div class="gn-figures" lang="tr" style="--n:{len(stats)}">{cells}</div>'


def columns(items: list[tuple[str, str, str]]) -> str:
    """Numaralı sütunlar: (numara, başlık, gövde HTML'i; çağıranca kaçışlanmış)."""
    cols = "".join(f'<article class="gn-col"><div class="gn-num">{esc(n)}</div><h4>{esc(t)}</h4>'
                   f'{body}</article>' for n, t, body in items)
    return f'<div class="gn-cols" lang="tr" style="--n:{len(items)}">{cols}</div>'


def cta(text_html: str) -> str:
    return f'<div class="gn-cta" lang="tr">{icon("arrow", 18)}<div>{text_html}</div></div>'


def notes(items_html: list[str], aside_html: str) -> str:
    lis = "".join(f"<li>{x}</li>" for x in items_html)
    return f'<div class="gn-notes" lang="tr"><ol>{lis}</ol><div>{aside_html}</div></div>'

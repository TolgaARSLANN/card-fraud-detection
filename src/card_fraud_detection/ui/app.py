"""Gece Nöbeti — kart dolandırıcılığı izleme paneli (Streamlit).

Çalıştırma (önce API: `make api`):
    streamlit run src/card_fraud_detection/ui/app.py      # make ui

Tasarım dili: docs/tasarim/gece-nobeti.md (tasarım sistemi: ui/theme.py).
Sekmeler: Canlı akış (test dönemi işlemleri sırayla API'ye gönderilir, alarm kuyruğu oluşur),
İşlem incele (kararın nedenleri), Eşik ve maliyet (inceleme ücreti değişirse ne olur).
"""

from __future__ import annotations

from datetime import datetime, time
from uuid import uuid4

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from card_fraud_detection.config import REVIEW_COST, TARGET, TIME_COL, demo_mode
from card_fraud_detection.data.clean import OUT_PATH as TRANSACTIONS_PATH
from card_fraud_detection.formatting import tr_num
from card_fraud_detection.ui import theme
from card_fraud_detection.ui.client import ApiClient, ApiError
from card_fraud_detection.ui.logic import (
    alert_queue,
    mask_card,
    money,
    resync_point,
    review_cost_curve,
    review_cost_point,
    stream_kpis,
)
from card_fraud_detection.ui.prepare import PANEL_SCORES

INPUT = [TIME_COL, "cc_num", "amt", "category", "merchant"]

st.set_page_config(page_title="Gece Nöbeti · Kart Dolandırıcılığı", page_icon="◐",
                   layout="wide")
st.markdown(theme.CSS, unsafe_allow_html=True)
# Sayfa dilini Türkçe işaretle: CSS büyük harf dönüşümü "i"yi "İ" yapsın ("IŞLEM" değil
# "İŞLEM"). Streamlit'in kendi öğeleri (sekme, etiket, düğme) için gerekli; bileşenlerimiz
# ayrıca lang="tr" taşır.
try:   # Streamlit ≥ 1.4x: betik doğrudan ana sayfada çalışır, yer kaplamaz
    st.html("<script>document.documentElement.lang = 'tr';</script>",
            unsafe_allow_javascript=True)
except TypeError:   # eski sürüm: kullanımdan kalkan bileşen yolu
    components.html("<script>window.parent.document.documentElement.lang = 'tr';</script>",
                    height=0)


DEMO = demo_mode()
if DEMO:   # herkese açık demo: hata olursa yığın izi ve dosya yolları ziyaretçiye gösterilmez
    st.set_option("client.showErrorDetails", "none")


@st.cache_resource
def get_client() -> ApiClient:
    return ApiClient()


@st.cache_resource(show_spinner="Model ve kart geçmişi yükleniyor…")
def demo_shared():
    """Demo: model, açıklayıcı ve yüklenmiş geçmiş tüm oturumlar için TEK kopya; oturumlar
    yalnızca kendi eklediklerini katmanlarında tutar (ui/demo_backend.py)."""
    from card_fraud_detection.serving.service import ScoringService
    from card_fraud_detection.ui.demo_backend import SessionRegistry, SharedBases
    service = ScoringService.load()
    service.num_threads = 1        # eşzamanlı oturumlar 2 çekirdekte birbirini boğmasın
    return service, SessionRegistry(SharedBases(service))


@st.cache_data(show_spinner="Test dönemi işlemleri yükleniyor…")
def load_stream() -> pd.DataFrame:
    df = pd.read_parquet(TRANSACTIONS_PATH, columns=["tx_id", "split", TARGET, *INPUT],
                         filters=[("split", "==", "test")])
    df["category"] = df["category"].astype(str)
    df["merchant"] = df["merchant"].astype(str)
    return df.sort_values("tx_id").reset_index(drop=True)


@st.cache_data(show_spinner="Skorlar yükleniyor…")
def load_panel_scores() -> pd.DataFrame | None:
    return pd.read_parquet(PANEL_SCORES) if PANEL_SCORES.exists() else None


def pct(x: float, decimals: int = 1) -> str:
    return f"%{tr_num(100 * x, decimals)}"


def html(s: str) -> None:
    st.markdown(s, unsafe_allow_html=True)


def watch_dial(results: pd.DataFrame) -> go.Figure:
    """Tuvaldeki kadranın canlı yankısı: açı saat, yarıçap akıştaki sıra; alarm = sinyal."""
    t = pd.to_datetime(results[TIME_COL])
    theta = (t.dt.hour * 60 + t.dt.minute) / 1440 * 360
    r = np.arange(1, len(results) + 1)
    alert = results["karar"].eq("alarm").to_numpy()
    hover = [f"{ts:%d.%m %H:%M} · {money(a)} · {c}" for ts, a, c in
             zip(t, results["amt"], results["category"], strict=True)]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        theta=theta[~alert], r=r[~alert], mode="markers", name="onay",
        marker=dict(size=4, color=theme.CALM, opacity=0.45),
        text=np.array(hover)[~alert], hovertemplate="%{text}<extra>onay</extra>"))
    fig.add_trace(go.Scatterpolar(
        theta=theta[alert], r=r[alert], mode="markers", name="alarm",
        marker=dict(size=9, color=theme.SIGNAL, line=dict(color=theme.INK, width=2)),
        text=np.array(hover)[alert], hovertemplate="%{text}<extra>alarm</extra>"))
    fig.update_layout(
        template="gece", height=300, showlegend=False, margin=dict(l=28, r=28, t=28, b=16),
        polar=dict(
            angularaxis=dict(rotation=90, direction="clockwise", tickmode="array",
                             tickvals=[0, 90, 180, 270], ticktext=["00", "06", "12", "18"],
                             gridcolor=theme.HAIR, linecolor=theme.HAIR,
                             tickfont=dict(color=theme.PAPER)),
            radialaxis=dict(showticklabels=False, gridcolor=theme.HAIR, linecolor=theme.HAIR,
                            ticks="", range=[0, max(len(results), 1) * 1.05]),
        ))
    return fig


def show_result(res: dict, amt: float) -> None:
    alert = res["karar"] == "alarm"
    html(theme.verdict(alert, pct(res["olasilik"], 2), money(res["beklenen_kayip"]),
                       res["risk_seviyesi"]))
    if alert and res["nedenler"]:
        html(theme.section("Neden", "Skoru en çok artıran üç etken"))
        html(theme.reasons(res["nedenler"]))
    extra = "" if alert else " Onaylanan işlemler için neden gösterilmez."
    html(theme.note(f"Karar beklenen kayba dayanır: olasılık × tutar ({money(amt)}) ≥ inceleme "
                    f"ücreti ({money(REVIEW_COST)}) ise alarm. Risk seviyesi yalnızca özet "
                    f"etikettir.{extra}"))


# --- Başlık ve bağlantı ---

if DEMO:
    from card_fraud_detection.ui.demo_backend import PRESETS, DemoBackend, DemoBusy
    service, registry = demo_shared()
    sid = st.session_state.setdefault("demo_sid", uuid4().hex)
    try:
        state, fresh = registry.session(sid)
    except DemoBusy as exc:
        html(theme.masthead("demo dolu"))
        html(theme.demo_notice())
        st.warning(str(exc))
        st.stop()
    client = DemoBackend(service, registry, state)
    if fresh and st.session_state.get("demo_seen"):
        st.info("Oturumunuz uzun süre işlem yapılmadığı için sıfırlandı; akış baştan başlıyor.")
    st.session_state.demo_seen = True
    state.api_n = None             # demo: ortak API durumu yok, kayma denetimi gerekmez
    api_health, in_sync = client.health(), True
else:
    client = get_client()
    try:
        api_health = client.health()
    except ApiError as exc:
        html(theme.masthead("bağlantı yok"))
        st.error(f"{exc}\n\nAPI'yi başlatmak için ayrı bir terminalde: `make api`")
        st.stop()
    state = st.session_state
    if "cursor" not in state:
        # Yeni oturum: akış imleci baştan başlar; API'nin geçmişi de başa dönmeli, yoksa önceki
        # oturumda skorlanan işlemler geçmişe ikinci kez eklenir. (Panel tek kullanıcılı bir
        # demodur; aynı anda iki sekme birbirinin geçmişini sıfırlar.)
        state.api_n = client.reset()["islem"]
        state.cursor, state.results = 0, []
    # API'de olması gereken işlem sayısı (son sıfırlama + bu oturumda kaydedilenler). Uymuyorsa
    # API yeniden başlamış ya da başka bir sekme geçmişi değiştirmiştir; o hâlde gönderilen
    # işlemlerin özellikleri eksik geçmişle hesaplanırdı. Akış durdurulur, eşitleme önerilir.
    in_sync = api_health["islem"] == state.api_n
mast = st.empty()          # sayfa sonunda doldurulur: bu çalıştırmadaki işlemler dahil
if DEMO:
    html(theme.demo_notice())

tab_stream, tab_inspect, tab_cost = st.tabs(["Canlı akış", "İşlem incele", "Eşik ve maliyet"])

# --- 1. Canlı akış ---

with tab_stream:
    stream = load_stream()
    html(theme.section("Test dönemi · 21 Haziran – 31 Aralık 2020", "Akış",
                       ("İşlemler sırayla skorlanıp yalnızca sizin oturumunuzdaki kart "
                        "geçmişine eklenir" if DEMO else
                        "İşlemler sırayla API'ye gönderilir; her biri skorlanıp kartın "
                        "geçmişine eklenir") + ". Dolandırıcılık çoğunlukla gece gelir."))
    if DEMO:
        with st.expander("Başlangıç anı"):
            st.caption("Atlanan işlemler skorlanmaz ama kartların geçmişine eklenir; özellikler "
                       "tutarlı kalır. Değişiklik yalnızca sizin oturumunuzu etkiler.")
            s1, s2 = st.columns([2, 1], vertical_alignment="bottom")
            preset = s1.selectbox("Başlangıç", list(PRESETS),
                                  index=list(PRESETS).index(state.start))
            if s2.button("Bu andan başlat", width="stretch"):
                client.start(preset)
                until = PRESETS[preset]
                state.cursor = 0 if until is None else int(
                    stream[TIME_COL].searchsorted(pd.Timestamp(until)))
                st.rerun()
    else:
        with st.expander("Başlangıç anı"):
            st.caption("Atlanan işlemler skorlanmaz ama kartların geçmişine eklenir; özellikler "
                       "tutarlı kalır.")
            s1, s2, s3 = st.columns([1, 1, 1])
            start_day = s1.date_input("Tarih", value=datetime(2020, 6, 21), key="start_day",
                                      min_value=datetime(2020, 6, 21),
                                      max_value=datetime(2020, 12, 31))
            start_hour = s2.time_input("Saat", value=time(22, 0), key="start_hour")
            s3.write("")
            if s3.button("Bu andan başlat", width="stretch"):
                start = datetime.combine(start_day, start_hour)
                with st.spinner("Kart geçmişi o ana kadar yeniden kuruluyor…"):
                    state.api_n = client.reset(until=start)["islem"]
                state.cursor = int(stream[TIME_COL].searchsorted(pd.Timestamp(start)))
                state.results = []
                st.rerun()

    if not in_sync:
        st.warning(
            f"API'deki kart geçmişi bu oturumla uyuşmuyor ({tr_num(api_health['islem'])} işlem "
            f"var, {tr_num(state.api_n)} bekleniyordu). API yeniden başlamış ya da başka bir "
            "sekme geçmişi değiştirmiş olabilir. Bu hâlde skorlanan işlemlerin özellikleri "
            "eksik geçmişle hesaplanır; akış, geçmiş eşitlenene kadar durduruldu.")
        if st.button("Geçmişi kaldığım yere kadar yeniden kur"):
            until, cursor = resync_point(stream[TIME_COL], state.cursor)
            with st.spinner("Kart geçmişi yeniden kuruluyor…"):
                h = client.reset(until=until.to_pydatetime()) if until is not None \
                    else client.reset()
            # İmleç geri alındıysa o işlemler yeniden skorlanacak: sonuçlardan çıkar
            state.results = state.results[:max(0, len(state.results) - (state.cursor - cursor))]
            state.cursor, state.api_n = cursor, h["islem"]
            st.rerun()

    c1, c2, c3 = st.columns([2, 1, 1], vertical_alignment="bottom")
    batch = c1.select_slider("Her adımda işlem", [10, 25, 50, 100, 200], value=50)
    # Demo: oturum başına akış sınırı (bellek ve işlem gücü ziyaretçi sayısıyla büyümesin)
    remaining = client.remaining if DEMO else len(stream)
    if c2.button("Sonraki →", type="primary", width="stretch",
                 disabled=not in_sync or remaining == 0):
        chunk = stream.iloc[state.cursor:state.cursor + min(batch, remaining)]
        bar = st.progress(0.0, text="Skorlanıyor…")
        try:
            for i, (_, row) in enumerate(chunk.iterrows(), start=1):
                tx = row[INPUT].to_dict()
                res = client.score({**tx, TIME_COL: tx[TIME_COL].to_pydatetime()})
                state.results.append({**tx, TARGET: int(row[TARGET]), **res})
                state.cursor += 1          # hata olursa aynı işlem ikinci kez gönderilmesin
                if not DEMO:
                    state.api_n += 1
                bar.progress(i / len(chunk), text=f"Skorlanıyor… {i}/{len(chunk)}")
        except ApiError as exc:
            st.error(str(exc))
        else:
            if DEMO and client.remaining == 0:
                st.rerun()                 # sınıra ulaşıldı: düğme hemen kilitli görünsün
        bar.empty()
    if c3.button("↺ Baştan", width="stretch"):
        state.api_n = client.reset()["islem"]      # demo: yalnızca bu oturumun katmanı
        state.cursor, state.results = 0, []
        st.rerun()
    if DEMO:
        remaining = client.remaining               # bu çalıştırmada skorlananlar düşülmüş
        left_note = (" · sınıra ulaşıldı; yeni bir sekmede yeni oturum açabilirsiniz"
                     if remaining == 0 else "")
        html(theme.note(f"Bu oturumda skorlanabilecek işlem: {tr_num(remaining)} / "
                        f"{tr_num(client.stream_limit)}{left_note}"))

    results = pd.DataFrame(state.results)
    k = stream_kpis(results)
    # Üstte: solda metrikler, sağda kadran. Altta: alarm kuyruğu tam genişlikte (tablo sıkışmasın)
    left, right = st.columns([5, 3], gap="large")
    with left:
        html(theme.kpis([
            ("İşlem", tr_num(k["işlem"]), None),
            ("Alarm", tr_num(k["alarm"]), "signal"),
            ("Yakalanan", tr_num(k["yakalanan"]), "signal"),
            ("Kaçan", tr_num(k["kaçan"]), None),
            ("Yanlış alarm", tr_num(k["yanlış alarm"]), "calm"),
            ("Kaçan tutar", money(k["kaçan tutar"]), None),
        ], cols=3))
        if results.empty:
            html(theme.note("Henüz işlem gönderilmedi. Gece saatlerini görmek için “Başlangıç "
                            "anı” bölümünden 22:00'yi seçebilirsiniz."))
        else:
            last = pd.Timestamp(results[TIME_COL].iloc[-1])
            html(theme.note(f"Akışta gelinen an: {last:%d.%m.%Y %H:%M} · "
                            f"{tr_num(state.cursor)} / {tr_num(len(stream))} işlem"))
    with right:
        if not results.empty:
            st.plotly_chart(watch_dial(results), width="stretch",
                            config={"displayModeBar": False})
            html(theme.note("Açı: saat · içten dışa: akıştaki sıra · kızıl: alarm"))

    if not results.empty:
        html(theme.section("Kuyruk", "Alarmlar"))
        queue = alert_queue(results)
        if queue.empty:
            html(theme.note("Henüz alarm yok."))
        else:
            st.dataframe(queue, width="stretch", hide_index=True, column_config={
                "işlem no": st.column_config.NumberColumn("no", format="%d", width="small"),
                "zaman": st.column_config.TextColumn("zaman", width="small"),
                "kart": st.column_config.TextColumn("kart", width="small"),
                "olasılık": st.column_config.ProgressColumn(
                    "olasılık", format="percent", min_value=0.0, max_value=1.0, width="small"),
                "tutar ($)": st.column_config.NumberColumn("tutar", format="$%.2f"),
                "beklenen kayıp ($)": st.column_config.NumberColumn("beklenen kayıp",
                                                                    format="$%.0f")})
            html(theme.note("Gerçek etiket yalnızca bu simülasyonda bilinir; gerçekte "
                            "etiketler (müşteri itirazı, inceleme sonucu) günler sonra gelir."))

# --- 2. İşlem incele ---

with tab_inspect:
    results = pd.DataFrame(state.results)
    alerts = results[results["karar"].eq("alarm")] if not results.empty else results
    html(theme.section("İnceleme", "Neden alarm?",
                       "Akıştaki bir alarmı ya da elle girilen bir işlemi seçin; karar ve onu "
                       "en çok etkileyen üç etken gösterilir."))
    mode = st.radio("Kaynak", ["Akıştaki bir alarm", "Elle işlem gir"], horizontal=True,
                    label_visibility="collapsed")
    if mode == "Akıştaki bir alarm":
        if alerts.empty:
            html(theme.note("Önce “Canlı akış” sekmesinde işlem gönderin."))
        else:
            labels = {f"#{int(r.islem_no)} · {pd.Timestamp(r[TIME_COL]):%d.%m %H:%M} · "
                      f"{money(r.amt)} · {r.category}": i for i, r in alerts.iloc[::-1].iterrows()}
            choice = st.selectbox("Alarm", list(labels))
            row = alerts.loc[labels[choice]]
            show_result(row.to_dict(), row["amt"])
            html(theme.note(f"Gerçek etiket: "
                            f"{'dolandırıcılık' if row[TARGET] == 1 else 'normal'}"))
    else:
        with st.form("manuel", border=False):
            c1, c2, c3 = st.columns(3)
            if DEMO:
                # Serbest numara yok: yalnızca veri setindeki sentetik kartlar, maskeli etiketle
                cards = client.state.store.cards()
                labels = {f"Kart {i} · {mask_card(c)}": c for i, c in enumerate(cards, start=1)}
                cc = labels[c1.selectbox("Kart (sentetik)", list(labels))]
            else:
                cc = c1.number_input("Kart numarası", value=4613314721966, step=1, format="%d")
            amt = c2.number_input("Tutar ($)", min_value=0.01, value=912.40, step=10.0)
            category = c3.selectbox("Kategori", sorted(load_stream()["category"].unique()),
                                    index=None, placeholder="Seçin")
            c4, c5, c6 = st.columns(3)
            day = c4.date_input("Tarih", value=datetime(2020, 6, 21))
            hour = c5.time_input("Saat", value=time(23, 15))
            if DEMO:
                merchant = c6.selectbox("Satıcı", sorted(load_stream()["merchant"].unique()))
            else:
                merchant = c6.text_input("Satıcı", value="Kutch, Hermiston and Farrell")
            submitted = st.form_submit_button("Skorla · geçmişe kaydetmeden", type="primary")
        if submitted:
            if category is None:
                st.warning("Kategori seçin.")
            else:
                tx = {TIME_COL: datetime.combine(day, hour), "cc_num": int(cc), "amt": amt,
                      "category": category, "merchant": merchant}
                try:
                    show_result(client.score(tx, save=False), amt)
                except ApiError as exc:
                    st.error(str(exc))

# --- 3. Eşik ve maliyet ---

with tab_cost:
    scores = load_panel_scores()
    html(theme.section("Karar kuralı", "Eşik ve maliyet",
                       "Olasılık × tutar ≥ inceleme ücreti ise alarm. Ücret değişirse alarm "
                       "sayısı, yakalanan tutar ve maliyet nasıl değişir? Veri: test dönemi, "
                       "son değerlendirmeyle aynı model."))
    if scores is None:
        st.warning("Skor dosyası yok. Oluşturmak için: `make panel-data`")
    else:
        cost = st.slider("Alarm başına inceleme ücreti ($)", 1, 100, int(REVIEW_COST), step=1)
        y, p, amt = scores[TARGET].to_numpy(), scores["p"].to_numpy(), scores["amt"].to_numpy()
        point = review_cost_point(p, amt, y, cost)
        html(theme.kpis([
            ("Alarm · 6 ay", tr_num(point["alarm"]), "signal"),
            ("Precision", pct(point["precision"]), None),
            ("Recall", pct(point["recall"]), None),
            ("Yakalanan tutar", pct(point["tutar recall"]), None),
            ("Toplam maliyet", money(point["maliyet"]), None),
        ]))
        curve = review_cost_curve(p, amt, y, np.arange(1, 101))
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=curve["alarm"], y=curve["tutar recall"], mode="lines", name="ücret $1–100",
            line=dict(color=theme.CALM, width=2), customdata=curve["inceleme ücreti"],
            hovertemplate="ücret $%{customdata}<br>alarm %{x:,}<br>yakalanan tutar "
                          "%{y:.1%}<extra></extra>"))
        fig.add_trace(go.Scatter(
            x=[point["alarm"]], y=[point["tutar recall"]], mode="markers+text",
            name=f"seçilen ${cost}", text=[f"  ${cost}"], textposition="middle right",
            textfont=dict(color=theme.PAPER, family=theme.MONO),
            marker=dict(color=theme.SIGNAL, size=12, line=dict(color=theme.INK, width=2)),
            hoverinfo="skip"))
        # Dikey eksen başlığı döndürülünce kesiliyordu; eksenin anlamı grafiğin üstünde yazar
        fig.update_layout(template="gece", height=380, showlegend=False,
                          margin=dict(l=10, r=16, t=10, b=48),
                          xaxis_title="Alarm sayısı (6 ay)",
                          yaxis_tickformat=".1%")       # dar aralıkta tam sayı etiketleri çakışır
        html(theme.note("↑ Yakalanan dolandırıcılık tutarı (dolandırıcılık tutarının yüzdesi)"))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        html(theme.note(f"Hiç alarm vermemenin maliyeti: {money(amt[y == 1].sum())}. Ücret "
                        "arttıkça kural yalnızca beklenen kaybı yüksek işlemlere alarm verir: "
                        "alarm sayısı düşer, küçük tutarlı dolandırıcılıklar kaçmaya başlar."))

# --- Başlık (en sonda: bu çalıştırmadaki işlemler dahil) ---

try:
    h = client.health()
    mast.markdown(theme.masthead(theme.status_line(
        "oturumunuza özel geçmiş" if DEMO else client.base_url, h["kart"], tr_num(h["islem"]),
        label="Demo · yerel skorlama" if DEMO else "API bağlı")), unsafe_allow_html=True)
except ApiError as exc:
    mast.error("Sunucu hatası" if DEMO else str(exc))

html(theme.footer())

"""Kart dolandırıcılığı izleme paneli (Streamlit).

Çalıştırma (önce API: `make api`):
    streamlit run src/card_fraud_detection/ui/app.py      # make ui

Sekmeler: Canlı akış (test dönemi işlemleri sırayla API'ye gönderilir, alarm kuyruğu oluşur),
İşlem incele (kararın nedenleri), Eşik ve maliyet (inceleme ücreti değişirse ne olur).
"""

from __future__ import annotations

from datetime import datetime, time

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from card_fraud_detection.config import REVIEW_COST, TARGET, TIME_COL
from card_fraud_detection.data.clean import OUT_PATH as TRANSACTIONS_PATH
from card_fraud_detection.models.explain import tr_num
from card_fraud_detection.ui.client import ApiClient, ApiError
from card_fraud_detection.ui.logic import (
    alert_queue,
    money,
    money_md,
    review_cost_curve,
    review_cost_point,
    stream_kpis,
)
from card_fraud_detection.ui.prepare import PANEL_SCORES

FRAUD, NORMAL, MUTED = "#eb6834", "#2a78d6", "#898781"
INPUT = [TIME_COL, "cc_num", "amt", "category", "merchant"]

st.set_page_config(page_title="Kart Dolandırıcılığı Paneli", page_icon="💳", layout="wide")


@st.cache_resource
def get_client() -> ApiClient:
    return ApiClient()


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


def reason_chart(reasons: list[dict]) -> go.Figure:
    r = list(reversed(reasons))
    fig = go.Figure(go.Bar(x=[x["katki"] for x in r], y=[x["aciklama"] for x in r],
                           orientation="h", marker_color=FRAUD,
                           hovertemplate="%{y}<br>katkı %{x:.2f}<extra></extra>"))
    fig.update_layout(height=60 + 45 * len(r), margin=dict(l=10, r=10, t=10, b=30),
                      xaxis_title="Skora katkı (log-oran)", showlegend=False)
    return fig


def show_result(res: dict, amt: float) -> None:
    alert = res["karar"] == "alarm"
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Karar", "🚨 ALARM" if alert else "✅ Onay")
    c2.metric("Olasılık", pct(res["olasilik"], 2))
    c3.metric("Beklenen kayıp", money(res["beklenen_kayip"]))
    c4.metric("Risk seviyesi", res["risk_seviyesi"])
    st.caption(f"Karar beklenen kayba dayanır: olasılık × tutar ({money_md(amt)}) ≥ "
               f"inceleme ücreti ({money_md(REVIEW_COST)}) ise alarm. Risk seviyesi yalnızca "
               "özet etikettir.")
    if alert and res["nedenler"]:
        st.markdown("**Neden alarm verildi?** (skoru en çok artıran 3 etken)")
        st.plotly_chart(reason_chart(res["nedenler"]), use_container_width=True)
    elif not alert:
        st.info("Onaylanan işlemler için neden gösterilmez.")


# --- Başlık ve bağlantı ---

st.title("💳 Kart Dolandırıcılığı İzleme Paneli")
client = get_client()
try:
    client.health()
except ApiError as exc:
    st.error(f"{exc}\n\nAPI'yi başlatmak için ayrı bir terminalde: `make api`")
    st.stop()
# Sayfanın sonunda doldurulur: bu çalıştırmada gönderilen işlemler de sayıya girsin
status_line = st.empty()

tab_stream, tab_inspect, tab_cost = st.tabs(["Canlı akış", "İşlem incele", "Eşik ve maliyet"])

# --- 1. Canlı akış ---

with tab_stream:
    stream = load_stream()
    state = st.session_state
    if "cursor" not in state:
        # Yeni oturum: akış imleci baştan başlar; API'nin geçmişi de başa dönmeli, yoksa önceki
        # oturumda skorlanan işlemler geçmişe ikinci kez eklenir. (Panel tek kullanıcılı bir
        # demodur; aynı anda iki sekme birbirinin geçmişini sıfırlar.)
        client.reset()
        state.cursor, state.results = 0, []

    st.markdown("Test dönemi (21 Haziran – 31 Aralık 2020) işlemleri sırayla API'ye gönderilir; "
                "her işlem skorlanıp kartın geçmişine eklenir.")
    with st.expander("Başlangıç anı"):
        st.caption("Dolandırıcılık çoğunlukla gece; akışı istediğiniz andan başlatabilirsiniz. "
                   "Atlanan işlemler skorlanmaz ama kartların geçmişine eklenir, böylece "
                   "özellikler tutarlı kalır.")
        s1, s2, s3 = st.columns([1, 1, 1])
        start_day = s1.date_input("Tarih", value=datetime(2020, 6, 21), key="start_day",
                                  min_value=datetime(2020, 6, 21), max_value=datetime(2020, 12, 31))
        start_hour = s2.time_input("Saat", value=time(22, 0), key="start_hour")
        if s3.button("Bu andan başlat", use_container_width=True):
            start = datetime.combine(start_day, start_hour)
            with st.spinner("Kart geçmişi o ana kadar yeniden kuruluyor…"):
                client.reset(until=start)
            state.cursor = int(stream[TIME_COL].searchsorted(pd.Timestamp(start)))
            state.results = []
            st.rerun()

    c1, c2, c3 = st.columns([2, 1, 1])
    batch = c1.select_slider("Her adımda işlem sayısı", [10, 25, 50, 100, 200], value=50)
    if c2.button("▶ Sonraki işlemler", type="primary", use_container_width=True):
        chunk = stream.iloc[state.cursor:state.cursor + batch]
        bar = st.progress(0.0, text="Skorlanıyor…")
        try:
            for i, (_, row) in enumerate(chunk.iterrows(), start=1):
                tx = row[INPUT].to_dict()
                res = client.score({**tx, TIME_COL: tx[TIME_COL].to_pydatetime()})
                state.results.append({**tx, TARGET: int(row[TARGET]), **res})
                state.cursor += 1          # hata olursa aynı işlem ikinci kez gönderilmesin
                bar.progress(i / len(chunk), text=f"Skorlanıyor… {i}/{len(chunk)}")
        except ApiError as exc:
            st.error(str(exc))
        bar.empty()
    if c3.button("↺ Baştan başlat", use_container_width=True):
        client.reset()
        state.cursor, state.results = 0, []
        st.rerun()

    results = pd.DataFrame(state.results)
    k = stream_kpis(results)
    m = st.columns(3) + st.columns(3)          # dar ekranda taşmasın: iki satır
    m[0].metric("İşlem", tr_num(k["işlem"]))
    m[1].metric("Alarm", tr_num(k["alarm"]))
    m[2].metric("Yanlış alarm", tr_num(k["yanlış alarm"]))
    m[3].metric("Yakalanan dolandırıcılık", tr_num(k["yakalanan"]))
    m[4].metric("Kaçan dolandırıcılık", tr_num(k["kaçan"]))
    m[5].metric("Kaçan tutar", money(k["kaçan tutar"]))
    if not results.empty:
        last = results[TIME_COL].iloc[-1]
        st.caption(f"Akışta gelinen an: {pd.Timestamp(last):%d.%m.%Y %H:%M} · "
                   f"{state.cursor:,}/{len(stream):,} işlem".replace(",", "."))
        st.markdown("#### Alarm kuyruğu")
        queue = alert_queue(results)
        if queue.empty:
            st.info("Henüz alarm yok.")
        else:
            st.dataframe(queue, use_container_width=True, hide_index=True, column_config={
                "olasılık": st.column_config.ProgressColumn(
                    "olasılık", format="percent", min_value=0.0, max_value=1.0),
                "tutar ($)": st.column_config.NumberColumn("tutar", format="$%.2f"),
                "beklenen kayıp ($)": st.column_config.NumberColumn("beklenen kayıp",
                                                                    format="$%.0f")})
            st.caption("Gerçek etiket yalnızca bu simülasyonda bilinir; gerçekte etiketler "
                       "(müşteri itirazı, inceleme sonucu) günler sonra gelir.")

# --- 2. İşlem incele ---

with tab_inspect:
    results = pd.DataFrame(st.session_state.get("results", []))
    alerts = results[results["karar"].eq("alarm")] if not results.empty else results
    mode = st.radio("Kaynak", ["Akıştaki bir alarm", "Elle işlem gir"], horizontal=True)
    if mode == "Akıştaki bir alarm":
        if alerts.empty:
            st.info("Önce 'Canlı akış' sekmesinde işlem gönderin.")
        else:
            labels = {f"#{int(r.islem_no)} · {pd.Timestamp(r[TIME_COL]):%d.%m %H:%M} · "
                      f"{money(r.amt)} · {r.category}": i for i, r in alerts.iloc[::-1].iterrows()}
            choice = st.selectbox("Alarm", list(labels))
            row = alerts.loc[labels[choice]]
            st.caption(f"Gerçek etiket: {'dolandırıcılık' if row[TARGET] == 1 else 'normal'}")
            show_result(row.to_dict(), row["amt"])
    else:
        with st.form("manuel"):
            c1, c2, c3 = st.columns(3)
            cc = c1.number_input("Kart numarası", value=4613314721966, step=1, format="%d")
            amt = c2.number_input("Tutar ($)", min_value=0.01, value=912.40, step=10.0)
            category = c3.selectbox("Kategori", sorted(load_stream()["category"].unique()),
                                    index=None, placeholder="Seçin")
            c4, c5, c6 = st.columns(3)
            day = c4.date_input("Tarih", value=datetime(2020, 6, 21))
            hour = c5.time_input("Saat", value=time(23, 15))
            merchant = c6.text_input("Satıcı", value="Kutch, Hermiston and Farrell")
            submitted = st.form_submit_button("Skorla (geçmişe kaydetmeden)", type="primary")
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
    if scores is None:
        st.warning("Skor dosyası yok. Oluşturmak için: `make panel-data`")
    else:
        st.markdown("Karar kuralı: **olasılık × tutar ≥ inceleme ücreti** ise alarm. İnceleme "
                    "ücreti değişirse alarm sayısı, yakalanan tutar ve maliyet nasıl değişir? "
                    "Veri: test dönemi (Faz 3.5 ile aynı model ve kalibrasyon).")
        cost = st.slider("Alarm başına inceleme ücreti ($)", 1, 100, int(REVIEW_COST), step=1)
        y, p, amt = scores[TARGET].to_numpy(), scores["p"].to_numpy(), scores["amt"].to_numpy()
        point = review_cost_point(p, amt, y, cost)
        m = st.columns(5)
        m[0].metric("Alarm", tr_num(point["alarm"]))
        m[1].metric("Precision", pct(point["precision"]))
        m[2].metric("Recall", pct(point["recall"]))
        m[3].metric("Yakalanan tutar", pct(point["tutar recall"]))
        m[4].metric("Toplam maliyet", money(point["maliyet"]),
                    help="Kaçan dolandırıcılık tutarı + alarm sayısı × inceleme ücreti")
        curve = review_cost_curve(p, amt, y, np.arange(1, 101))
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=curve["alarm"], y=curve["tutar recall"], mode="lines",
                                 line=dict(color=NORMAL, width=2), name="ücret 1–100 $",
                                 customdata=curve["inceleme ücreti"],
                                 hovertemplate="ücret $%{customdata}<br>alarm %{x:,}<br>"
                                               "yakalanan tutar %{y:.1%}<extra></extra>"))
        fig.add_trace(go.Scatter(x=[point["alarm"]], y=[point["tutar recall"]], mode="markers",
                                 marker=dict(color=FRAUD, size=12, line=dict(color="white",
                                                                             width=2)),
                                 name=f"seçilen: ${cost}", hoverinfo="skip"))
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=40),
                          xaxis_title="Alarm sayısı (6 ay)",
                          yaxis_title="Yakalanan dolandırıcılık tutarı",
                          yaxis_tickformat=".1%",      # dar aralıkta tam sayı etiketleri çakışır
                          legend=dict(orientation="h", y=1.08))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Hiç alarm vermemenin maliyeti: {money_md(amt[y == 1].sum())}. Ücret arttıkça "
                   "kural yalnızca beklenen kaybı yüksek işlemlere alarm verir: alarm sayısı "
                   "düşer, küçük tutarlı dolandırıcılıklar kaçmaya başlar.")

# --- Durum satırı (en sonda: bu çalıştırmadaki işlemler dahil) ---

try:
    h = client.health()
    status_line.caption(f"API: {client.base_url} · kart geçmişi: {h['kart']} kart, "
                        f"{tr_num(h['islem'])} işlem")
except ApiError as exc:
    status_line.error(str(exc))

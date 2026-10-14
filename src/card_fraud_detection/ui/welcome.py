"""Karşılama sekmesi: gazete ön sayfası (manşet, gece kadranı, iri rakamlar, sütunlar).

Rakamlar elle yazılmaz; çağıran taraf model meta verisinden ve test dönemi skorlarından
hesaplayıp verir (`summary`). Veri yoksa ilgili rakamlar ve manşetteki pay gösterilmez.
"""

from __future__ import annotations

from card_fraud_detection.formatting import tr_ek, tr_num
from card_fraud_detection.ui import theme

REPO = "https://github.com/TolgaARSLANN/card-fraud-detection"


def _p(text: str) -> str:
    return f"<p>{theme.rich(text)}</p>"


def _ul(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{theme.rich(x)}</li>" for x in items) + "</ul>"


def stats(summary: dict | None) -> list[tuple[str, str]]:
    """summary: pr_auc, tutar_recall, maliyet, alarmsiz_maliyet (hepsi isteğe bağlı)."""
    s, out = summary or {}, []
    if s.get("pr_auc") is not None:
        out.append((tr_num(s["pr_auc"], 3), "Test döneminde PR-AUC (1,0 kusursuz sıralama)"))
    if s.get("tutar_recall") is not None:
        out.append((f"%{tr_num(100 * s['tutar_recall'], 1)}",
                    "Dolandırıcılık tutarının yakalanan payı (6 aylık test)"))
    if s.get("maliyet") is not None and s.get("alarmsiz_maliyet") is not None:
        out.append((f"${tr_num(s['maliyet'])}",
                    f"Toplam maliyet; hiç alarm vermemek ${tr_num(s['alarmsiz_maliyet'])} olurdu"))
    return out


def _headline(share: float | None) -> str:
    if share is None:
        return "Kart dolandırıcılığını <em>işlem anında</em> yakalamak."
    pay = str(round(100 * share))
    return f"Dolandırıcılığın <em>%{pay}&#8217;{tr_ek(pay)}</em> gece gelir."


def welcome_html(summary: dict | None, demo: bool, stream_limit: int | None = None) -> str:
    share = (summary or {}).get("gece_payi")
    lead = theme.front(
        "Baş haber · Test dönemi, 21 Haziran – 31 Aralık 2020",
        _headline(share),
        "Bu panel o saatlerde nöbet tutar: her kart işlemini **işlem anında**, yalnızca o ana "
        "kadar bilinen bilgilerle puanlar ve şüpheli olanları inceleme kuyruğuna gönderir.",
        "İşlemlerin yalnızca ~%0,5'i dolandırıcılık. Bir inceleme ekibi her işleme bakamaz; amaç, "
        "az sayıda alarmla dolandırıcılığın büyük kısmını yakalamak ve her alarmın **nedenini** "
        "göstermek.",
        share)

    how = theme.columns([
        ("I", "Neyi amaçlıyor?",
         _p("Model **hangi işlemi neden** şüpheli bulduğunu gösterir; inceleme ücretiyle "
            "kaçırılan dolandırıcılık arasındaki dengeyi ölçülebilir kılar.")),
        ("II", "Nasıl karar veriyor?",
         _ul(["**LightGBM**, kartın geçmişinden hesaplanan 19 özelliğe bakar: son 1 saat / "
              "24 saat / 7 gün harcaması, tutarın kartın ve kategorinin normuna oranı, saat.",
              "Kural: **olasılık × tutar ≥ $10** inceleme ücreti ise alarm.",
              "Her alarmın en güçlü **3 nedeni** (SHAP) Türkçe yazılır."])),
        ("III", "Veri ve gizlilik",
         _p("Veriler **tamamen sentetiktir** (Sparkov simülatörü). Kart numaraları takma "
            "numaralarla değiştirildi; ad, adres, doğum tarihi demoya hiç girmez. Yaş ve "
            "cinsiyet modelde kullanılmaz.")),
    ])

    limit = (f"Demo'da oturum başına en fazla **{tr_num(stream_limit)} işlem**." if demo
             and stream_limit else "Skorlanan işlemler kartın geçmişine eklenir.")
    usage = theme.columns([
        ("1", "Canlı akış",
         _ul(["**Sonraki →** ile test dönemindeki işlemleri sırayla skorlayın.",
              "**Başlangıç anı** ile bir geceden başlayın; dolandırıcılık gece gelir.",
              "Rakam şeridi ve alarm kuyruğu her adımda güncellenir. " + limit])),
        ("2", "İşlem incele",
         _ul(["Akıştaki bir **alarmı** seçin ya da **Elle işlem gir** ile senaryo kurun.",
              "Demo'da kart, listedeki **sentetik kartlardan** seçilir." if demo else
              "Kart numarası, tutar, kategori, saat ve satıcıyı girin.",
              "Karar damgası, olasılık, beklenen kayıp ve **3 neden** görünür."])),
        ("3", "Eşik ve maliyet",
         _ul(["**Alarm başına inceleme ücretini** kaydırın.",
              "6 aylık testte alarm sayısı, precision, recall ve toplam maliyeti izleyin.",
              "Ücret arttıkça yalnızca beklenen kaybı yüksek işlemlere alarm verilir."])),
    ])

    foot = ["Sonuçlar sentetik veriye aittir; gerçek bir ödeme sisteminde kullanılmaz.",
            "Gerçek etiket yalnızca bu simülasyonda bilinir; gerçekte günler sonra gelir."]
    if demo:
        foot += ["Her ziyaretçinin akışı yalnızca kendi oturumunu etkiler; 15 dakika işlem "
                 "yapılmazsa oturum sıfırlanır.",
                 "Uygulama 12 saat ziyaret edilmezse uyur; açılışta \"Yes, get this app back "
                 "up!\" düğmesine basıp yaklaşık bir dakika bekleyin."]
    aside = (f"<p><b>Kaynak ve yöntem.</b> Yöntem, testler ve tek seferlik test değerlendirmesi: "
             f'<a href="{REPO}" target="_blank" rel="noopener">TolgaARSLANN/card-fraud-detection'
             f"</a></p>")

    return "".join([
        lead,
        theme.figures(stats(summary)),
        theme.section("Proje", "Bu panel ne yapıyor?", index=1),
        how,
        theme.section("Kullanım", "Üç adımda deneyin",
                      "Üstteki bölümler sırasıyla bu adımlara karşılık gelir.", index=2),
        usage,
        theme.cta("Başlamak için üstteki <b>Canlı akış</b> bölümüne geçin ve "
                  "<b>Sonraki →</b> düğmesine basın."),
        theme.section("Notlar", "Bilmeniz gerekenler", index=3),
        theme.notes([theme.esc(n) for n in foot], aside),
    ])

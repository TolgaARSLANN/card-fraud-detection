"""Karşılama sekmesi: projenin amacı, nasıl karar verdiği, veri ve kullanım adımları.

Öne çıkan sonuçlar elle yazılmaz; çağıran taraf model meta verisinden ve test dönemi
skorlarından hesaplayıp verir (`summary`). Veri yoksa ilgili rakamlar gösterilmez.
"""

from __future__ import annotations

from card_fraud_detection.formatting import tr_num
from card_fraud_detection.ui import theme

REPO = "https://github.com/TolgaARSLANN/card-fraud-detection"


def _rich(text: str) -> str:
    """Kaçışlı satır içi metin; **kalın** desteklenir."""
    parts = theme.esc(text).split("**")
    return "".join(f"<b>{s}</b>" if i % 2 else s for i, s in enumerate(parts))


def _p(text: str) -> str:
    return f"<p>{_rich(text)}</p>"


def _ul(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{_rich(x)}</li>" for x in items) + "</ul>"


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


def welcome_html(summary: dict | None, demo: bool, stream_limit: int | None = None) -> str:
    hero = theme.hero(
        "Kart dolandırıcılığını işlem anında yakalamak",
        "Her kart işlemi, yalnızca o ana kadar bilinen bilgilerle puanlanır ve şüpheli olanlar "
        "inceleme kuyruğuna gönderilir. İşlemlerin yalnızca ~%0,5'i dolandırıcılık olduğu için "
        "amaç, az sayıda alarmla dolandırıcılığın büyük kısmını yakalamak.",
        stats(summary), night_share=(summary or {}).get("gece_payi"), accent="işlem anında")

    about = theme.grid([
        theme.card("target", "Neyi amaçlıyor?",
                   _p("Bir bankanın inceleme ekibi her işleme bakamaz. Panel, model **hangi "
                      "işlemi neden** şüpheli bulduğunu gösterir ve inceleme ücretiyle "
                      "kaçırılan dolandırıcılık arasındaki dengeyi ölçülebilir kılar.")),
        theme.card("cpu", "Nasıl karar veriyor?",
                   _ul(["**LightGBM** modeli, kartın geçmişinden hesaplanan 19 özelliğe bakar: "
                        "son 1 saat / 24 saat / 7 gündeki harcama, tutarın kartın ve "
                        "kategorinin normuna oranı, saat, yeni satıcı.",
                        "Kural: **olasılık × tutar ≥ $10** inceleme ücreti ise alarm.",
                        "Her alarm için kararı en çok etkileyen **3 neden** (SHAP) Türkçe "
                        "gösterilir."])),
        theme.card("lock", "Veri ve gizlilik",
                   _p("Veriler **tamamen sentetiktir** (Sparkov simülatörü). Kart numaraları "
                      "takma numaralarla değiştirildi; ad, adres, doğum tarihi gibi alanlar "
                      "demoya hiç girmez. Yaş ve cinsiyet modelde kullanılmaz."),
                   theme.OK),
    ])

    limit = (f"Demo'da oturum başına en fazla **{tr_num(stream_limit)} işlem** "
             "skorlanabilir." if demo and stream_limit else
             "Skorlanan işlemler kartın geçmişine eklenir.")
    usage = theme.grid([
        theme.step_card(1, "Canlı akış", [
            "**Sonraki →** ile test dönemindeki işlemleri sırayla skorlayın.",
            "**Başlangıç anı** ile bir geceden başlayın; dolandırıcılık çoğunlukla gece gelir.",
            "Üstte yakalanan / kaçan sayıları, altta alarm kuyruğu güncellenir. " + limit,
        ], "activity"),
        theme.step_card(2, "İşlem incele", [
            "Akıştaki bir **alarmı** seçin ya da **Elle işlem gir** ile kendi senaryonuzu "
            "kurun.",
            "Demo'da kart, listedeki **sentetik kartlardan** seçilir; tutar, kategori, saat "
            "ve satıcıyı değiştirin." if demo else
            "Kart numarası, tutar, kategori, saat ve satıcıyı girin.",
            "Karar, olasılık, beklenen kayıp ve **en güçlü 3 neden** görünür.",
        ], "search"),
        theme.step_card(3, "Eşik ve maliyet", [
            "**Alarm başına inceleme ücretini** kaydırın.",
            "6 aylık test döneminde alarm sayısı, precision, recall ve toplam maliyetin nasıl "
            "değiştiğini görün.",
            "Ücret arttıkça yalnızca beklenen kaybı yüksek işlemlere alarm verilir.",
        ], "sliders"),
    ])

    notes = [
        "Sonuçlar sentetik veriye aittir; gerçek bir ödeme sisteminde kullanılmaz.",
        "Gerçek etiket yalnızca bu simülasyonda bilinir; gerçekte günler sonra gelir.",
    ]
    if demo:
        notes += ["Her ziyaretçinin akışı yalnızca kendi oturumunu etkiler; 15 dakika işlem "
                  "yapılmazsa oturum sıfırlanır.",
                  "Uygulama 12 saat ziyaret edilmezse uyur; açılışta \"Yes, get this app back "
                  "up!\" düğmesine basıp yaklaşık bir dakika bekleyin."]
    good_to_know = theme.grid([
        theme.card("alert", "Bilmeniz gerekenler", _ul(notes)),
        theme.card("database", "Kaynak ve yöntem",
                   "<p>Yöntem, testler ve tek seferlik test değerlendirmesi kaynak repoda: "
                   f'<a href="{REPO}" target="_blank" rel="noopener">'
                   f"TolgaARSLANN/card-fraud-detection</a></p>"),
    ])

    return "".join([
        hero,
        theme.section("Proje", "Bu panel ne yapıyor?", index=1),
        about,
        theme.section("Kullanım", "Üç adımda deneyin",
                      "Üstteki sekmeler sırasıyla bu adımlara karşılık gelir.", index=2),
        usage,
        theme.cta("Başlamak için üstteki <b>Canlı akış</b> sekmesine geçin ve "
                  "<b>Sonraki →</b> düğmesine basın."),
        theme.section("Notlar", "Sınırlar ve kaynak", index=3),
        good_to_know,
    ])

# Arayüz v4: "Gece Bülteni"

Önceki tasarımlar ([v3](arayuz-v3.md), [v2](arayuz-v2.md), [ilk](gece-nobeti.md)) renkleri
değiştirse de aynı iskeleti taşıyordu: koyu konsol zemini, yuvarlatılmış kutu kartlar, küçük
başlık. v4 iskeleti değiştirir: panel bir **finans gazetesinin ön sayfası** gibi okunur.

Kod: `src/card_fraud_detection/ui/theme.py`, `src/card_fraud_detection/ui/welcome.py`,
`.streamlit/config.toml` (açık tema).

## Çıkış noktası
`ui-ux-pro-max` ("editorial financial report premium light serif data storytelling",
çeşitlilik 9) ve stil / tipografi aramaları. Alınanlar ve bilerek değiştirilenler:

| Öneri | Karar | Neden |
|---|---|---|
| Editorial Grid / Magazine | Alındı | Asimetrik ızgara, sütunlar, büyük ilk harf, ayırıcı çizgiler |
| Exaggerated Minimalism | Alındı | Dev künye adı ve manşet, bol boşluk |
| "Magazine Style": Libre Bodoni + Public Sans | Alındı | Gazete serifi; okunaklı gövde yazısı |
| Brutalism | **Kısmen**: yalnızca kalın siyah çizgiler | Kaba "anti-tasarım" bir veri paneline güven vermez |
| Cormorant / Montserrat (lüks moda) | **Alınmadı** | Moda markası tonu; finans bültenine uymuyor |
| Scroll-triggered storytelling | **Alınmadı** | Streamlit'te kaydırmaya bağlı efekt güvenilir değil; okuma sırası yeterli |

## Fikir: gündüz kâğıdı, gece kadranı
Sayfa açık, sıcak bir gazete kâğıdıdır. Tek koyu alan "gece fotoğrafı"dır: 24 saatlik nöbet
saati, gece dilimi (22:00–04:00) altın yay. Manşet veriden yazılır: **"Dolandırıcılığın %84'ü
gece gelir."** (pay test dönemi skorlarından hesaplanır; veri yoksa genel manşet).

## Öğeler
- **Künye:** tarih satırı (sayı, tarih, durum), dev Bodoni ad, italik slogan, çift çizgi.
- **Okur notu:** demo uyarısı kırmızı etiketli not.
- **Bölüm çubuğu:** büyük harfli sekmeler, seçili sekmede kırmızı alt çizgi; telefonda 2×2.
- **Ön sayfa:** manşet (kırmızı italik vurgu), alt başlık, büyük ilk harfli gövde, gece
  kadranı; altında iri Bodoni rakam şeridi; Roma rakamlı "nasıl çalışır" ve 1-2-3 "nasıl
  kullanılır" sütunları (kutu yok, ince çizgilerle ayrılır); siyah çağrı bandı; dipnotlar.
- **Rakam şeridi (metrikler):** iri serif rakamlar, ince dikey çizgiler; satır başları
  Python'da işaretlenir.
- **Karar:** müfettiş damgası, eğik çerçeveli "ALARM" / "ONAY" (renk + simge + yazı),
  iri rakamlar, üç dilimli risk göstergesi.
- **Nedenler:** kırmızı italik numaralı dipnot dizisi, ince kırmızı çubuklar.
- **Grafikler:** açık zemin, mürekkep çizgi; canlı kadranda gece dilimi gri.

## Renk rolleri
| Belirteç | Değer | Rol | Kontrast (kâğıt üzerinde) |
|---|---|---|---|
| `INK` (zemin) | #f4efe4 | gazete kâğıdı | |
| `PAPER` / `RULE` | #16130f | mürekkep: metin, çizgi, birincil düğme | ~17:1 |
| `MUTED` | #57514a | ikincil metin | ~7:1 |
| `SIGNAL` | #b42318 | yalnızca alarm / dolandırıcılık, vurgu numaraları | ~6:1 |
| `OK` | #16643a | yalnızca "onay" | ~6,6:1 |
| `GOLD` | #e0b44c | gece kadranı (yalnızca koyu zeminde) | |

Streamlit'in tema rengi mürekkeptir (kaydırıcı, seçim düğmesi); kırmızı yalnızca alarma
ayrıldığı için tema rengi kırmızı yapılmadı.

## Erişilebilirlik
Metin kontrastları AA üstü; anlam yalnızca renkle verilmez (damga: simge + yazı; risk: dilim
sayısı + yazı + `aria-label`); düğme ve sekmeler en az 44 px; odak halkası mürekkep;
"hareketi azalt" tercihinde geçişler kapalı; 375 px'de yatay taşma yok.

# Arayüz v3: "Gece Nöbeti" izleme konsolu

Panelin üçüncü tasarımı (önceki: [arayuz-v2.md](arayuz-v2.md), ilk: [gece-nobeti.md](gece-nobeti.md)).
Amaç: v2'nin temiz ama sıradan "koyu dashboard" görünümünü **ayırt edici** ve daha
**profesyonel** yapmak. Kod: `src/card_fraud_detection/ui/theme.py`,
`src/card_fraud_detection/ui/welcome.py`, `.streamlit/config.toml`.

## Çıkış noktası
`ui-ux-pro-max` önerileri ("fintech risk monitoring console professional", çeşitlilik 7,
yoğunluk 7; ayrıca tipografi araması). Alınanlar ve bilerek değiştirilenler:

| Öneri | Karar | Neden |
|---|---|---|
| Stil: Minimalism & Swiss Style | Alındı | Kurumsal / profesyonel araçlar için; keskin köşeler (8 px), ızgara disiplini, tipografiyle hiyerarşi |
| Yazı: IBM Plex Sans | Alındı (+ IBM Plex Mono) | Bankacılık ve fintech için önerildi; Inter ya da Fira'dan daha karakterli |
| Ana renk amber (#F59E0B), "gold trust" | Alındı, marka rengi yapıldı (#f5b544) | "Nöbetçinin feneri": proje adıyla anlam bağı; koyu yazıyla ~10:1 kontrast |
| Vurgu rengi mor (#8B5CF6) | **Alınmadı** | Aracın kendi "kaçın" listesinde ("AI purple"); anlam taşımıyor |
| Sayfa yapısı "Trust & Authority + Conversion" | **Alınmadı** | Satış odaklı; bir demo paneline uymuyor |

## İmza öğesi: nöbet saati
Karşılama ekranındaki 24 saatlik kadran: 24 çentik, gece dilimi (22:00–04:00) amber yay,
ortada dolandırıcılığın gece payı. Pay **test dönemi skorlarından hesaplanır** (şu an %84);
veri yoksa kadran rakamsız çizilir. Canlı akış kadranı aynı görsel dili kullanır: gece dilimi
arka planda amber bir dilim. Böylece marka, projenin en önemli veri bulgusundan doğar.

## Renk rolleri
| Belirteç | Değer | Rol |
|---|---|---|
| `INK` / `SURFACE` / `SURFACE_2` | #0a0f1c / #101828 / #172235 | gece laciverti zemin, kart, vurgulu yüzey |
| `PAPER` / `MUTED` | #f1f5f9 / #9aa8bd | birincil (~17:1) / ikincil metin (kart üzerinde ~7:1) |
| `LAMP` | #f5b544 | marka, eylem düğmesi (koyu yazı), seçili sekme, odak halkası |
| `SIGNAL` | #f87171 | yalnızca alarm / dolandırıcılık |
| `OK` | #4ade80 | yalnızca "onay" |
| `CALM` | #7aa2f7 | grafiklerde normal işlem |

Risk seviyesi renkle değil **üç dilimli göstergeyle** (dolu dilim sayısı + yazı +
`aria-label`) verilir; amber yalnızca markaya ve eyleme ayrılmıştır.

## Bileşen kararları
- Sekmeler segmentli kontrol; seçili sekmede amber alt çizgi. Telefonda (375 px) dört sekme
  kaydırmasız sığar, her biri 40 px yüksekliğinde.
- Bölüm başlıkları numaralı ("01 · Proje"), kullanım kartları "ADIM 01".
- Karar kartı: renkli sol kenar + simge + yazı; risk göstergesi; nedenler numaralı liste.
- Sayılar IBM Plex Mono, eşit genişlikli rakamlar (güncellenirken kaymaz).
- Düğmeler en az 44 px, odak halkası amber, hareket 150–200 ms ve "hareketi azalt"
  tercihinde kapalı; simgeler Lucide SVG (`aria-hidden`).

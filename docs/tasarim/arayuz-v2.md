# Arayüz v2: izleme konsolu

Panelin ikinci tasarımı (ilk tasarım: [gece-nobeti.md](gece-nobeti.md)). Kod:
`src/card_fraud_detection/ui/theme.py` (belirteçler ve bileşenler),
`src/card_fraud_detection/ui/welcome.py` (karşılama içeriği), `.streamlit/config.toml`.

## Çıkış noktası
`ui-ux-pro-max` tasarım sistemi önerisi ("fintech fraud detection monitoring dashboard dark
data-dense"). Öneriden alınanlar ve bilerek değiştirilenler:

| Öneri | Karar | Neden |
|---|---|---|
| Stil: Dark Mode (OLED), yüksek kontrast | Alındı | Gece izleme konsolu, uzun süre bakılan ekran |
| Yazı: Fira Sans + Fira Code | Alındı | Veri paneli için okunaklı; rakamlar eşit genişlikte (tabular) |
| Yüzeyler: slate tonları (#020617 / #0e1223) | Alındı | |
| Eylem rengi yeşil (#22C55E) | **Değiştirildi: mavi #2563eb** | Bu panelde yeşil "onay" kararıdır; eylem de yeşil olsaydı anlamlar karışırdı |
| Sayfa yapısı "Enterprise Gateway" | **Alınmadı** | Satış/iletişim yapısı; bir demo paneline uymuyor |

## Renk rolleri
Her renk tek bir anlam taşır ve anlam yalnızca renkle verilmez (yanında simge ve yazı vardır).

| Belirteç | Değer | Rol | Kontrast |
|---|---|---|---|
| `INK` | #020617 | zemin | |
| `SURFACE` | #0e1223 | kart | |
| `PAPER` | #f8fafc | birincil metin | zemin üzerinde ~19:1 |
| `MUTED` | #94a3b8 | ikincil metin | kart üzerinde ~7:1 |
| `PRIMARY` | #2563eb | eylem düğmesi | beyaz yazıyla 5,2:1 |
| `PRIMARY_SOFT` | #93c5fd | seçili sekme, bağlantı, odak halkası | |
| `SIGNAL` | #f87171 | yalnızca alarm / dolandırıcılık | kart üzerinde ~6:1 |
| `OK` | #4ade80 | yalnızca "onay" kararı | |
| `WARN` | #fbbf24 | orta risk, "bilmeniz gerekenler" | |
| `CALM` | #60a5fa | grafiklerde normal işlem | |

## İlkeler
- **Karşılama sekmesi** ilk açılan sekmedir: amaç, nasıl karar verdiği, veri ve gizlilik,
  üç adımlık kullanım, bilmeniz gerekenler. Öne çıkan sonuçlar elle yazılmaz; model meta
  verisinden ve test dönemi skorlarından hesaplanır (veri yoksa gösterilmez).
- Simgeler emoji değil, satır içi SVG (Lucide, 2 px çizgi); metnin yanındakiler
  `aria-hidden`.
- Düğmeler en az 44 px yükseklik; klavye odağı her zaman görünür (2 px halka).
- Hareket kısa (200 ms) ve yalnızca durum değişiminde; "hareketi azalt" tercihinde kapalı.
- Kartlar `auto-fit` ızgarada; telefonda tek sütuna iner, yatay taşma yok (375 px'de
  doğrulandı).
- Metrik etiketleri büyük harfe çevrilmez: Türkçe büyük harf kuralı (`lang="tr"`)
  İngilizce terimleri bozuyordu ("PRECİSİON").

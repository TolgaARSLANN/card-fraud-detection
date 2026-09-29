# Hata Analizi (Faz 3.4)

_Üreten: `python -m card_fraud_detection.evaluation.error_analysis` · Mayıs ve Haziran 2020 (doğrulama), her ay önceki aylarla kalibre edilmiş alarmlar (Faz 3.3 ile aynı) · Kural: beklenen maliyet_

## 1. Genel tablo

| sonuç | işlem |
|---|---|
| doğru sessizlik | 131065 |
| yakalandı | 768 |
| yanlış alarm | 164 |
| kaçtı | 93 |

Dolandırıcılık tutarı $467,456; kaçan $3,832 (%0.8). Kaçanların %92'i $50'nin altında; $200 ve üzeri kaçan dolandırıcılık 4 adet.

## 2. Kaçan dolandırıcılıklar

### Tutara göre

| tutar ($) | dolandırıcılık | kaçan | kaçan tutar ($) | kaçma oranı | kaçan tutar payı |
|---|---|---|---|---|---|
| <10 | 57 | 57 | 471 | 1.000 | 0.123 |
| 10–50 | 126 | 29 | 619 | 0.230 | 0.161 |
| 50–100 | 6 | 2 | 147 | 0.333 | 0.038 |
| 100–200 | 13 | 1 | 110 | 0.077 | 0.029 |
| 200–500 | 224 | 1 | 306 | 0.004 | 0.080 |
| 500–1000 | 331 | 3 | 2179 | 0.009 | 0.569 |
| ≥1000 | 104 | 0 | 0 | 0.000 | 0.000 |

### Kategoriye göre

| kategori | dolandırıcılık | kaçan | kaçan tutar ($) | kaçma oranı | kaçan tutar payı |
|---|---|---|---|---|---|
| gas_transport | 76 | 37 | 352 | 0.487 | 0.092 |
| misc_pos | 31 | 16 | 213 | 0.516 | 0.056 |
| kids_pets | 24 | 9 | 128 | 0.375 | 0.033 |
| personal_care | 29 | 8 | 220 | 0.276 | 0.057 |
| health_fitness | 19 | 6 | 117 | 0.316 | 0.030 |
| grocery_net | 13 | 6 | 63 | 0.462 | 0.016 |
| travel | 9 | 5 | 48 | 0.556 | 0.012 |
| shopping_pos | 104 | 2 | 1436 | 0.019 | 0.375 |
| food_dining | 14 | 2 | 207 | 0.143 | 0.054 |
| home | 23 | 1 | 306 | 0.043 | 0.080 |
| misc_net | 115 | 1 | 743 | 0.009 | 0.194 |
| entertainment | 21 | 0 | 0 | 0.000 | 0.000 |
| grocery_pos | 188 | 0 | 0 | 0.000 | 0.000 |
| shopping_net | 195 | 0 | 0 | 0.000 | 0.000 |

### Saate göre

| saat | dolandırıcılık | kaçan | kaçan tutar ($) | kaçma oranı | kaçan tutar payı |
|---|---|---|---|---|---|
| gece (22–03) | 731 | 72 | 1780 | 0.098 | 0.465 |
| gündüz (04–21) | 130 | 21 | 2052 | 0.162 | 0.535 |

### Patlamadaki sıraya göre

| patlamadaki sıra | dolandırıcılık | kaçan | kaçan tutar ($) | kaçma oranı | kaçan tutar payı |
|---|---|---|---|---|---|
| 1 | 88 | 14 | 1544 | 0.159 | 0.403 |
| 2 | 88 | 11 | 962 | 0.125 | 0.251 |
| 3 | 86 | 14 | 267 | 0.163 | 0.070 |
| 4 | 84 | 12 | 174 | 0.143 | 0.045 |
| 5+ | 515 | 42 | 886 | 0.082 | 0.231 |

### $200 ve üzeri kaçan dolandırıcılıklar

Kuralın bilerek atladığı küçük işlemler değil. Çoğunda tutar kategori medyanının ve kart ortalamasının çok üzerinde, ama eşlik eden bir patlama yok (24 sa tutar düşük); model aşırı sapmayı tek başına yeterli saymıyor.

| kaçan ≥$200 | amt | category | hour | p | amt_to_cat_median | amt_to_card_mean | amt_sum_24h | n_24h | p × tutar |
|---|---|---|---|---|---|---|---|---|---|
| işlem 121613 | 656.000 | shopping_pos | 1 | 0.002 | 84.645 | 12.741 | 99.890 | 4 | 1.519 |
| işlem 183974 | 780.140 | shopping_pos | 18 | 0.000 | 100.663 | 13.617 | 317.680 | 8 | 0.009 |
| işlem 189434 | 742.740 | misc_net | 7 | 0.001 | 75.405 | 8.461 | 69.020 | 2 | 0.478 |
| işlem 192648 | 306.260 | home | 22 | 0.015 | 6.345 | 5.603 | 457.400 | 6 | 4.713 |

Patlama sayısı 90; **tamamen kaçan patlama 1** (toplam $20; işlem sayıları [2]).

## 3. Yanlış alarmlar

### Tutara göre

| tutar ($) | normal işlem | yanlış alarm | alarm | yanlış alarm oranı | precision |
|---|---|---|---|---|---|
| <10 | 34243 | 0 | 0 | 0.0000 |  |
| 10–50 | 33760 | 9 | 106 | 0.0003 | 0.9151 |
| 50–100 | 40026 | 1 | 5 | 0.0000 | 0.8000 |
| 100–200 | 17593 | 6 | 18 | 0.0003 | 0.6667 |
| 200–500 | 4406 | 18 | 241 | 0.0041 | 0.9253 |
| 500–1000 | 897 | 94 | 422 | 0.1048 | 0.7773 |
| ≥1000 | 304 | 36 | 140 | 0.1184 | 0.7429 |

### Kategoriye göre

| kategori | normal işlem | yanlış alarm | alarm | yanlış alarm oranı | precision |
|---|---|---|---|---|---|
| shopping_net | 9726 | 45 | 240 | 0.0046 | 0.8125 |
| shopping_pos | 11878 | 39 | 141 | 0.0033 | 0.7234 |
| misc_net | 6537 | 32 | 146 | 0.0049 | 0.7808 |
| misc_pos | 8116 | 11 | 26 | 0.0014 | 0.5769 |
| entertainment | 9559 | 9 | 30 | 0.0009 | 0.7000 |
| food_dining | 9081 | 7 | 19 | 0.0008 | 0.6316 |
| travel | 4009 | 4 | 8 | 0.0010 | 0.5000 |
| home | 12328 | 4 | 26 | 0.0003 | 0.8462 |
| grocery_net | 4747 | 4 | 11 | 0.0008 | 0.6364 |
| health_fitness | 8706 | 3 | 16 | 0.0003 | 0.8125 |
| kids_pets | 11460 | 3 | 18 | 0.0003 | 0.8333 |
| grocery_pos | 12427 | 2 | 190 | 0.0002 | 0.9895 |
| personal_care | 9135 | 1 | 22 | 0.0001 | 0.9545 |
| gas_transport | 13520 | 0 | 39 | 0.0000 | 1.0000 |

### Saate göre

| saat | normal işlem | yanlış alarm | alarm | yanlış alarm oranı | precision |
|---|---|---|---|---|---|
| gece (22–03) | 30498 | 95 | 754 | 0.0031 | 0.8740 |
| gündüz (04–21) | 100731 | 69 | 178 | 0.0007 | 0.6124 |

### Kartlara dağılım

| yanlış alarmların kartlara dağılımı | değer |
|---|---|
| yanlış alarm | 164.000 |
| yanlış alarm alan kart | 149.000 |
| en çok alarm alan %10 kartın payı | 0.183 |
| kart başına en fazla yanlış alarm | 2.000 |

## 4. Patlama sonrası yanlış alarmlar

Kart geçmişi özellikleri (24 sa / 7 g tutar, kart ortalaması) patlamanın izini bir süre taşır; bu, kart sahibinin patlamadan sonraki gerçek işlemlerinde yanlış alarm üretebilir.

| normal işlem | normal işlem | yanlış alarm | yanlış alarm oranı |
|---|---|---|---|
| diğer normal işlemler | 130671 | 157 | 0.0012 |
| son 72 saatte dolandırıcılık görmüş kart | 558 | 7 | 0.0125 |

Yanlış alarmların %4.3'i son 72 saatte dolandırıcılık görmüş kartlarda.

## 5. Adalet kontrolü (model yaş ve cinsiyeti kullanmıyor)

| yaş | işlem | dolandırıcılık | recall | yanlış alarm oranı (‰) |
|---|---|---|---|---|
| <25 | 11769 | 62 | 0.919 | 1.025 |
| 25–34 | 27588 | 186 | 0.909 | 1.168 |
| 35–44 | 28682 | 128 | 0.828 | 1.191 |
| 45–54 | 26694 | 170 | 0.871 | 1.131 |
| 55–64 | 16402 | 153 | 0.922 | 1.292 |
| ≥65 | 20955 | 162 | 0.907 | 1.683 |

| cinsiyet | işlem | dolandırıcılık | recall | yanlış alarm oranı (‰) |
|---|---|---|---|---|
| F | 72272 | 424 | 0.880 | 1.531 |
| M | 59818 | 437 | 0.904 | 0.909 |

Kart düzeyinde (işlemler kartlara göre kümelendiği için ayrıca):

| cinsiyet | yanlış alarm alan kart oranı |
|---|---|
| F | 0.217 |
| M | 0.109 |

### Cinsiyet farkı nereden geliyor?

Model cinsiyeti kullanmıyor; fark cinsiyetle ilişkili bir özellik üzerinden gelmeli. Farkın büyük kısmı $500 üzerindeki gerçek alışverişlerde. Kategori karışımı:

| kategori (≥$500 normal işlem) | işlem payı: F | işlem payı: M | yanlış alarm (‰): F | yanlış alarm (‰): M |
|---|---|---|---|---|
| shopping_pos | 0.408 | 0.181 | 101.887 | 120.000 |
| shopping_net | 0.279 | 0.168 | 171.271 | 139.785 |
| misc_net | 0.126 | 0.100 | 280.488 | 163.636 |
| misc_pos | 0.117 | 0.136 | 105.263 | 26.667 |
| travel | 0.060 | 0.406 | 25.641 | 8.929 |

| ≥$500 normal işlemde yanlış alarm | ham (‰) | kategori × gece karışımı eşitlenmiş (‰) |
|---|---|---|
| F | 140 | 120 |
| M | 71 | 94 |

Kategori ve gece/gündüz karışımı iki grupta eşitlendiğinde fark belirgin biçimde küçülüyor: Kategori, cinsiyetin yerine geçen bir değişken (vekil) gibi davranıyor. Korunan özelliği modelden çıkarmak, dolaylı farkı tek başına önlemiyor. Veri sentetik; harcama kalıplarını cinsiyete göre simülatör üretiyor.


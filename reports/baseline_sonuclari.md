# Referans Model Sonuçları

_Üreten: `python -m card_fraud_detection.models.baselines` · Eğitim: eğitim bölmesi · Ölçüm: doğrulama bölmesi (198,982 işlem, 1,163 dolandırıcılık, 82 gün)_

## Eşikten bağımsız karşılaştırma (ana ölçüt)

Bütçe: Her gün en yüksek skorlu **25** işlem incelenir (ölçüm döneminde günde ortalama 14.2 dolandırıcılık var).

| model | PR-AUC | ROC-AUC | recall@p0.5 | bütçe: recall | bütçe: tutar recall | bütçe: precision | süre (sn) |
|---|---|---|---|---|---|---|---|
| Lojistik regresyon | 0.625 | 0.987 | 0.753 | 0.723 | 0.868 | 0.410 | 50.090 |
| Isolation Forest | 0.415 | 0.929 | 0.344 | 0.512 | 0.724 | 0.290 | 17.679 |
| Kural tabanlı | 0.212 | 0.941 | 0.000 | 0.478 | 0.602 | 0.271 | 0.010 |
| Yalnızca tutar | 0.187 | 0.840 | 0.000 | 0.458 | 0.785 | 0.260 | 0.000 |

## Maliyete göre seçilen eşikte (iyimser)

\* Eşik, maliyeti (kaçan tutar + alarm başına $10) en aza indirecek biçimde **ölçüm verisinin kendisinde** seçildi; sonuçlar iyimserdir. Nihai eşik Faz 3.3'te doğrulamada seçilip testte sabit tutulacak. Hiç alarm vermemenin maliyeti: $619,630.

| model | eşik*: alarm | eşik*: precision | eşik*: recall | eşik*: tutar recall | eşik*: kaçan tutar ($) | eşik*: maliyet ($) | eşik*: patlama recall | eşik*: ilk işlemde yakalanan |
|---|---|---|---|---|---|---|---|---|
| Lojistik regresyon | 3120 | 0.320 | 0.859 | 0.950 | 30796 | 61996 | 0.992 | 0.532 |
| Isolation Forest | 5382 | 0.144 | 0.666 | 0.874 | 77819 | 131639 | 0.984 | 0.492 |
| Kural tabanlı | 7749 | 0.113 | 0.751 | 0.973 | 16656 | 94146 | 0.984 | 0.782 |
| Yalnızca tutar | 5568 | 0.156 | 0.749 | 0.981 | 12022 | 67702 | 0.984 | 0.790 |


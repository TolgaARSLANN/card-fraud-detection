# Space Ölçümü (Faz 5, ara rapor)

_Ortam: Docker Desktop (WSL 2), imaj `build/space` (python:3.12-slim), `--cpus=2 --memory=3g`.
Ölçüm betiği konteynerin içinde panelin demo arka ucunu aynı nesnelerle ve aynı kod yoluyla
çalıştırır (`python -m card_fraud_detection.space.measure`). Tarih: 2026-10-08._

## Paket
| | |
|---|---|
| Space klasörü (`make space`) | 40 MB (kesit 24 MB, skorlar 12 MB, model 3,5 MB) |
| Kesit | 1.457.879 işlem, 987 kart, 8 sütun; 3 başlangıç × 500 işlemde özellik ve olasılık farkı 0 |
| Duman testi (`make space-smoke`, 2 CPU / 3 GB) | geçti: üç sekmede istisna yok, uid 1000, HTTP 200 |
| Panelin ilk açılışı (AppTest, konteyner içinde) | 13,5 sn (model + geçmiş yükleme dahil) |

## Tek oturum (2 oturum × 50 işlemlik ön ölçümden)
| | |
|---|---|
| Model + geçmiş yükleme | 4,4 sn, ~600 MB |
| Başlangıç katmanları (1 Tem / 15 Ağu) | 0,4 / 0,9 sn; tam kopya yerine katman olduğu için bellek artmıyor |
| İşlem başına skorlama | medyan 90 ms, %95 133 ms |
| 2.000 işlemlik akış (kestirim) | ~3 dk (2.000 × 90 ms) |

## Eşzamanlı oturumlar: kilit karşılaştırması (10 oturum × 300 işlem)
| | oturum başına kilit | tek ortak kilit |
|---|---|---|
| Toplam süre | 540 sn | 247 sn |
| Saniyede işlem | 5,6 | 12,1 |
| İşlem başına süre (medyan / %95) | 1.749 / 2.211 ms | 732 / 1.285 ms |
| En yüksek bellek | 684 MB | 699 MB |

**Bulgu:** Oturum başına kilit beklenenin tersine **2,2 kat yavaş**. Özellik hesabının büyük
kısmı Python'da çalışıyor ve Python'un küresel kilidi (GIL) iş parçacıklarının paralel
ilerlemesine izin vermiyor. Konteyner 2 CPU'dan yalnızca ~1'ini kullandı (%95). Aynı anda
çalışmaya zorlanan oturumlar birbirini yavaşlatıyor; sırayla işlemek hem toplam süreyi hem
işlem başına süreyi düşürüyor. Doğruluk iki yolda da aynı; oturum verileri her iki durumda da
ayrı katmanlarda kalıyor. Ölçüm bir kez ve bu sırayla yapıldı (önce oturum kilidi); ters
sırayla tekrarı süre nedeniyle durduruldu.

**Karar (uygulandı):** Demo'da özellik hesabı ve geçmişe ekleme servisin tek ortak kilidiyle
sırayla yapılıyor (`ScoringService.shared_lock = True`, varsayılan). Oturum verileri yine ayrı
katmanlarda kalıyor. Testler iki modda da eşzamanlı sonuçların tek iş parçacıklı sonuçla
birebir aynı olduğunu doğruluyor. Karşılaştırma ölçümü `measure --compare` ile tekrarlanabilir.

## 16 GB kestirimi ve varsayımları
Ücretsiz Space'in gerçek sınırları (bildiğimiz kadarıyla 2 vCPU, 16 GB) bu makinede
kurulamıyor; bilgisayarın toplam belleği 6,9 GB, Docker'ın kullanabildiği 3,5 GB. Ölçümler
3 GB sınırla yapıldı. 16 GB için kestirim:
- Bellek sorun değil: paylaşılan servis ~600 MB; 10 eşzamanlı oturumla en yüksek ~700 MB.
  **Varsayım:** bir oturum katmanı yalnızca eklediği işlemleri tutar (en fazla 2.000 satır,
  birkaç MB) ve Streamlit'in oturum başına yükü birkaç MB'tır. Bu varsayımla 50 oturumun
  (kayıt sınırı) tamamı bile 1-1,5 GB'ı aşmaz. Streamlit sunucusunun oturum başına gerçek
  belleği ayrıca ölçülmedi.
- Darboğaz işlemci: Space'te de 2 vCPU ve aynı GIL sınırı geçerli. **Varsayım:** HF'nin
  vCPU'su bu makinenin çekirdeğiyle benzer hızdadır; değilse süreler orantılı değişir.
  Ortak kilitle saniyede ~12 işlem, aynı anda akıtan 10 ziyaretçi için kişi başı ~1,2
  işlem/sn demektir.

## Ölçülmeyenler (sıradaki oturumda)
- 10 oturum × 2.000 işlemin tamamı (kestirim: ortak kilitle ~28 dk) ve tek oturumun gerçek
  2.000 işlemlik akışı.
- Streamlit sunucusunun boşta ve ilk ziyaretçiden sonraki belleği (`make space-measure`).
- Kısıtsız çalıştırma (`CPUS=8 MEM=0 make space-measure`).

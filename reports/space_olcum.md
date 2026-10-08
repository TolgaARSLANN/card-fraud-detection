# Space Ölçümü (Faz 5)

_Ortam: Docker Desktop (WSL 2), imaj `build/space` (python:3.12-slim). Asıl kısıt
`--cpus=2 --memory=3g`; ücretsiz Space'e en yakın kurulabilen ayar. Arka uç ölçümü konteynerin
içinde panelin demo arka ucunu aynı nesnelerle ve aynı kod yoluyla çalıştırır
(`make space-measure`); sunucu belleği gerçek Streamlit sunucusunda, tarayıcı oturumlarıyla
`docker stats` ile ölçüldü. Tarih: 2026-10-08._

## Paket
| | |
|---|---|
| Space klasörü (`make space`) | 40 MB (kesit 24 MB, skorlar 12 MB, model 3,5 MB) |
| Kesit | 1.457.879 işlem, 987 kart, 8 sütun; 3 başlangıç × 500 işlemde özellik ve olasılık farkı 0 |
| Duman testi (`make space-smoke`, 2 CPU / 3 GB) | geçti: üç sekmede istisna yok, uid 1000, HTTP 200 |

## Açılış ve sunucu belleği (2 CPU / 3 GB, gerçek Streamlit sunucusu)
| | `MALLOC_ARENA_MAX` yok | `MALLOC_ARENA_MAX=2` (imajda) |
|---|---|---|
| Konteyner → sağlık ucu | 4,1-4,9 sn | aynı |
| Boşta (ziyaretçi yok) | 78-86 MB | 76 MB |
| İlk ziyaretçi: panel hazır | ~9 sn (model + geçmiş yükleme dahil) | aynı |
| İlk ziyaretçiden sonra | 671 MB | 542 MB |
| 3 oturum × 50 işlem | 876 MB | 672 MB |
| Bir oturumda +150 işlem | 936 MB, **artmaya devam** | 668 MB, **sabit** |

**Bulgu ve düzeltme:** Streamlit her oturumun betiğini ayrı bir iş parçacığında çalıştırıyor.
glibc'nin bellek ayırıcısı her iş parçacığı için ayrı havuz (arena) açıyor ve boşalan belleği
sisteme geri vermiyordu; bellek oturum ve işlemle birlikte artıyordu. Bu bir sızıntı değil:
skorlama kodu aynı yükte (aşağıda, 20.000 işlem) yalnızca ~180 MB arttı. Havuz sayısı 2 ile
sınırlanınca (`ENV MALLOC_ARENA_MAX=2`, space/Dockerfile) bellek sabit kaldı.

## Skorlama (2 CPU / 3 GB, konteyner içinde, demo arka ucu)
| | |
|---|---|
| Model + geçmiş yükleme | 4,2 sn; süreç belleği 589 MB |
| Başlangıç katmanları (1 Tem / 15 Ağu) | 0,3 / 0,5 sn; tam kopya yerine katman, bellek artmıyor |
| Tek oturum, 2.000 işlemlik akış | **116 sn**; işlem başına medyan 54 ms, %95 81 ms |
| 10 eşzamanlı oturum × 2.000 işlem (20.000) | **1.328 sn (22 dk)**; saniyede 15,1 işlem |
| ... işlem başına (medyan / %95) | 647 / 802 ms |
| ... süreç belleği | 589 → en fazla 771 MB |

## Kilit karşılaştırması (10 oturum × 300 işlem, 2 CPU / 3 GB)
| | oturum başına kilit | tek ortak kilit |
|---|---|---|
| Toplam süre | 540 sn | 247 sn |
| Saniyede işlem | 5,6 | 12,1 |
| İşlem başına süre (medyan / %95) | 1.749 / 2.211 ms | 732 / 1.285 ms |
| En yüksek bellek | 684 MB | 699 MB |

Oturum başına kilit 2,2 kat yavaştı: özellik hesabının büyük kısmı Python'da çalışıyor ve
Python'un küresel kilidi (GIL) iş parçacıklarının paralel ilerlemesine izin vermiyor (konteyner
2 CPU'dan ~1'ini kullandı). **Karar (uygulandı):** demo'da özellik hesabı ve geçmişe ekleme tek
ortak kilitle sırayla yapılıyor (`ScoringService.shared_lock = True`, varsayılan); oturum
verileri yine ayrı katmanlarda. Testler iki modda da eşzamanlı sonuçların tek iş parçacıklı
sonuçla birebir aynı olduğunu doğruluyor. Karşılaştırma `measure --compare` ile tekrarlanabilir.
(Bu karşılaştırma bir kez ve bu sırayla yapıldı; ters sırayla tekrarı süre nedeniyle durduruldu.)

## Kısıtsız çalıştırma (8 CPU, bellek sınırı yok; 10 oturum × 300 işlem)
| | 8 CPU, sınırsız | 2 CPU / 3 GB (yukarıda) |
|---|---|---|
| Saniyede işlem (10 eşzamanlı oturum) | 14,9 | 15,1 |
| İşlem başına (medyan / %95) | 643 / 836 ms | 647 / 802 ms |
| Tek oturumda işlem başına medyan | 54 ms | 54 ms |
| Model + geçmiş yükleme | 5,4 sn | 4,2 sn |
| Süreç belleği en fazla | 637 MB (3.000 işlem) | 771 MB (20.000 işlem) |

**Bulgu:** Fazla çekirdek hızlandırmıyor; kapasite 2 ve 8 CPU'da aynı (saniyede ~15 işlem).
Skorlama Python'un küresel kilidiyle sınırlı; ücretsiz Space'in 2 vCPU'su bu iş için yeterli.

## Ziyaretçi açısından ne demek
- Tek ziyaretçi: 50 işlemlik bir adım ~3 sn, 2.000 işlemin tamamı ~2 dk.
- 10 ziyaretçi aynı anda akıtırsa toplam kapasite (saniyede ~15 işlem) paylaşılır: kişi başı
  saniyede ~1,5 işlem, 50 işlemlik adım ~35 sn. Demo için kabul edilebilir; daha fazlası için
  özellik hesabını hızlandırmak (kart özetlerini önceden hesaplamak) ya da çok süreçli çalışmak
  gerekir.

## 16 GB kestirimi ve varsayımları
Ücretsiz Space'in sınırları (bildiğimiz kadarıyla 2 vCPU, 16 GB) bu makinede kurulamıyor:
bilgisayarın toplam belleği 6,9 GB, Docker'ın kullanabildiği 3,5 GB. Ölçümler 3 GB sınırla
yapıldı. 16 GB için kestirim:
- **Bellek sorun değil.** `MALLOC_ARENA_MAX=2` ile sunucu ilk ziyaretçiden sonra ~540 MB,
  3 etkin oturumla ~670 MB'ta sabit kaldı. **Varsayım:** daha fazla oturumda da oturum başına
  ek bellek küçük kalır (oturum katmanı en fazla 2.000 satır, sonuç listesi birkaç MB). Bu
  varsayımla 50 oturumluk kayıt sınırının tamamı bile 1-1,5 GB'ı aşmaz. 3'ten fazla eşzamanlı
  tarayıcı oturumu sunucuda ölçülmedi; 10 eşzamanlı oturum yalnızca arka uç ölçümünde (771 MB)
  denendi.
- **Darboğaz işlemci.** Space'te de 2 vCPU ve aynı GIL sınırı geçerli. **Varsayım:** HF'nin
  vCPU'su bu makinenin çekirdeğiyle benzer hızdadır; değilse süreler orantılı değişir.
- **Uyku:** Ücretsiz Space bir süre ziyaret edilmezse uyur; uyanan ilk ziyaretçi konteynerin
  başlamasını (~5 sn burada; HF'de imaj çekme ile daha uzun) ve ~9 sn yüklemeyi bekler.

## Streamlit Community Cloud benzeri kontrol (`make cloud-check`)
Hugging Face Docker Space'leri ücretli plana bağlandığı için yayın yolu Streamlit Community
Cloud oldu. Cloud'da ortam değişkeni süreç başlamadan verilemez; demo modu ve bellek havuzu
sınırı kökteki `streamlit_app.py` içinde ayarlanır (`mallopt`). Kontrol: temiz
python:3.12-slim, `packages.txt` + `requirements.txt` kurulumu, ortam değişkeni yok,
`--cpus=2 --memory=1g`.

| Streamlit süreci (RSS) | Koddan ayar (Cloud) | Docker + `MALLOC_ARENA_MAX=2` | Ayar yok |
|---|---|---|---|
| İlk ziyaretçiden sonra | 648 MB | 542 MB | 671 MB |
| 3 oturum × 50 işlem | 823 MB | 672 MB | 876 MB |
| Bir oturumda +150 işlem | 815 MB, sabit | 668 MB, sabit | 936 MB, artıyor |

Duman testi (üç sekme, giriş dosyası üzerinden) 1 GB sınırda geçti. Koddan ayar artışı
durduruyor ama Docker'dakinden ~150 MB yüksek kalıyor; olası neden, ilk oturumun bellek havuzunun
ayar devreye girmeden açılması. Cloud'un bellek sınırı belirsiz (690 MB-2,7 GB; sık geçen
~1 GB). ~820 MB sıkışık olduğu için yayından önce paylaşılan geçmişin bellek kullanımını
düşürmek öneriliyor (yol haritası 5.6).

## Bellek iyileştirmesi (yol haritası 5.6)
Ölçülen dağılım (servis yüklendikten sonra): kütüphaneler ~290 MB, paylaşılan kart geçmişi
99 MB (kategori ve satıcı metin sütunları bunun büyük kısmı), ham işlem kopyası
(`service.transactions`) 51 MB, panelin akış ve skor tabloları 6 + 18 MB. Panel bu iki tabloyu
`st.cache_data` ile yüklüyordu; `cache_data` her çağrıda kopya döndürür, yani her yenilemede.

Yapılanlar:
1. Yüklenmiş geçmişte kategori ve satıcı kategorik tipte tutuluyor (kart tabloları 99 → 63 MB).
   Yeni işlemler metin kalıyor; özellik kodu iki durumda da aynı değerleri görüyor.
2. Demo'da başlangıç katmanları yüklemede kuruluyor, ham işlem kopyası bırakılıyor (~51 MB).
3. Akış ve skor tabloları `cache_resource` ile tek kopya paylaşılıyor (panel yalnızca okur).

Sonuçlar değişmedi: gerçek veriyle `make consistency` TUTARLI (2.000 işlem, fark 0), `make
space-data` KESİT TUTARLI (3 × 500 işlem, fark 0). Skorlama hızı aynı (medyan ~51 ms).

| Streamlit süreci (Cloud yolu, `make cloud-check`, 1 GB) | Önce | Sonra |
|---|---|---|
| İlk ziyaretçiden sonra | 648 MB | 576 MB |
| 3 oturum × 50 işlem | 823 MB | 577 MB |
| Bir oturumda +150 işlem | 815 MB | 591 MB |

Oturumlarla gelen artış neredeyse tamamen kayboldu (asıl neden büyük olasılıkla her
yenilemedeki tablo kopyalarıydı). ~590 MB, Cloud için kaynaklarda geçen en düşük sınırın
(690 MB) da altında.

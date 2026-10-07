---
title: Gece Nöbeti · Kart Dolandırıcılığı Tespiti
emoji: 🌙
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 8501
pinned: false
license: mit
short_description: Sentetik kart işlemlerinde dolandırıcılık tespiti demosu
---

# Gece Nöbeti · Kart Dolandırıcılığı Tespiti (demo)

Kart işlemlerini işlem anında bilinen bilgilerle puanlayan bir modelin herkese açık demosu.
Kaynak kod, yöntem ve sonuçlar: https://github.com/TolgaARSLANN/card-fraud-detection

- **Veriler tamamen sentetiktir.** Gerçek kişi ya da kart yoktur. Kart numaraları da takma
  numaralarla değiştirilmiştir. Gerçek kart numarası ya da kişisel bilgi girmeyin.
- Proje eğitim ve portföy amaçlıdır; gerçek bir ödeme sisteminde kullanılmaz.
- Her ziyaretçinin akışı yalnızca kendi oturumunu etkiler. Oturum başına 2.000 işlem sınırı
  vardır; 15 dakika işlem yapılmayan oturum sıfırlanır.

**Veri kaynağı:** [Credit Card Transactions Fraud Detection](https://www.kaggle.com/datasets/kartik2112/fraud-detection)
(Kaggle, Kartik Shenoy, **CC0: Public Domain**). Veri, Brandon Harris'in
[Sparkov Data Generation](https://github.com/namebrandon/Sparkov_Data_Generation)
simülatörüyle (**MIT**) üretilmiştir.

**Lisans:** MIT, © 2026 Tolga Arslan.

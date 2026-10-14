"""Türkçe sayı biçimi (açıklamalar ve panel ortak kullanır; ağır bağımlılığı yoktur)."""


def tr_num(x: float, decimals: int = 0) -> str:
    """Türkçe sayı biçimi: binlik ayırıcı nokta, ondalık virgül (1.940 · 5,2)."""
    s = f"{x:,.{decimals}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


# 3. tekil iyelik eki, sayının okunuşundaki son kelimeye göre (dört → dördü, altı → altısı)
_EK_BIRLER = {1: "i", 2: "si", 3: "ü", 4: "ü", 5: "i", 6: "sı", 7: "si", 8: "i", 9: "u"}
_EK_ONLAR = {1: "u", 2: "si", 3: "u", 4: "ı", 5: "si", 6: "ı", 7: "i", 8: "i", 9: "ı"}


def tr_ek(sayi: str) -> str:
    """Türkçe yazılmış bir sayının iyelik eki ("84" → "ü", "0,5" → "i", "60" → "ı").

    Ondalıklı sayıda son okunan kelime virgülden sonraki kısımdır. Yüz ve üstü için
    yalnızca son iki basamak ve "yüz"/"bin" yeterlidir (yüzde değerleri için tasarlandı).
    """
    tam, _, kesir = sayi.replace(".", "").partition(",")
    n = int(kesir or tam)
    if n % 10:
        return _EK_BIRLER[n % 10]
    if n % 100:
        return _EK_ONLAR[n % 100 // 10]
    if n == 0:
        return "ı"
    return "ü" if n % 1000 else "i"  # yüz → yüzü, bin → bini

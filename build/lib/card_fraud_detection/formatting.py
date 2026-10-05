"""Türkçe sayı biçimi (açıklamalar ve panel ortak kullanır; ağır bağımlılığı yoktur)."""


def tr_num(x: float, decimals: int = 0) -> str:
    """Türkçe sayı biçimi: binlik ayırıcı nokta, ondalık virgül (1.940 · 5,2)."""
    s = f"{x:,.{decimals}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")

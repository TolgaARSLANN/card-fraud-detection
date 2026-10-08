"""glibc bellek havuzu (arena) sınırı: `MALLOC_ARENA_MAX` ortam değişkeninin koddaki karşılığı.

Streamlit her oturumun betiğini ayrı bir iş parçacığında çalıştırır; glibc her iş parçacığı
için ayrı bir bellek havuzu açar ve boşalan belleği sisteme geri vermez. Ölçümde bellek oturum
ve işlemle birlikte artıyordu; 2 havuzla sabit kaldı (reports/space_olcum.md). Docker'da ortam
değişkeniyle ayarlanır; ortam değişkeninin süreç başlamadan verilemediği yerlerde (Streamlit
Community Cloud) bu fonksiyon, oturum iş parçacıkları açılmadan önce çağrılır.
"""

from __future__ import annotations

import ctypes
import ctypes.util

M_ARENA_MAX = -8          # glibc malloc.h


def limit_malloc_arenas(n: int = 2) -> bool:
    """Havuz sayısını sınırlar. glibc yoksa (Windows, macOS, musl) hiçbir şey yapmaz.
    Dönen: ayar uygulandı mı."""
    name = ctypes.util.find_library("c")
    if not name:
        return False
    try:
        libc = ctypes.CDLL(name)
        return bool(libc.mallopt(M_ARENA_MAX, n))
    except (OSError, AttributeError):
        return False

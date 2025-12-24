"""
Core Enums Modülü

Bu modül, sistemde kullanılan enum'ları içerir:
- TaskType: Görev tipi (CPU_BOUND veya IO_BOUND)
- TaskStatus: Görev durumu (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
"""

from enum import Enum, IntEnum


class TaskType(Enum):
    """
    Görev Tipi
    
    Görevlerin CPU-bound veya IO-bound olduğunu belirtir.
    Bu bilgi, görevin hangi worker pool'a gönderileceğini belirler.
    
    - CPU_BOUND: CPU yoğun görevler (hesaplama, işleme)
    - IO_BOUND: IO yoğun görevler (dosya, ağ, veritabanı)
    """
    CPU_BOUND = "cpu_bound"  # CPU yoğun görevler
    IO_BOUND = "io_bound"    # IO yoğun görevler


class TaskStatus(Enum):
    """
    Görev Durumu
    
    Görevlerin yaşam döngüsündeki durumlarını belirtir.
    
    - PENDING: Görev gönderildi, henüz işlenmedi
    - RUNNING: Görev çalışıyor
    - COMPLETED: Görev başarıyla tamamlandı
    - FAILED: Görev başarısız oldu
    - CANCELLED: Görev iptal edildi
    """
    PENDING = "pending"      # Beklemede
    RUNNING = "running"       # Çalışıyor
    COMPLETED = "completed"  # Tamamlandı
    FAILED = "failed"        # Başarısız
    CANCELLED = "cancelled"  # İptal edildi


class ProcessMetric(IntEnum):
    CPU = 0
    MEM = 1
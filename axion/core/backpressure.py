
import psutil
import time
from enum import Enum

class SystemHealth(Enum):
    HEALTHY = "healthy"     # Her şey yolunda
    WARNING = "warning"     # Yük artıyor, dikkat
    CRITICAL = "critical"   # Sistem yanıyor, görev reddet

class BackpressureController:
    """
    Adaptive Backpressure Controller (PID Mantığı ile)
    
    Sistem kaynaklarını izler ve yeni görev kabul edilip edilmeyeceğine karar verir.
    """
    
    def __init__(self, cpu_threshold=100.0, memory_threshold=100.0):
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        self._last_check = 0
        self._cached_health = SystemHealth.HEALTHY
        
    def check_health(self) -> SystemHealth:
        """Sistem sağlığını kontrol et (Throttled)"""
        now = time.time()
        if now - self._last_check < 1.0:  # Saniyede en fazla 1 kere kontrol et
            return self._cached_health
            
        self._last_check = now
        
        # CPU Yükü (Tüm çekirdekler)
        cpu_percent = psutil.cpu_percent(interval=None)
        
        # RAM Yükü
        memory = psutil.virtual_memory()
        mem_percent = memory.percent
        
        # Karar Mekanizması
        if cpu_percent > self.cpu_threshold or mem_percent > self.memory_threshold:
            self._cached_health = SystemHealth.CRITICAL
        elif cpu_percent > (self.cpu_threshold * 0.8):
            self._cached_health = SystemHealth.WARNING
        else:
            self._cached_health = SystemHealth.HEALTHY
            
        return self._cached_health

    def should_accept_task(self) -> bool:
        """Görev kabul edelim mi?"""
        health = self.check_health()
        return health != SystemHealth.CRITICAL

"""
Engine Yapılandırması

Bu modül, Engine'in tüm yapılandırma ayarlarını içerir.
Tek bir config sınıfı ile tüm ayarlar yönetilir.

Kullanım:
    config = EngineConfig(
        input_queue_size=2000,
        cpu_bound_count=2,
        io_bound_count=4
    )
    engine = Engine(config)
"""

from dataclasses import dataclass
from typing import Optional
import multiprocessing


@dataclass
class EngineConfig:
    """
    Engine yapılandırması - Tüm ayarlar burada
    
    Bu sınıf, Engine'in tüm yapılandırma ayarlarını içerir:
    - Queue ayarları: Input/Output queue boyutları
    - Worker ayarları: CPU/IO-bound worker sayıları ve limitler
    - Genel ayarlar: Log level, timeout değerleri
    
    Varsayılan değerler makul seçilmiştir, çoğu durumda değiştirmeye gerek yoktur.
    """
    # Queue ayarları
    input_queue_size: int = 1000
    output_queue_size: int = 10000
    
    # Worker ayarları
    cpu_bound_count: int = 1
    io_bound_count: Optional[int] = None  # None = otomatik (CPU - 1)
    cpu_bound_task_limit: int = 1
    io_bound_task_limit: int = 20
    
    # Genel ayarlar
    log_level: str = "INFO"
    queue_poll_timeout: float = 1.0
    
    def __post_init__(self):
        """Değerleri doğrula ve otomatik ayarla"""
        # IO-bound count otomatik hesaplama
        if self.io_bound_count is None:
            cpu_count = multiprocessing.cpu_count()
            self.io_bound_count = max(1, cpu_count - 1)
        
        # Validasyon
        if self.input_queue_size < 1:
            raise ValueError("input_queue_size en az 1 olmalı")
        if self.output_queue_size < 1:
            raise ValueError("output_queue_size en az 1 olmalı")
        if self.cpu_bound_count < 1:
            raise ValueError("cpu_bound_count en az 1 olmalı")
        if self.io_bound_count < 1:
            raise ValueError("io_bound_count en az 1 olmalı")
        if self.cpu_bound_task_limit < 1:
            raise ValueError("cpu_bound_task_limit en az 1 olmalı")
        if self.io_bound_task_limit < 1:
            raise ValueError("io_bound_task_limit en az 1 olmalı")
        
        # Log level kontrolü
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_levels:
            raise ValueError(f"Geçersiz log_level: {self.log_level}")
        
        self.log_level = self.log_level.upper()


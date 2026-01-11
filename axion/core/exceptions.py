"""
Exception Hiyerarşisi

Bu modül, sistemde kullanılan özel exception'ları içerir.
Tüm exception'lar EngineError'dan türer.

Hiyerarşi:
    EngineError (base)
    ├── TaskError (görev hataları)
    ├── QueueError (queue hataları)
    ├── ConfigError (yapılandırma hataları)
    ├── ExecutorError (executor hataları)
    └── WorkerError (worker hataları)
"""

from typing import Optional


class EngineError(Exception):
    """
    Engine Hataları - Base exception
    
    Tüm sistem hataları bu sınıftan türer.
    Hata mesajı ve kod içerir.
    """
    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.code = code  # Hata kodu (örn: "ENG001")
    
    def __str__(self):
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message


class TaskError(EngineError):
    """
    Görev Hataları
    
    Görev gönderme veya işleme sırasında oluşan hatalar.
    Task ID bilgisi içerir.
    """
    def __init__(self, message: str, code: Optional[str] = None, task_id: Optional[str] = None):
        super().__init__(message, code)
        self.task_id = task_id  # Hangi görevde hata oldu


class QueueError(EngineError):
    """
    Queue Hataları
    
    Queue işlemleri sırasında oluşan hatalar.
    """
    pass


class ConfigError(EngineError):
    """
    Yapılandırma Hataları
    
    Config oluşturma veya doğrulama sırasında oluşan hatalar.
    """
    pass


class ExecutorError(EngineError):
    """
    Executor Hataları
    
    Script çalıştırma sırasında oluşan hatalar.
    """
    pass


class WorkerError(EngineError):
    """
    Worker Hataları
    
    Worker process veya thread işlemleri sırasında oluşan hatalar.
    """
    pass


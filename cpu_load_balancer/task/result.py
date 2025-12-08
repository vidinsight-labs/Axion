"""
Result (Sonuç) Sınıfı

Bu modül, görevlerin çalıştırılması sonucu oluşan sonuçları içerir.
Sonuçlar başarılı veya başarısız olabilir.

Kullanım:
    result = Result.success(task_id, data)
    # veya
    result = Result.failed(task_id, error)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from ..core.enums import TaskType, TaskStatus


@dataclass
class Result:
    """
    Görev sonucu
    
    Bir sonuç şunları içerir:
    - Task ID: Hangi görevin sonucu olduğu
    - Status: COMPLETED veya FAILED
    - Data: Başarılı durumda sonuç verisi
    - Error: Başarısız durumda hata mesajı
    - Zaman bilgileri: Başlangıç ve bitiş zamanı
    
    Sonuçlar queue'ya gönderilmeden önce dict'e dönüştürülür.
    """
    task_id: str 
    status: TaskStatus
    data: Any = None
    error: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_success(self) -> bool:
        """
        Başarılı mı?
        
        Returns:
            bool: True ise başarılı, False ise başarısız
        """
        return self.status == TaskStatus.COMPLETED

    @property
    def duration(self) -> Optional[float]:
        """
        Çalışma süresi (saniye)
        
        Returns:
            float: Başlangıç ve bitiş zamanı varsa süre, yoksa None
        """
        if self.started_at and self.completed_at:
            # Timezone-aware datetime'ları karşılaştırmak için normalize et
            from datetime import timezone
            started = self.started_at
            completed = self.completed_at
            
            # Eğer biri timezone-aware diğeri değilse, normalize et
            if started.tzinfo is None and completed.tzinfo is not None:
                started = started.replace(tzinfo=timezone.utc)
            elif started.tzinfo is not None and completed.tzinfo is None:
                completed = completed.replace(tzinfo=timezone.utc)
            
            return (completed - started).total_seconds()
        return None
    
    @classmethod
    def success(cls, task_id: str, data: Any, started_at: Optional[datetime] = None) -> "Result":
        """
        Başarılı sonuç oluşturur
        
        Args:
            task_id: Görev ID'si
            data: Sonuç verisi
            started_at: Başlangıç zamanı (opsiyonel)
        
        Returns:
            Result: Başarılı sonuç objesi
        """
        return cls(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            data=data,
            started_at=started_at,
        )
    
    @classmethod
    def failed(cls, task_id: str, error: str, started_at: Optional[datetime] = None) -> "Result":
        """
        Başarısız sonuç oluşturur
        
        Args:
            task_id: Görev ID'si
            error: Hata mesajı
            started_at: Başlangıç zamanı (opsiyonel)
        
        Returns:
            Result: Başarısız sonuç objesi
        """
        return cls(
            task_id=task_id,
            status=TaskStatus.FAILED,
            error=error,
            started_at=started_at,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Dict'e dönüştür (queue için)"""
        return {
            "task_id": self.task_id,
            "status": "SUCCESS" if self.is_success else "FAILED",
            "data": self.data,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Result":
        """Dict'ten oluştur"""
        status_str = data.get("status", "FAILED")
        status = TaskStatus.COMPLETED if status_str == "SUCCESS" else TaskStatus.FAILED
        
        started_at = None
        completed_at = None
        if data.get("started_at"):
            started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            completed_at = datetime.fromisoformat(data["completed_at"])
        
        return cls(
            task_id=data.get("task_id", "unknown"),
            status=status,
            data=data.get("data"),
            error=data.get("error"),
            started_at=started_at,
            completed_at=completed_at
        )
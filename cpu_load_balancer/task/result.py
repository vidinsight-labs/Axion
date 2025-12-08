from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from ..core.enums import TaskType, TaskStatus


@dataclass
class Result:
    """
    Görev sonucu - basitleştirilmiş
    """
    task_id: str 
    status: TaskStatus
    data: Any = None
    error: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: datetime = field(default_factory=datetime.now(timezone.utc))

    @property
    def duration(self) -> Optional[float]:
        """Çalışma süresi (saniye)"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @classmethod
    def success(cls, task_id: str, data: Any, started_at: Optional[datetime] = None) -> "Result":
        """Başarılı sonuç oluştur"""
        return cls(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            data=data,
            started_at=started_at,
        )
    
    @classmethod
    def failed(cls, task_id: str, error: str, started_at: Optional[datetime] = None) -> "Result":
        """Başarısız sonuç oluştur"""
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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from ..core.enums import TaskType, TaskStatus


@dataclass
class Task:
    """
    Görev tanımı - basitleştirilmiş
    """
    # Base fields
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now(timezone.utc))
    # Task type and status
    task_type: TaskType = TaskType.CPU_BOUND
    status: TaskStatus = TaskStatus.PENDING
    # Dynamic parameters
    params: Dict[str, Any] = field(default_factory=dict)
    script_path: str = ""
    max_retries: int = 3
    retry_count: int = 0

    @classmethod
    def create(
        cls,
        script_path: str,
        params: Optional[Dict[str, Any]] = None,
        task_type: TaskType = TaskType.IO_BOUND,
        max_retries: int = 3
    ) -> "Task":
        """Factory metodu - görev oluştur"""
        return cls(
            script_path=script_path,
            params=params or {},
            task_type=task_type,
            max_retries=max_retries
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Dict'e dönüştür (queue için)"""
        return {
            "task_id": self.id,
            "script_path": self.script_path,
            "params": self.params,
            "task_type": self.task_type.value,
            "max_retries": self.max_retries,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Dict'ten oluştur"""
        task_type = TaskType(data.get("task_type", "io_bound"))
        return cls(
            id=data.get("task_id", str(uuid.uuid4())),
            script_path=data.get("script_path", ""),
            params=data.get("params", {}),
            task_type=task_type,
            max_retries=data.get("max_retries", 3)
        )
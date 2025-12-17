"""
Task (Görev) Sınıfı

Bu modül, çalıştırılacak görevlerin tanımını içerir.
Görevler script path, parametreler ve tip bilgisi içerir.

Kullanım:
    task = Task.create(
        script_path="my_script.py",
        params={"value": 42},
        task_type=TaskType.IO_BOUND
    )
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from typing import Any, Dict, Optional, List

from ..core.enums import TaskType, TaskStatus


@dataclass
class Task:
    """
    Görev tanımı
    
    Bir görev şunları içerir:
    - Script path: Çalıştırılacak Python script'inin yolu
    - Params: Script'e geçirilecek parametreler
    - Task type: CPU_BOUND veya IO_BOUND
    - Status: Görev durumu (PENDING, RUNNING, COMPLETED, FAILED)
    - Retry bilgileri: Maksimum deneme sayısı ve mevcut deneme
    
    Görevler queue'ya gönderilmeden önce dict'e dönüştürülür.
    """
    # Base fields
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Task type and status
    task_type: TaskType = TaskType.CPU_BOUND
    status: TaskStatus = TaskStatus.PENDING
    # Dynamic parameters
    params: Dict[str, Any] = field(default_factory=dict)
    script_path: str = ""
    max_retries: int = 3
    retry_count: int = 0
    # Workflow dependencies
    dependencies: List[str] = field(default_factory=list)  # Beklenen task ID'leri

    @classmethod
    def create(
        cls,
        script_path: str,
        params: Optional[Dict[str, Any]] = None,
        task_type: TaskType = TaskType.IO_BOUND,
        max_retries: int = 3,
        dependencies: Optional[List[str]] = None
    ) -> "Task":
        """
        Factory metodu - görev oluşturur
        
        Args:
            script_path: Çalıştırılacak Python script'inin yolu
            params: Script'e geçirilecek parametreler (dict)
            task_type: Görev tipi (CPU_BOUND veya IO_BOUND)
            max_retries: Maksimum deneme sayısı
        
        Returns:
            Task: Yeni görev objesi
        """
        return cls(
            script_path=script_path,
            params=params or {},
            task_type=task_type,
            max_retries=max_retries,
            dependencies=dependencies or []
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Dict'e dönüştürür (queue için)
        
        Multiprocessing.Queue pickle kullanır, bu yüzden dict formatı gerekir.
        
        Returns:
            Dict: Queue'ya gönderilebilir format
        """
        return {
            "task_id": self.id,
            "script_path": self.script_path,
            "params": self.params,
            "task_type": self.task_type.value,
            "max_retries": self.max_retries,
            "dependencies": self.dependencies,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """
        Dict'ten Task objesi oluşturur
        
        Queue'dan gelen dict'ten Task objesi oluşturur.
        
        Args:
            data: Queue'dan gelen dict
        
        Returns:
            Task: Yeni Task objesi
        """
        task_type = TaskType(data.get("task_type", "io_bound"))
        return cls(
            id=data.get("task_id", str(uuid.uuid4())),
            script_path=data.get("script_path", ""),
            params=data.get("params", {}),
            task_type=task_type,
            max_retries=data.get("max_retries", 3),
            dependencies=data.get("dependencies", [])
        )
"""
Python Executor Modülü

Bu modül, Python script'lerini dinamik olarak yükler ve çalıştırır.
Script'lerde main(params, context) fonksiyonu aranır.

Kullanım:
    executor = PythonExecutor()
    result = executor.execute(task, context)
"""

import importlib.util
import sys
from typing import Any, Optional
from datetime import datetime

from ..task.task import Task
from ..task.result import Result
from ..core.enums import TaskStatus


class ExecutionContext:
    """
    Execution Context - Script'e geçirilecek bilgiler
    
    Script'ler bu context'i kullanarak görev ve worker bilgisine erişebilir.
    """
    def __init__(self, task_id: str, worker_id: str):
        self.task_id = task_id    # Görev ID'si
        self.worker_id = worker_id  # Worker ID'si (örn: "io-0")


class PythonExecutor:
    """
    Python Executor - Python script çalıştırıcı
    
    Python script'lerini dinamik olarak yükler ve çalıştırır.
    
    Özellikler:
    - Module cache: Script'leri cache'ler (performans için)
    - main() fonksiyonu: Script'te main(params, context) fonksiyonu aranır
    - Hata yönetimi: Hata durumunda failed result döndürür
    """
    
    def __init__(self):
        self._module_cache = {}  # Basit cache
    
    def execute(self, task: Task, context: ExecutionContext) -> Result:
        """
        Script'i çalıştırır
        
        Script'i yükler, main() fonksiyonunu bulur ve çalıştırır.
        Başarılı veya başarısız sonuç döndürür.
        
        Args:
            task: Çalıştırılacak görev
            context: Execution context (task_id, worker_id)
        
        Returns:
            Result: Başarılı veya başarısız sonuç
        """
        from datetime import timezone
        started_at = datetime.now(timezone.utc)  # Timezone-aware datetime
        
        try:
            # Script'i yükle (cache'den veya dosyadan)
            module = self._load_module(task.script_path)
            
            # main() fonksiyonunu bul
            if not hasattr(module, 'main'):
                raise ValueError(f"Script'te 'main' fonksiyonu bulunamadı: {task.script_path}")
            
            main_func = module.main
            
            # Script'i çalıştır: main(params, context)
            data = main_func(task.params, context)
            
            # Başarılı sonuç döndür
            return Result.success(
                task_id=task.id,
                data=data,
                started_at=started_at
            )
        
        except Exception as e:
            # Hata durumunda başarısız sonuç döndür
            return Result.failed(
                task_id=task.id,
                error=str(e),
                started_at=started_at
            )
    
    def _load_module(self, script_path: str):
        """
        Script'i yükler (cache ile)
        
        Script daha önce yüklenmişse cache'den döner.
        Yoksa dosyadan yükler ve cache'e ekler.
        
        Args:
            script_path: Script dosya yolu
        
        Returns:
            Module: Yüklenen modül
        
        Raises:
            ValueError: Script yüklenemezse
        """
        # Cache'de varsa direkt döndür
        if script_path in self._module_cache:
            return self._module_cache[script_path]
        
        # Script'i dosyadan yükle
        spec = importlib.util.spec_from_file_location("task_module", script_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Script yüklenemedi: {script_path}")
        
        # Modülü oluştur ve çalıştır
        module = importlib.util.module_from_spec(spec)
        sys.modules["task_module"] = module
        spec.loader.exec_module(module)
        
        # Cache'e ekle (bir sonraki kullanım için)
        self._module_cache[script_path] = module
        return module
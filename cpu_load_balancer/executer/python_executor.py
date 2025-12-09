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
import os
import logging
from typing import Any, Optional, Tuple
from datetime import datetime
from types import ModuleType

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
    - Cache invalidation: File modification time kontrolü ile otomatik reload
    - main() fonksiyonu: Script'te main(params, context) fonksiyonu aranır
    - Hata yönetimi: Hata durumunda failed result döndürür
    """

    def __init__(self):
        # Module cache: path → (module, mtime)
        self._module_cache: dict[str, Tuple[ModuleType, float]] = {}
        self._logger = logging.getLogger("python_executor")
    
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
    
    def _load_module(self, script_path: str) -> ModuleType:
        """
        Script'i yükler (cache ile + modification time check)

        Script daha önce yüklenmişse ve değişmemişse cache'den döner.
        Script değişmişse yeniden yükler.

        Args:
            script_path: Script dosya yolu

        Returns:
            ModuleType: Yüklenen modül

        Raises:
            ValueError: Script yüklenemezse veya bulunamazsa
        """
        # 1. Dosyanın mevcut modification time'ını al
        try:
            current_mtime = os.path.getmtime(script_path)
        except OSError as e:
            raise ValueError(f"Script bulunamadı: {script_path}") from e

        # 2. Cache'de var mı kontrol et
        if script_path in self._module_cache:
            cached_module, cached_mtime = self._module_cache[script_path]

            # 3. Modification time aynı mı?
            if cached_mtime == current_mtime:
                # ✅ Cache hit! Dosya değişmemiş
                return cached_module
            else:
                # ⚠️ Dosya değişmiş! Yeniden yükle
                self._logger.info(
                    f"Script değişti, yeniden yükleniyor: {script_path} "
                    f"(old mtime: {cached_mtime}, new: {current_mtime})"
                )

        # 4. Script'i dosyadan yükle
        module = self._load_module_fresh(script_path)

        # 5. Cache'e ekle (mtime ile birlikte)
        self._module_cache[script_path] = (module, current_mtime)

        return module

    def _load_module_fresh(self, script_path: str) -> ModuleType:
        """
        Modülü dosyadan yükle (cache bypass)

        Args:
            script_path: Script dosya yolu

        Returns:
            ModuleType: Yüklenen modül

        Raises:
            ValueError: Script yüklenemezse
        """
        # Script'i dosyadan yükle
        spec = importlib.util.spec_from_file_location("task_module", script_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Script yüklenemedi: {script_path}")

        # Modülü oluştur ve çalıştır
        module = importlib.util.module_from_spec(spec)
        sys.modules["task_module"] = module
        spec.loader.exec_module(module)

        return module

    def clear_cache(self, script_path: Optional[str] = None):
        """
        Cache'i temizle

        Args:
            script_path: Belirli bir script için, None ise tüm cache
        """
        if script_path:
            if script_path in self._module_cache:
                self._module_cache.pop(script_path)
                self._logger.info(f"Cache temizlendi: {script_path}")
        else:
            self._module_cache.clear()
            self._logger.info("Tüm module cache temizlendi")
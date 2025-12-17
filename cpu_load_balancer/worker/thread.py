"""
Thread Pool Modülü

Bu modül, bir worker process içinde birden fazla thread'i yönetir.
Her thread görev alır, executor ile çalıştırır ve sonucu queue'ya gönderir.

Kullanım:
    pool = ThreadPool(max_threads=20, output_queue=queue)
    pool.start()
    pool.submit_task(task_dict)
    pool.shutdown()
"""

import threading
from typing import Any, Optional, Callable, Dict
from queue import Queue
from threading import Event

from ..task.task import Task
from ..task.result import Result
from ..executer.python_executor import PythonExecutor, ExecutionContext


class ThreadPool:
    """
    Thread Pool - Thread yönetimi
    
    Bir worker process içinde birden fazla thread çalıştırır.
    Her thread görev alır, executor ile çalıştırır ve sonucu gönderir.
    
    Özellikler:
    - Thread yönetimi: Belirli sayıda thread oluşturur
    - Görev dağıtımı: Thread'ler queue'dan görev alır
    - Executor entegrasyonu: PythonExecutor ile script çalıştırır
    """
    
    def __init__(
        self,
        max_threads: int,
        output_queue: Any,
        executor_func: Optional[Callable] = None,
        worker_id: str = "unknown",
        active_task_count: Any = None  # Shared counter
    ):
        self._max_threads = max_threads
        self._output_queue = output_queue
        self._executor_func = executor_func or self._default_executor
        self._worker_id = worker_id
        self._active_task_count = active_task_count
        
        self._task_queue: Queue = Queue()
        self._threads: list = []
        self._shutdown_event = Event()
        self._active_count = 0
        self._lock = threading.Lock()
    
    def start(self):
        """Thread pool'u başlat"""
        for i in range(self._max_threads):
            thread = threading.Thread(
                target=self._worker_loop,
                daemon=True
            )
            thread.start()
            self._threads.append(thread)
    
    def submit_task(self, task_dict: Dict[str, Any]):
        """Görev gönder"""
        self._task_queue.put(task_dict)
    
    def shutdown(self):
        """Thread pool'u kapat"""
        self._shutdown_event.set()
        # Queue'ya None ekle ki thread'ler çıksın
        for _ in self._threads:
            self._task_queue.put(None)
        
        for thread in self._threads:
            thread.join(timeout=2.0)
    
    def _worker_loop(self):
        """
        Worker thread loop - Her thread bu döngüde çalışır
        
        Thread sürekli queue'dan görev alır, çalıştırır ve sonucu gönderir.
        """
        while not self._shutdown_event.is_set():
            try:
                # Queue'dan görev al (timeout ile)
                task_dict = self._task_queue.get(timeout=0.1)
                
                if task_dict is None:  # Shutdown signal
                    break
                
                # Aktif thread sayısını artır
                with self._lock:
                    self._active_count += 1
                
                try:
                    # Dict'ten Task objesi oluştur
                    task = Task.from_dict(task_dict)
                    
                    # Execution context oluştur (script'e geçirilecek)
                    context = ExecutionContext(
                        task_id=task.id,
                        worker_id=self._worker_id
                    )
                    
                    # Executor ile görevi çalıştır
                    result = self._executor_func(task, context)
                    
                    # Sonucu output queue'ya gönder
                    if result:
                        self._output_queue.put(result.to_dict())
                
                except Exception as e:
                    # Hata durumunda failed result oluştur
                    # Görev çalıştırılamadı, hata mesajı ile sonuç oluştur
                    task_id = task_dict.get("task_id", "unknown")
                    result = Result.failed(
                        task_id=task_id,
                        error=str(e)
                    )
                    self._output_queue.put(result.to_dict())
                
                finally:
                    # Aktif thread sayısını azalt
                    with self._lock:
                        self._active_count -= 1
                    
                    # Shared counter'ı azalt (varsa)
                    if self._active_task_count is not None:
                        with self._active_task_count.get_lock():
                            self._active_task_count.value -= 1
                
            except:
                # Queue timeout veya başka hata, devam et
                pass
    
    def _default_executor(self, task: Task, context: ExecutionContext) -> Result:
        """Varsayılan executor (PythonExecutor)"""
        executor = PythonExecutor()
        return executor.execute(task, context)
    
    def active_count(self) -> int:
        """Aktif thread sayısı"""
        with self._lock:
            return self._active_count


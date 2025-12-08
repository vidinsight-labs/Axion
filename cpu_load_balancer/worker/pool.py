"""
Process Pool Modülü

Bu modül, CPU-bound ve IO-bound worker process'lerini yönetir.
Load balancing yaparak görevleri en az yüklü worker'a dağıtır.

Kullanım:
    pool = ProcessPool(output_queue, cpu_bound_count=1, io_bound_count=4)
    pool.start()
    pool.submit_task(task, TaskType.IO_BOUND)
    pool.shutdown()
"""

import multiprocessing
from typing import List, Optional, Callable, Any
from threading import Lock, Thread, Event
import time

from ..core.enums import TaskType
from ..status import ComponentStatus
from .process import WorkerProcess


class ProcessPool:
    """
    Process Pool - Worker process yönetimi
    
    CPU-bound ve IO-bound worker'ları yönetir ve görevleri dağıtır.
    
    Özellikler:
    - Load balancing: En az yüklü worker'a görev gönderir
    - CPU/IO ayrımı: Görev tipine göre uygun worker seçer
    - Status takibi: Worker sayıları ve aktif thread sayıları
    """
    
    def __init__(
        self,
        output_queue: Any,  # OutputQueue
        cpu_bound_count: int = 1,
        io_bound_count: Optional[int] = None,
        cpu_task_limit: int = 1,
        io_task_limit: int = 20,
        executor_func: Optional[Callable] = None
    ):
        if io_bound_count is None:
            io_bound_count = max(1, multiprocessing.cpu_count() - 1)
        
        self._output_queue = output_queue
        self._cpu_bound_count = cpu_bound_count
        self._io_bound_count = io_bound_count
        self._cpu_task_limit = cpu_task_limit
        self._io_task_limit = io_task_limit
        self._executor_func = executor_func
        
        self._cpu_workers: List[WorkerProcess] = []
        self._io_workers: List[WorkerProcess] = []
        
        self._started = False
        self._shutdown_event = Event()
        self._lock = Lock()
    
    def start(self) -> bool:
        """Pool'u başlat"""
        if self._started:
            return True
        
        # CPU-bound worker'ları oluştur
        for i in range(self._cpu_bound_count):
            worker = WorkerProcess(
                worker_id=f"cpu-{i}",
                task_type=TaskType.CPU_BOUND,
                max_threads=self._cpu_task_limit,
                output_queue=self._output_queue,
                executor_func=None  # Process içinde oluşturulacak
            )
            worker.start()
            self._cpu_workers.append(worker)
        
        # IO-bound worker'ları oluştur
        for i in range(self._io_bound_count):
            worker = WorkerProcess(
                worker_id=f"io-{i}",
                task_type=TaskType.IO_BOUND,
                max_threads=self._io_task_limit,
                output_queue=self._output_queue,
                executor_func=None  # Process içinde oluşturulacak
            )
            worker.start()
            self._io_workers.append(worker)
        
        self._started = True
        return True
    
    def submit_task(self, task: Any, task_type: TaskType) -> bool:
        """
        Görev gönderir (load balancing ile)
        
        Görev tipine göre uygun worker listesini seçer ve
        en az yüklü worker'a gönderir.
        
        Args:
            task: Gönderilecek görev
            task_type: Görev tipi (CPU_BOUND veya IO_BOUND)
        
        Returns:
            bool: True ise başarılı, False ise başarısız
        """
        if not self._started:
            return False
        
        # Uygun worker listesini seç: CPU veya IO
        if task_type == TaskType.CPU_BOUND:
            workers = self._cpu_workers
        else:
            workers = self._io_workers
        
        if not workers:
            return False  # Worker yok
        
        # Load balancing: En az yüklü worker'ı bul
        # active_thread_count() ile worker'ın aktif thread sayısını alır
        best_worker = min(workers, key=lambda w: w.active_thread_count())
        
        # Seçilen worker'a görev gönder
        return best_worker.submit_task(task)
    
    def shutdown(self):
        """Pool'u kapat"""
        self._shutdown_event.set()
        
        for worker in self._cpu_workers + self._io_workers:
            worker.shutdown()
        
        self._started = False
    
    def get_status(self) -> ComponentStatus:
        """Pool durumu"""
        cpu_active = sum(w.active_thread_count() for w in self._cpu_workers)
        io_active = sum(w.active_thread_count() for w in self._io_workers)
        
        metrics = {
            "cpu_bound_workers": len(self._cpu_workers),
            "io_bound_workers": len(self._io_workers),
            "total_workers": len(self._cpu_workers) + len(self._io_workers),
            "cpu_active_threads": cpu_active,
            "io_active_threads": io_active,
            "total_active_threads": cpu_active + io_active,
        }
        
        health = "healthy" if self._started else "unhealthy"
        
        return ComponentStatus(
            name="process_pool",
            health=health,
            metrics=metrics
        )


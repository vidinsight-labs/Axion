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
        
        # Sharded Queues (Her worker için ayrı kuyruk)
        self._cpu_queues = []
        self._io_queues = []
        
        self._cpu_workers: List[WorkerProcess] = []
        self._io_workers: List[WorkerProcess] = []
        
        self._started = False
        self._shutdown_event = Event()
        self._lock = Lock()
        
        # Worker ID counter (Unique ID'ler için)
        self._worker_counter = 0
    
    def start(self) -> bool:
        """Pool'u başlat"""
        if self._started:
            return True
        
        # CPU-bound worker'ları oluştur
        # Kuyrukları oluştur
        self._cpu_queues = [multiprocessing.Queue() for _ in range(self._cpu_bound_count)]
        
        # CPU affinity için mevcut çekirdekleri al
        try:
            available_cpus = list(range(multiprocessing.cpu_count()))
        except:
            available_cpus = []
            
        for i in range(self._cpu_bound_count):
            # Worker'a CPU ata (Round-robin)
            cpu_id = available_cpus[i % len(available_cpus)] if available_cpus else None
            
            worker_id = f"cpu-{self._worker_counter}"
            self._worker_counter += 1
            
            worker = WorkerProcess(
                worker_id=worker_id,
                task_type=TaskType.CPU_BOUND,
                max_threads=self._cpu_task_limit,
                output_queue=self._output_queue,
                executor_func=None,
                cpu_id=cpu_id,
                nice_level=0,
                # Work Stealing Parametreleri
                my_queue=self._cpu_queues[i],
                all_queues=self._cpu_queues # Tüm kuyrukları bilmeli ki çalabilsin
            )
            worker.start()
            self._cpu_workers.append(worker)
        
        # IO-bound worker'ları oluştur
        self._io_queues = [multiprocessing.Queue() for _ in range(self._io_bound_count)]
        
        for i in range(self._io_bound_count):
            cpu_id = available_cpus[(i + self._cpu_bound_count) % len(available_cpus)] if available_cpus else None
            
            worker_id = f"io-{self._worker_counter}"
            self._worker_counter += 1
            
            worker = WorkerProcess(
                worker_id=worker_id,
                task_type=TaskType.IO_BOUND,
                max_threads=self._io_task_limit,
                output_queue=self._output_queue,
                executor_func=None,
                cpu_id=cpu_id,
                nice_level=5,
                my_queue=self._io_queues[i],
                all_queues=self._io_queues
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
        # best_worker = min(workers, key=lambda w: w.active_thread_count())
        
        # Work Stealing Modunda:
        # Görevi rastgele veya Round-Robin bir kuyruğa atarız.
        # Worker'lar zaten boş kalınca diğerlerinden çalacak.
        # Basitlik için: En az işi olan worker'ın kuyruğuna atalım (Push-based balancing)
        
        best_worker_idx = 0
        min_load = float('inf')
        
        for i, worker in enumerate(workers):
            active_tasks, queue_size = worker.active_thread_count()
            load = active_tasks + queue_size
            if load < min_load:
                min_load = load
                best_worker_idx = i
                
        # Seçilen worker'ın kuyruğuna at
        if task_type == TaskType.CPU_BOUND:
            target_queue = self._cpu_queues[best_worker_idx]
        else:
            target_queue = self._io_queues[best_worker_idx]
            
        # Görevi kuyruğa at (Dict olarak)
        task_data = task.to_dict() if hasattr(task, 'to_dict') else task
        
        # WorkerProcess artık Pipe yerine Queue dinliyor.
        # Ancak WorkerProcess içinde "execute_task" komutu bekleyen bir yapı var.
        # O yapıyı değiştirmemiz lazım.
        # Şimdilik uyumluluk için:
        target_queue.put({
            "command": "execute_task",
            "task": task_data
        })
        return True
    
    def shutdown(self):
        """Pool'u kapat"""
        self._shutdown_event.set()
        
        # Tüm worker'ları kapat
        for worker in self._cpu_workers + self._io_workers:
            worker.shutdown()
        
        # Process'lerin kapanmasını bekle
        for worker in self._cpu_workers + self._io_workers:
            if worker._process and worker._process.is_alive():
                worker._process.join(timeout=5.0)
                # Hala çalışıyorsa terminate et
                if worker._process.is_alive():
                    worker._process.terminate()
                    worker._process.join(timeout=2.0)
                    if worker._process.is_alive():
                        worker._process.kill()
                        worker._process.join(timeout=1.0)
        
        self._started = False
    
    def wait_for_shutdown(self, timeout: float = 10.0):
        """Tüm process'lerin kapanmasını bekler"""
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            all_dead = True
            for worker in self._cpu_workers + self._io_workers:
                if worker._process and worker._process.is_alive():
                    all_dead = False
                    break
            
            if all_dead:
                return True
            
            time.sleep(0.1)
        
        return False
    
    def add_worker(self, task_type: TaskType) -> bool:
        """Yeni bir worker ekler (Scale Out)"""
        with self._lock:
            if not self._started:
                return False
                
            try:
                available_cpus = list(range(multiprocessing.cpu_count()))
            except:
                available_cpus = []
            
            worker_id = f"{'cpu' if task_type == TaskType.CPU_BOUND else 'io'}-{self._worker_counter}"
            self._worker_counter += 1
            
            # Yeni kuyruk oluştur
            new_queue = multiprocessing.Queue()
            
            if task_type == TaskType.CPU_BOUND:
                self._cpu_queues.append(new_queue)
                # Yeni worker için CPU seç (Round-robin)
                idx = len(self._cpu_workers)
                cpu_id = available_cpus[idx % len(available_cpus)] if available_cpus else None
                
                worker = WorkerProcess(
                    worker_id=worker_id,
                    task_type=TaskType.CPU_BOUND,
                    max_threads=self._cpu_task_limit,
                    output_queue=self._output_queue,
                    executor_func=None,
                    cpu_id=cpu_id,
                    nice_level=0,
                    my_queue=new_queue,
                    all_queues=self._cpu_queues
                )
                worker.start()
                self._cpu_workers.append(worker)
                self._cpu_bound_count += 1
                
            else:
                self._io_queues.append(new_queue)
                idx = len(self._io_workers)
                cpu_id = available_cpus[(idx + self._cpu_bound_count) % len(available_cpus)] if available_cpus else None
                
                worker = WorkerProcess(
                    worker_id=worker_id,
                    task_type=TaskType.IO_BOUND,
                    max_threads=self._io_task_limit,
                    output_queue=self._output_queue,
                    executor_func=None,
                    cpu_id=cpu_id,
                    nice_level=5,
                    my_queue=new_queue,
                    all_queues=self._io_queues
                )
                worker.start()
                self._io_workers.append(worker)
                self._io_bound_count += 1
                
            return True

    def remove_worker(self, task_type: TaskType) -> bool:
        """Bir worker'ı kapatır (Scale In)"""
        with self._lock:
            if not self._started:
                return False
                
            if task_type == TaskType.CPU_BOUND:
                if not self._cpu_workers:
                    return False
                # En son eklenen worker'ı kapat (LIFO)
                worker = self._cpu_workers.pop()
                queue = self._cpu_queues.pop()
                self._cpu_bound_count -= 1
            else:
                if not self._io_workers:
                    return False
                worker = self._io_workers.pop()
                queue = self._io_queues.pop()
                self._io_bound_count -= 1
                
            # Worker'a kapanma sinyali gönder
            try:
                queue.put({"command": "shutdown"})
            except:
                pass
                
            # Worker'ın bitmesini bekleme (arka planda kapansın)
            # worker.join() yaparsak burası bloklanır, gerek yok.
            
            return True

    def resize(self, task_type: TaskType, target_count: int):
        """Worker sayısını hedefe ayarlar"""
        current_count = len(self._cpu_workers) if task_type == TaskType.CPU_BOUND else len(self._io_workers)
        
        if target_count > current_count:
            # Büyüme
            for _ in range(target_count - current_count):
                self.add_worker(task_type)
        elif target_count < current_count:
            # Küçülme
            for _ in range(current_count - target_count):
                self.remove_worker(task_type)
                
    def get_worker_count(self, task_type: TaskType) -> int:
        if task_type == TaskType.CPU_BOUND:
            return len(self._cpu_workers)
        return len(self._io_workers)
        
    def get_status(self) -> ComponentStatus:
        """Pool durumu"""
        cpu_active = sum(w.active_thread_count()[0] for w in self._cpu_workers)
        io_active = sum(w.active_thread_count()[0] for w in self._io_workers)
        
        # Her worker'ın aktif görev sayısını topla
        cpu_worker_tasks = {}
        for i, worker in enumerate(self._cpu_workers):
            worker_id = worker._worker_id
            active_tasks, queue_size = worker.active_thread_count()
            try:
                queue_size = self._cpu_queues[i].qsize() if i < len(self._cpu_queues) else 0
            except:
                queue_size = 0  # qsize() bazı platformlarda çalışmayabilir
            thread_pool_queue_size = worker.thread_pool_queue_size()
            cpu_worker_tasks[worker_id] = {
                "active_tasks": active_tasks,
                "queue_size": queue_size,
                "thread_pool_queue_size": thread_pool_queue_size,
                "total_load": active_tasks + queue_size + thread_pool_queue_size
            }
        
        io_worker_tasks = {}
        for i, worker in enumerate(self._io_workers):
            worker_id = worker._worker_id
            active_tasks, queue_size = worker.active_thread_count()
            try:
                queue_size = self._io_queues[i].qsize() if i < len(self._io_queues) else 0
            except:
                queue_size = 0  # qsize() bazı platformlarda çalışmayabilir
            thread_pool_queue_size = worker.thread_pool_queue_size()
            io_worker_tasks[worker_id] = {
                "active_tasks": active_tasks,
                "queue_size": queue_size,
                "thread_pool_queue_size": thread_pool_queue_size,
                "total_load": active_tasks + queue_size + thread_pool_queue_size
            }
        
        metrics = {
            "cpu_bound_workers": len(self._cpu_workers),
            "io_bound_workers": len(self._io_workers),
            "total_workers": len(self._cpu_workers) + len(self._io_workers),
            "cpu_active_threads": cpu_active,
            "io_active_threads": io_active,
            "total_active_threads": cpu_active + io_active,
            "cpu_worker_tasks": cpu_worker_tasks,  # Her CPU worker'ın görev sayıları
            "io_worker_tasks": io_worker_tasks,    # Her IO worker'ın görev sayıları
        }
        
        health = "healthy" if self._started else "unhealthy"
        
        return ComponentStatus(
            name="process_pool",
            health=health,
            metrics=metrics
        )


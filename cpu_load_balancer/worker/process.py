"""Worker Process - tek bir worker process"""

import multiprocessing
import os
from typing import Any, Optional, Callable, List
import time
import queue
from threading import Event
import psutil

from ..core.enums import TaskType, ProcessMetric
from .thread import ThreadPool


class WorkerProcess:
    """
    Worker Process - basitleştirilmiş
    
    Bir process içinde birden fazla thread çalıştırır.
    """
    
    def __init__(
        self,
        worker_id: str,
        task_type: TaskType,
        max_threads: int,
        output_queue: Any,
        executor_func: Optional[Callable] = None,
        cpu_id: Optional[int] = None,
        nice_level: int = 0,
        my_queue: Any = None,  # Kendi kuyruğu
        all_queues: List[Any] = None  # Tüm kuyruklar (çalmak için)
    ):
        self._worker_id = worker_id
        self._task_type = task_type
        self._max_threads = max_threads
        self._output_queue = output_queue
        self._cpu_id = cpu_id
        self._nice_level = nice_level
        self._my_queue = my_queue
        self._all_queues = all_queues or []
        # executor_func pickle edilemez, process içinde oluşturulacak
        self._executor_func = None
        
        # Process communication
        self._cmd_pipe, child_pipe = multiprocessing.Pipe()
        self._process: Optional[multiprocessing.Process] = None
        # Event pickle edilemez, process içinde oluşturulacak
        self._child_pipe = child_pipe
        
        # Shared counter for active tasks
        self._active_task_count = multiprocessing.Value('i', 0)
        # Shared counter for ThreadPool queue size
        self.thread_pool_queue_size = multiprocessing.Value('i', 0)

        self.process_metrics = multiprocessing.Array('d', len(ProcessMetric), lock=False)

    def start(self):
        """Process'i başlat"""
        # executor_func pickle edilemez, None geçiriyoruz
        # Process objesi pickle edilebilir olmalı
        process = multiprocessing.Process(
            target=self._run_process,
            args=(
                self._child_pipe,
                self._output_queue,
                None,  # executor_func process içinde oluşturulacak
                self._max_threads,
                self._worker_id,
                self._active_task_count,
                self.thread_pool_queue_size,
                self._cpu_id,
                self._nice_level,
                self._my_queue,
                self._all_queues,
                self.process_metrics
            )
        )
        process.start()
        self._process = process
    
    def submit_task(self, task: Any) -> bool:
        """Görev gönder"""
        try:
            self._cmd_pipe.send({
                "command": "execute_task",
                "task": task.to_dict() if hasattr(task, 'to_dict') else task
            })
                
            return True
        except:
            return False
    
    def shutdown(self):
        """Process'i kapat"""
        try:
            # Shutdown komutu gönder
            if self._cmd_pipe and not self._cmd_pipe.closed:
                try:
                    self._cmd_pipe.send({"command": "shutdown"})
                except:
                    pass
            
            # Process'in kapanmasını bekle
            if self._process:
                self._process.join(timeout=5.0)
                
                # Hala çalışıyorsa terminate et
                if self._process.is_alive():
                    self._process.terminate()
                    self._process.join(timeout=2.0)
                    
                    # Hala çalışıyorsa kill et
                    if self._process.is_alive():
                        self._process.kill()
                        self._process.join(timeout=1.0)
        except Exception:
            pass
    
    def active_thread_count(self) -> tuple:
        """Aktif thread sayısı (yaklaşık)"""
        return self._active_task_count.value, self._my_queue.qsize(), self.thread_pool_queue_size.value
        
    def increment_load(self):
        """Yükü artır (Main process'ten çağrılır)"""
        with self._active_task_count.get_lock():
            self._active_task_count.value += 1
    
    def __getstate__(self):
        """Pickle için state - sadece pickle edilebilir değerleri döndür"""
        # Process objesi pickle edilemez, None yap
        state = {
            '_worker_id': self._worker_id,
            '_task_type': self._task_type,
            '_max_threads': self._max_threads,
            '_output_queue': self._output_queue,
            '_cmd_pipe': self._cmd_pipe,
            '_child_pipe': self._child_pipe,
            '_executor_func': None,
            '_process': None,  # Process objesi pickle edilemez
            '_active_task_count': self._active_task_count,
            'thread_pool_queue_size': self.thread_pool_queue_size,
            '_cpu_id': self._cpu_id,
            '_nice_level': self._nice_level,
            '_my_queue': self._my_queue,
            '_all_queues': self._all_queues,
        }
        return state
    
    def __setstate__(self, state):
        """Pickle'dan restore et"""
        self._worker_id = state['_worker_id']
        self._task_type = state['_task_type']
        self._max_threads = state['_max_threads']
        self._output_queue = state['_output_queue']
        self._cmd_pipe = state['_cmd_pipe']
        self._child_pipe = state['_child_pipe']
        self._executor_func = None
        self._process = None
        self._active_task_count = state['_active_task_count']
        self.thread_pool_queue_size = state.get('thread_pool_queue_size', multiprocessing.Value('i', 0))
        self._cpu_id = state.get('_cpu_id')
        self._nice_level = state.get('_nice_level', 0)
        self._my_queue = state.get('_my_queue')
        self._all_queues = state.get('_all_queues', [])
    
    @staticmethod
    def _run_process(cmd_pipe, output_queue, executor_func, max_threads, worker_id, active_task_count, thread_pool_queue_size, cpu_id, nice_level, my_queue, all_queues, process_metrics):
        """Process içinde çalışan fonksiyon"""

        # 1. Process Önceliğini Ayarla (Nice Value)
        # Pozitif değerler önceliği düşürür (sistemi rahatlatır)
        if nice_level != 0:
            try:
                os.nice(nice_level)
            except Exception as e:
                pass  # İzin hatası olabilir, yoksay

        # 2. CPU Affinity Ayarla (Çekirdek Sabitleme)
        # Process'i belirli bir çekirdeğe kilitler
        if cpu_id is not None and hasattr(os, 'sched_setaffinity'):
            try:
                os.sched_setaffinity(0, {cpu_id})
            except Exception as e:
                pass  # Desteklenmiyor veya hata, yoksay

        # executor_func None ise, process içinde oluştur
        # Event'i de burada oluştur (pickle sorunu için)

        thread_pool = ThreadPool(
            max_threads=max_threads,
            output_queue=output_queue,
            executor_func=executor_func,  # None olacak, ThreadPool içinde oluşturulacak
            worker_id=worker_id,
            active_task_count=active_task_count,  # Counter'ı ThreadPool'a geçir
            thread_pool_queue_size=thread_pool_queue_size  # Queue size counter'ı
        )
        thread_pool.start()

        shutdown_event = Event()

        proc = psutil.Process(os.getpid())
        proc.cpu_percent(None)

        last_metrics_update = 0.0
        metrics_interval = 1.0

        while not shutdown_event.is_set():

            now = time.time()
            if now - last_metrics_update >= metrics_interval:
                cpu = proc.cpu_percent(None)
                mem = proc.memory_info().rss / (1024 * 1024)

                process_metrics[0] = cpu
                process_metrics[1] = mem

                last_metrics_update = now

            request = None

            thread_pool_queue_size_val = thread_pool.queue_size()

            with thread_pool_queue_size.get_lock():
                thread_pool_queue_size.value = thread_pool_queue_size_val

            if thread_pool_queue_size_val >= max_threads:
                time.sleep(0.001)
                continue

            # Aktif görev sayısı kontrolü (ek güvenlik)
            if active_task_count.value >= max_threads:
                time.sleep(0.001)
                continue

            # 1. Önce kendi kuyruğuna bak (Öncelikli)
            if my_queue:
                try:
                    request = my_queue.get_nowait()
                except queue.Empty:
                    pass

            # 2. Kendi kuyruğu boşsa, diğerlerinden çal (Work Stealing)
            if request is None and all_queues:
                other_queues = []

                for q in all_queues:
                    if q != my_queue:
                        try:
                            size = q.qsize()
                            if size > 0:
                                other_queues.append((size, q))
                        except:
                            other_queues.append((1, q))

                other_queues.sort(reverse=True, key=lambda x: x[0])

                # En dolu olanlardan başlayarak dene
                for size, victim_queue in other_queues:
                    try:
                        request = victim_queue.get_nowait()
                        break  # Bulduğumuzu al, devam etme
                    except queue.Empty:
                        continue  # Bir sonrakini dene

            # 3. Hala iş yoksa Pipe'ı kontrol et (Eski usul komutlar için)
            if request is None:
                try:
                    if cmd_pipe.poll(0.01): # Biraz bekle (CPU'yu yakmamak için)
                        request = cmd_pipe.recv()
                except:
                    pass

            # İşi işle
            if request:
                command = request.get("command")

                if command == "execute_task":
                    task_dict = request.get("task")
                    thread_pool.submit_task(task_dict)

                elif command == "shutdown":
                    shutdown_event.set()
                    break
            else:
                time.sleep(0.001)

        thread_pool.shutdown()


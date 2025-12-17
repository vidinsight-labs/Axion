"""Worker Process - tek bir worker process"""

import multiprocessing
import os
from typing import Any, Optional, Callable, List
import time
import queue
import random
from threading import Event

from ..core.enums import TaskType
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
                self._cpu_id,
                self._nice_level,
                self._my_queue,
                self._all_queues
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
            
            # Görev gönderildiğinde sayacı artır (main process)
            with self._active_task_count.get_lock():
                self._active_task_count.value += 1
                
            return True
        except:
            return False
    
    def shutdown(self):
        """Process'i kapat"""
        try:
            self._cmd_pipe.send({"command": "shutdown"})
            if self._process:
                self._process.join(timeout=5.0)
        except:
            pass
    
    def active_thread_count(self) -> int:
        """Aktif thread sayısı (yaklaşık)"""
        return self._active_task_count.value
        
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
        self._cpu_id = state.get('_cpu_id')
        self._nice_level = state.get('_nice_level', 0)
        self._my_queue = state.get('_my_queue')
        self._all_queues = state.get('_all_queues', [])
    
    @staticmethod
    def _run_process(cmd_pipe, output_queue, executor_func, max_threads, worker_id, active_task_count, cpu_id, nice_level, my_queue, all_queues):
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
            active_task_count=active_task_count  # Counter'ı ThreadPool'a geçir
        )
        thread_pool.start()
        
        shutdown_event = Event()
        
        while not shutdown_event.is_set():
            request = None
            
            # 1. Önce kendi kuyruğuna bak (Öncelikli)
            if my_queue:
                try:
                    request = my_queue.get_nowait()
                except queue.Empty:
                    pass
            
            # 2. Kendi kuyruğu boşsa, diğerlerinden çal (Work Stealing)
            if request is None and all_queues:
                # Rastgele bir kurbandan çalmaya çalış
                # Tüm kuyrukları denemek yerine rastgele 1-2 tanesini denemek daha verimlidir
                victim_queue = random.choice(all_queues)
                if victim_queue != my_queue:
                    try:
                        request = victim_queue.get_nowait()
                        # Çaldık!
                    except queue.Empty:
                        pass
            
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

                    # Görev alındı, sayacı artır (eğer pool artırmadıysa)
                    # Not: Pool zaten artırmıştı, ama work stealing ile aldıysak
                    # pool bizim aldığımızı bilmiyor olabilir.
                    # Ancak active_task_count shared olduğu için sorun yok.
                    # Sadece "hangi worker"ın aldığı değişti.

                    thread_pool.submit_task(task_dict)
                elif command == "shutdown":
                    shutdown_event.set()
                    break
            else:
                # Hiç iş yok, biraz uyu (Busy wait yapma)
                # Work stealing sistemlerinde tamamen uyumak tehlikelidir (latency artar)
                # Ama çok kısa bir uyku (yield) iyidir.
                time.sleep(0.001)
        
        thread_pool.shutdown()


"""Worker Process - tek bir worker process"""

import multiprocessing
import os
from typing import Any, Optional, Callable

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
        executor_func: Optional[Callable] = None
    ):
        self._worker_id = worker_id
        self._task_type = task_type
        self._max_threads = max_threads
        self._output_queue = output_queue
        # executor_func pickle edilemez, process içinde oluşturulacak
        self._executor_func = None
        
        # Process communication
        self._cmd_pipe, child_pipe = multiprocessing.Pipe()
        self._process: Optional[multiprocessing.Process] = None
        # Event pickle edilemez, process içinde oluşturulacak
        self._child_pipe = child_pipe
    
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
                self._worker_id
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
            self._cmd_pipe.send({"command": "shutdown"})
            if self._process:
                self._process.join(timeout=5.0)
        except:
            pass
    
    def active_thread_count(self) -> int:
        """Aktif thread sayısı (yaklaşık)"""
        # Basit implementasyon - gerçek sayıyı process'ten almak gerekir
        # Şimdilik sabit döndürüyoruz
        return 0
    
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
    
    @staticmethod
    def _run_process(cmd_pipe, output_queue, executor_func, max_threads, worker_id):
        """Process içinde çalışan fonksiyon"""
        # executor_func None ise, process içinde oluştur
        # Event'i de burada oluştur (pickle sorunu için)
        from threading import Event
        
        thread_pool = ThreadPool(
            max_threads=max_threads,
            output_queue=output_queue,
            executor_func=executor_func,  # None olacak, ThreadPool içinde oluşturulacak
            worker_id=worker_id
        )
        thread_pool.start()
        
        shutdown_event = Event()
        
        while not shutdown_event.is_set():
            try:
                if cmd_pipe.poll(0.1):
                    request = cmd_pipe.recv()
                    command = request.get("command")
                    
                    if command == "execute_task":
                        task_dict = request.get("task")
                        thread_pool.submit_task(task_dict)
                    elif command == "shutdown":
                        shutdown_event.set()
                        break
            except:
                pass
        
        thread_pool.shutdown()


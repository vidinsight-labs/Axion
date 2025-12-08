"""
Output Queue Modülü

Bu modül, görev sonuçlarının toplandığı kuyruğu yönetir.
Multiprocessing.Queue kullanır ve status takibi sağlar.

Kullanım:
    queue = OutputQueue(maxsize=10000)
    queue.put(result_dict)
    result = queue.get(timeout=1.0)
"""

import multiprocessing
import queue
from typing import Any, Dict, Optional
from threading import Lock
from datetime import datetime

from ..status import ComponentStatus


class OutputQueue:
    """
    Output Queue - Sonuç kuyruğu
    
    Görev sonuçları buraya eklenir ve Engine tarafından alınır.
    
    Özellikler:
    - Non-blocking put: Queue doluysa False döner
    - Blocking get: Timeout ile sonuç alır
    - Status takibi: Queue boyutu, toplam eklenen/alınan sonuç sayısı
    """
    
    def __init__(self, maxsize: int = 10000):
        self._queue = multiprocessing.Queue(maxsize=maxsize)
        self._maxsize = maxsize
        self._total_put = 0
        self._total_get = 0
        self._lock = Lock()
        self._created_at = datetime.now()
    
    def put(self, item: Dict[str, Any]) -> bool:
        """Sonuç ekle (non-blocking)"""
        try:
            self._queue.put_nowait(item)
            with self._lock:
                self._total_put += 1
            return True
        except queue.Full:
            return False
    
    def get(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Sonuç al"""
        try:
            if timeout is None:
                return self._queue.get_nowait()
            else:
                item = self._queue.get(timeout=timeout)
                with self._lock:
                    self._total_get += 1
                return item
        except queue.Empty:
            return None
    
    def size(self) -> int:
        """Queue boyutu"""
        try:
            return self._queue.qsize()
        except:
            return 0
    
    def get_status(self) -> ComponentStatus:
        """Component durumu"""
        with self._lock:
            metrics = {
                "size": self.size(),
                "maxsize": self._maxsize,
                "total_put": self._total_put,
                "total_get": self._total_get,
            }
        
        health = "healthy"
        
        return ComponentStatus(
            name="output_queue",
            health=health,
            metrics=metrics
        )
    
    def __getstate__(self):
        """Pickle için state - lock'ları hariç tut"""
        return {
            '_queue': self._queue,
            '_maxsize': self._maxsize,
            '_total_put': self._total_put,
            '_total_get': self._total_get,
            '_created_at': self._created_at,
        }
    
    def __setstate__(self, state):
        """Pickle'dan restore et"""
        from threading import Lock
        self._queue = state['_queue']
        self._maxsize = state['_maxsize']
        self._total_put = state['_total_put']
        self._total_get = state['_total_get']
        self._created_at = state['_created_at']
        self._lock = Lock()  # Yeni lock oluştur
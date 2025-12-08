"""
Input Queue Modülü

Bu modül, görevlerin gönderildiği kuyruğu yönetir.
Multiprocessing.Queue kullanır ve status takibi sağlar.

Kullanım:
    queue = InputQueue(maxsize=1000)
    queue.put(task_dict)
    task = queue.get(timeout=1.0)
"""

import multiprocessing
import queue
from typing import Any, Dict, Optional
from threading import Lock
from datetime import datetime, timezone

from ..status import ComponentStatus


class InputQueue:
    """
    Input Queue - Görev kuyruğu
    
    Görevler buraya gönderilir ve queue processing thread tarafından alınır.
    
    Özellikler:
    - Non-blocking put: Queue doluysa False döner
    - Blocking get: Timeout ile görev alır
    - Status takibi: Queue boyutu, toplam gönderilen görev sayısı
    """
    def __init__(self, maxsize: int = 1000):
        self._queue = multiprocessing.Queue(maxsize=maxsize)
        self._created_at = datetime.now(timezone.utc)
        self._maxsize = maxsize
        self._total_put = 0
        self._total_dropped = 0
        self._lock = Lock()

    def put(self, item: Dict[str, Any]) -> bool:
        """
        Görev ekler (non-blocking)
        
        Queue doluysa False döner, görev eklenmez.
        
        Args:
            item: Görev dict'i (Task.to_dict() sonucu)
        
        Returns:
            bool: True ise başarılı, False ise queue dolu
        """
        try:
            self._queue.put_nowait(item)
            with self._lock:
                self._total_put += 1
            return True
        except queue.Full:
            # Queue dolu, görev eklenemedi
            with self._lock:
                self._total_dropped += 1
            return False 

    def get(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Görev alır
        
        Args:
            timeout: Maksimum bekleme süresi (saniye). None = non-blocking
        
        Returns:
            Dict: Görev dict'i veya None (timeout/boş)
        """
        try:
            if timeout is None:
                return self._queue.get_nowait()  # Non-blocking
            else:
                return self._queue.get(timeout=timeout)  # Blocking with timeout
        except queue.Empty:
            return None  # Queue boş veya timeout

    def size(self) -> int:
        """Queue boyutu"""
        try:
            return self._queue.qsize()
        except:
            return 0
    
    def is_empty(self) -> bool:
        """Boş mu?"""
        return self._queue.empty()
    
    def is_full(self) -> bool:
        """Dolu mu?"""
        return self._queue.full()
    
    def get_status(self) -> ComponentStatus:
        """Component durumu"""
        with self._lock:
            metrics = {
                "size": self.size(),
                "maxsize": self._maxsize,
                "fullness": self.size() / self._maxsize if self._maxsize > 0 else 0.0,
                "total_put": self._total_put,
                "total_dropped": self._total_dropped,
            }
        
        health = "healthy" if self._total_dropped < 100 else "unhealthy"
        
        return ComponentStatus(
            name="input_queue",
            health=health,
            metrics=metrics
        )

    def __getstate__(self):
        """Pickle için state - lock'ları hariç tut"""
        return {
            '_queue': self._queue,
            '_maxsize': self._maxsize,
            '_total_put': self._total_put,
            '_total_dropped': self._total_dropped,
            '_created_at': self._created_at,
        }
    
    def __setstate__(self, state):
        """Pickle'dan restore et"""
        from threading import Lock
        self._queue = state['_queue']
        self._maxsize = state['_maxsize']
        self._total_put = state['_total_put']
        self._total_dropped = state['_total_dropped']
        self._created_at = state['_created_at']
        self._lock = Lock()  # Yeni lock oluştur
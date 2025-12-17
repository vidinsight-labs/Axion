
from typing import Dict, List, Set, Optional
from threading import Lock
from ..task.task import Task
from ..task.result import Result

class WorkflowManager:
    """
    Workflow (DAG) Yöneticisi
    
    Görevler arasındaki bağımlılıkları yönetir.
    Bir görev tamamlandığında, ona bağımlı olan diğer görevleri tetikler.
    """
    
    def __init__(self):
        self._lock = Lock()
        
        # Tüm görevler: {task_id: Task}
        self._tasks: Dict[str, Task] = {}
        
        # Bağımlılık haritası: {task_id: [dependent_task_ids]}
        # Örnek: A -> B ise, {A: [B]}
        self._dependency_graph: Dict[str, List[str]] = {}
        
        # Bekleyen bağımlılık sayısı: {task_id: count}
        # Örnek: C, A ve B'yi bekliyorsa {C: 2}
        self._waiting_counts: Dict[str, int] = {}
        
        # Tamamlanan görevlerin sonuçları (Veri aktarımı için)
        self._results: Dict[str, Result] = {}
        
    def add_workflow(self, tasks: List[Task]):
        """
        Yeni bir workflow (görev grubu) ekler
        """
        with self._lock:
            for task in tasks:
                self._tasks[task.id] = task
                self._waiting_counts[task.id] = len(task.dependencies)
                
                # Graph'ı oluştur (Reverse index)
                # Eğer B, A'ya bağımlıysa: graph[A].append(B)
                for dep_id in task.dependencies:
                    if dep_id not in self._dependency_graph:
                        self._dependency_graph[dep_id] = []
                    self._dependency_graph[dep_id].append(task.id)
                    
    def get_ready_tasks(self) -> List[Task]:
        """
        Çalışmaya hazır (bağımlılığı kalmayan) görevleri döndürür
        """
        ready_tasks = []
        with self._lock:
            for task_id, count in list(self._waiting_counts.items()):
                if count == 0:
                    ready_tasks.append(self._tasks[task_id])
                    # Artık beklemiyor, listeden çıkar (tekrar gönderilmemesi için)
                    del self._waiting_counts[task_id]
        return ready_tasks
        
    def task_completed(self, result: Result) -> List[Task]:
        """
        Bir görev tamamlandığında çağrılır.
        Yeni açılan (kilidi kalkan) görevleri döndürür.
        """
        newly_ready_tasks = []
        
        with self._lock:
            task_id = result.task_id
            self._results[task_id] = result
            
            # Bu göreve bağımlı olanları bul
            dependents = self._dependency_graph.get(task_id, [])
            
            for dep_id in dependents:
                if dep_id in self._waiting_counts:
                    self._waiting_counts[dep_id] -= 1
                    
                    # Eğer tüm bağımlılıklar bittiyse
                    if self._waiting_counts[dep_id] == 0:
                        task = self._tasks[dep_id]
                        
                        # Veri Aktarımı (Data Passing):
                        # Önceki görevin sonucunu, yeni görevin parametrelerine ekle
                        # Basit bir convention: params['upstream_results'] = {task_id: result_data}
                        if 'upstream_results' not in task.params:
                            task.params['upstream_results'] = {}
                        
                        # Bağımlı olduğu tüm görevlerin sonuçlarını topla
                        for dep in task.dependencies:
                            if dep in self._results:
                                task.params['upstream_results'][dep] = self._results[dep].data
                        
                        newly_ready_tasks.append(task)
                        del self._waiting_counts[dep_id]
                        
        return newly_ready_tasks

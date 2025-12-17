"""
Ana Engine Sınıfı

Bu modül, CPU Load Balancer'ın merkezi kontrol noktasıdır.
Görev gönderme, sonuç alma ve sistem yönetimi buradan yapılır.

Kullanım:
    engine = Engine(config)
    engine.start()
    task_id = engine.submit_task(task)
    result = engine.get_result(task_id)
    engine.shutdown()
"""

import logging
import threading
import time
import multiprocessing
from typing import Optional, Dict, Any
from threading import Lock, Thread

from ..config import EngineConfig
from ..task.task import Task
from ..task.result import Result
from ..core.enums import TaskType
from ..core.exceptions import EngineError, TaskError
from ..queue.input_queue import InputQueue
from ..queue.output_queue import OutputQueue
from ..worker.pool import ProcessPool
from ..status import ComponentStatus
from ..core.backpressure import BackpressureController, SystemHealth
from ..core.workflow import WorkflowManager


class Engine:
    """
    Ana Engine - Sistemin merkezi kontrol noktası
    
    Bu sınıf, tüm görev yönetimi ve sistem kontrolünü sağlar:
    - Görev gönderme (submit_task)
    - Sonuç alma (get_result)
    - Sistem durumu (get_status)
    - Queue işleme thread'i yönetimi
    
    Özellikler:
    - Result cache: Batch işlemler için sonuçları saklar
    - Pending tasks: Gönderilen görevleri takip eder
    - Graceful shutdown: Güvenli kapanma
    """
    
    def __init__(self, config: Optional[EngineConfig] = None):
        """
        Engine'i başlatır
        
        Args:
            config: Engine yapılandırması (opsiyonel, varsayılan kullanılır)
        """
        self._config = config or EngineConfig()
        
        # Logger: Sistem mesajları için
        logging.basicConfig(level=getattr(logging, self._config.log_level))
        self._logger = logging.getLogger("engine")
        
        # Durum: Engine'in çalışıp çalışmadığını takip eder
        self._started = False
        self._lock = Lock()  # Thread-safe işlemler için
        
        # Queue'lar: Görevler ve sonuçlar için
        self._input_queue: Optional[InputQueue] = None   # Görevler buraya gönderilir
        self._output_queue: Optional[OutputQueue] = None  # Sonuçlar buradan alınır
        
        # Worker pool: Görevleri işleyen process'ler
        self._process_pool: Optional[ProcessPool] = None
        
        # Queue processing thread: InputQueue'dan görev alıp worker'lara dağıtır
        self._queue_thread: Optional[Thread] = None
        self._shutdown_event = threading.Event()  # Kapanma sinyali
        
        # Pending tasks: Gönderilen ama henüz tamamlanmamış görevler
        self._pending_tasks: Dict[str, Task] = {}
        
        # Result cache: Tamamlanan görevlerin sonuçları (batch işlemler için)
        # Queue'dan gelen sonuçlar burada saklanır, istenen task_id gelene kadar bekler
        self._result_cache: Dict[str, Result] = {}
        
        # Backpressure Controller: Sistem sağlığını izler
        self._backpressure = BackpressureController()
        
        # Workflow Manager: DAG ve bağımlılık yönetimi
        self._workflow_manager = WorkflowManager()
        
        # Result processing thread: OutputQueue'dan sonuçları alıp işler
        self._result_thread: Optional[Thread] = None
        
        # Resource Manager thread: Auto-scaling
        self._resource_manager_thread: Optional[Thread] = None
    
    def start(self):
        """
        Engine'i başlatır
        
        Bu metod:
        1. Input ve Output queue'ları oluşturur
        2. Process pool'u başlatır (CPU/IO-bound worker'lar)
        3. Queue processing thread'ini başlatır
        
        Raises:
            EngineError: Engine zaten başlatılmışsa
        """
        with self._lock:
            if self._started:
                raise EngineError("Engine zaten başlatılmış", code="ENG001")
            
            # Queue'ları oluştur: Görevler ve sonuçlar için
            self._input_queue = InputQueue(maxsize=self._config.input_queue_size)
            self._output_queue = OutputQueue(maxsize=self._config.output_queue_size)
            
            # Process pool'u oluştur ve başlat
            # executor_func=None: Process içinde oluşturulacak (pickle sorunu nedeniyle)
            self._process_pool = ProcessPool(
                output_queue=self._output_queue,
                cpu_bound_count=self._config.cpu_bound_count,
                io_bound_count=self._config.io_bound_count,
                cpu_task_limit=self._config.cpu_bound_task_limit,
                io_task_limit=self._config.io_bound_task_limit,
                executor_func=None  # Process içinde oluşturulacak
            )
            self._process_pool.start()
            
            # Queue processing thread'i başlat: InputQueue'dan görev alıp worker'lara dağıtır
            self._queue_thread = Thread(target=self._process_queue_loop, daemon=True)
            self._queue_thread.start()
            
            # Result processing thread'i başlat: Sonuçları alıp WorkflowManager'a bildirir
            self._result_thread = Thread(target=self._process_result_loop, daemon=True)
            self._result_thread.start()
            
            # Resource Manager thread'i başlat
            self._resource_manager_thread = Thread(target=self._resource_manager_loop, daemon=True)
            self._resource_manager_thread.start()
            
            self._started = True
            self._logger.info("Engine başlatıldı")
    
    def shutdown(self):
        """Engine'i kapat"""
        with self._lock:
            if not self._started:
                return
            
            self._shutdown_event.set()
            
            # Process pool'u kapat
            if self._process_pool:
                self._process_pool.shutdown()
            
            # Thread'lerin bitmesini bekle
            if self._queue_thread:
                self._queue_thread.join(timeout=2.0)
            if self._result_thread:
                self._result_thread.join(timeout=2.0)
            if self._resource_manager_thread:
                self._resource_manager_thread.join(timeout=2.0)
            
            self._started = False
            self._logger.info("Engine kapatıldı")
    
    def submit_task(self, task: Task) -> str:
        """
        Görev gönderir
        
        Görev InputQueue'ya eklenir ve pending listesine kaydedilir.
        Queue processing thread görevi alıp worker'lara dağıtır.
        
        Args:
            task: Gönderilecek görev (Task objesi)
        
        Returns:
            str: Görev ID'si (UUID)
        
        Raises:
            EngineError: Engine başlatılmamışsa
            TaskError: Queue doluysa
        """
        if not self._started:
            raise EngineError("Engine başlatılmamış", code="ENG002")
            
        # Backpressure Kontrolü: Sistem aşırı yüklüyse görevi reddet
        if not self._backpressure.should_accept_task():
            # Sistem kritik durumda, görev reddediliyor
            # Kullanıcıya "Lütfen daha sonra tekrar deneyin" mesajı
            raise TaskError("Sistem aşırı yüklü (Backpressure Active)", code="TASK002")
        
        # Task'ı dict'e dönüştürüp queue'ya ekle (multiprocessing için)
        success = self._input_queue.put(task.to_dict())
        
        if not success:
            raise TaskError("Queue dolu, görev eklenemedi", code="TASK001")
        
        # Pending listesine ekle: Görev takibi için
        with self._lock:
            self._pending_tasks[task.id] = task
        
        return task.id
            
    def submit_workflow(self, tasks: list[Task]) -> list[str]:
        """
        Workflow (birbirine bağımlı görevler) gönderir
        
        Args:
            tasks: Task listesi (bağımlılıkları tanımlanmış)
            
        Returns:
            list[str]: Task ID listesi
        """
        if not self._started:
            raise EngineError("Engine başlatılmamış", code="ENG002")
            
        # WorkflowManager'a kaydet
        self._workflow_manager.add_workflow(tasks)
        
        # Hazır olan görevleri (bağımlılığı olmayanları) hemen kuyruğa at
        ready_tasks = self._workflow_manager.get_ready_tasks()
        for task in ready_tasks:
            self.submit_task(task)
            
        # Pending listesine hepsini ekle
        with self._lock:
            for task in tasks:
                self._pending_tasks[task.id] = task
                
        return [t.id for t in tasks]
    
    def get_result(self, task_id: str, timeout: Optional[float] = None) -> Optional[Result]:
        """
        Görev sonucunu alır
        
        Önce result cache'e bakılır (batch işlemler için).
        Cache'de yoksa OutputQueue'dan alınır.
        Gelen sonuç istenen task_id değilse cache'e kaydedilir.
        
        Args:
            task_id: Görev ID'si
            timeout: Maksimum bekleme süresi (saniye). None = süresiz bekle
        
        Returns:
            Result: Görev sonucu veya None (timeout)
        
        Raises:
            EngineError: Engine başlatılmamışsa
        """
        if not self._started:
            raise EngineError("Engine başlatılmamış", code="ENG002")
        
        # Önce cache'e bak: Batch işlemlerde sonuçlar burada olabilir
        with self._lock:
            if task_id in self._result_cache:
                result = self._result_cache.pop(task_id)
                self._pending_tasks.pop(task_id, None)
                return result
        
        start_time = time.time()
        
        # Artık sonuçları Result Thread topluyor ve Cache'e yazıyor.
        # Biz sadece Cache'i kontrol edeceğiz.
        
        while True:
            # Timeout kontrolü
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return None  # Timeout
            
            # Cache'e bak
            with self._lock:
                if task_id in self._result_cache:
                    result = self._result_cache.pop(task_id) # Al ve sil (veya silme opsiyonel)
                    # Not: Workflow testlerinde sonucu birden fazla yer isteyebilir, 
                    # o yüzden pop yerine get kullanmak daha güvenli olabilir ama memory şişer.
                    # Şimdilik pop yapıyoruz, kullanıcı sorumluluğunda.
                    self._pending_tasks.pop(task_id, None)
                    return result
            
            # Biraz bekle (Busy wait yapma)
            time.sleep(0.01)
    
    def _process_queue_loop(self):
        """
        Queue processing loop - Arka planda çalışan thread
        
        Bu metod sürekli InputQueue'dan görev alır ve ProcessPool'a gönderir.
        Load balancing ProcessPool içinde yapılır.
        """
        while not self._shutdown_event.is_set():
            try:
                # Input queue'dan görev al (timeout ile)
                task_dict = self._input_queue.get(timeout=self._config.queue_poll_timeout)
                
                if task_dict is None:
                    continue  # Timeout, tekrar dene
                
                # Dict'ten Task objesi oluştur
                task = Task.from_dict(task_dict)
                
                # Task type'ı belirle (CPU_BOUND veya IO_BOUND)
                task_type = task.task_type
                
                # Process pool'a gönder: Load balancing burada yapılır
                self._process_pool.submit_task(task, task_type)
            
            except Exception as e:
                # Hata durumunda logla ve devam et
                self._logger.error(f"Queue processing hatası: {e}")
                time.sleep(0.1)  # Kısa bekleme

    def _process_result_loop(self):
        """
        Result processing loop - Arka planda çalışan thread
        
        OutputQueue'dan sonuçları alır:
        1. Result Cache'e yazar.
        2. WorkflowManager'a bildirir (yeni görevleri tetikler).
        """
        while not self._shutdown_event.is_set():
            try:
                # Output queue'dan sonuç al
                item = self._output_queue.get(timeout=0.1)
                
                if item is None:
                    continue
                
                # Result objesi oluştur
                result = Result.from_dict(item)
                
                # 1. Cache'e yaz
                with self._lock:
                    self._result_cache[result.task_id] = result
                    # Cache temizliği (basit)
                    if len(self._result_cache) > 5000:
                        self._result_cache.pop(next(iter(self._result_cache)))
                
                # 2. Workflow Manager'a bildir
                new_tasks = self._workflow_manager.task_completed(result)
                
                # 3. Yeni açılan görevleri kuyruğa at
                for task in new_tasks:
                    try:
                        self.submit_task(task)
                    except Exception as e:
                        self._logger.error(f"Workflow task submission error: {e}")
                        
            except Exception as e:
                self._logger.error(f"Result processing hatası: {e}")
                time.sleep(0.1)

    def _resource_manager_loop(self):
        """
        Resource Manager Loop - Auto-Scaling
        
        Sistemi izler ve worker sayısını dinamik olarak ayarlar.
        """
        while not self._shutdown_event.is_set():
            try:
                time.sleep(5.0)  # 5 saniyede bir kontrol et
                
                if not self._process_pool:
                    continue
                    
                # Metrikleri al
                # InputQueue boyutu + Worker'lardaki aktif işler
                input_queue_size = self._input_queue.size()
                
                # ProcessPool status'undan aktif iş sayısını al
                pool_status = self._process_pool.get_status()
                active_tasks = pool_status.metrics.get('cpu_active_threads', 0)
                
                total_load = input_queue_size + active_tasks
                cpu_worker_count = self._process_pool.get_worker_count(TaskType.CPU_BOUND)
                
                # Basit Scaling Algoritması
                # Hedef: Her worker başına en fazla 5 aktif iş olsun
                
                if total_load > cpu_worker_count * 5:
                    # Scale Out (Büyüme)
                    # Max limit: 2 * CPU Core
                    max_workers = multiprocessing.cpu_count() * 2
                    
                    if cpu_worker_count < max_workers:
                        self._logger.info(f"Auto-Scaling: Yük arttı ({total_load} iş), yeni worker ekleniyor...")
                        self._process_pool.add_worker(TaskType.CPU_BOUND)
                        
                elif total_load < cpu_worker_count * 2 and cpu_worker_count > self._config.cpu_bound_count:
                    # Scale In (Küçülme)
                    # Min limit: Config'deki başlangıç sayısı
                    self._logger.info(f"Auto-Scaling: Yük azaldı ({total_load} iş), worker kapatılıyor...")
                    self._process_pool.remove_worker(TaskType.CPU_BOUND)
                    
            except Exception as e:
                self._logger.error(f"Resource manager hatası: {e}")
                time.sleep(5.0)
    
    def get_status(self) -> Dict[str, Any]:
        """Engine durumu"""
        status = {
            "engine": {
                "is_running": self._started,
            },
            "components": {}
        }
        
        if self._input_queue:
            status["components"]["input_queue"] = self._input_queue.get_status().to_dict()
        
        if self._output_queue:
            status["components"]["output_queue"] = self._output_queue.get_status().to_dict()
        
        if self._process_pool:
            status["components"]["process_pool"] = self._process_pool.get_status().to_dict()
        
        return status
    
    def get_component_status(self, name: str) -> Optional[ComponentStatus]:
        """Belirli component durumu"""
        if name == "input_queue" and self._input_queue:
            return self._input_queue.get_status()
        elif name == "output_queue" and self._output_queue:
            return self._output_queue.get_status()
        elif name == "process_pool" and self._process_pool:
            return self._process_pool.get_status()
        return None
    
    # Context manager
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        return False


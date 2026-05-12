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
from typing import Optional, Dict, Any, TYPE_CHECKING
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

if TYPE_CHECKING:
    from ..isolation import CpuIsolationManager


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
    
    def __init__(
        self,
        config: Optional[EngineConfig] = None,
        isolation_manager: Optional["CpuIsolationManager"] = None,
    ):
        """
        Engine'i başlatır

        Args:
            config: Engine yapılandırması (opsiyonel, varsayılan kullanılır)
            isolation_manager: Dışarıdan verilen CPU isolation manager.
                - Verilirse: Engine sadece kullanır; start/stop sorumluluğu çağıranındır.
                - None + config.cpu_isolation.enabled=True: Engine kendi manager'ını
                  yaratır ve yaşam döngüsünü (start/stop) kendisi yönetir.
                - None + config.cpu_isolation.enabled=False: izolasyon devre dışı.
        """
        self._config = config or EngineConfig()
        self._isolation_manager = isolation_manager
        # Manager sahipliği: True ise start/stop bu Engine'in sorumluluğunda.
        self._owns_isolation_manager = False

        if self._isolation_manager is None and self._config.cpu_isolation.enabled:
            try:
                from ..isolation import CpuIsolationManager
                self._isolation_manager = CpuIsolationManager(self._config.cpu_isolation)
                self._owns_isolation_manager = True
            except ImportError:
                # isolation modülü import edilemiyorsa sessizce atla;
                # logger henüz oluşmamış olabilir.
                self._isolation_manager = None
        
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

            # Isolation manager start: Pool'dan önce çalışmalı (cgroup hazır olsun)
            if self._owns_isolation_manager and self._isolation_manager:
                try:
                    self._isolation_manager.start()
                except Exception as e:
                    self._logger.warning(f"CPU isolation start failed: {e}")

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
                isolation_config=self._config.cpu_isolation,
                isolation_manager=self._isolation_manager,
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

            # Thread'lerin bitmesini bekle (daha uzun timeout)
            if self._queue_thread:
                self._queue_thread.join(timeout=5.0)
            if self._result_thread:
                self._result_thread.join(timeout=5.0)
            if self._resource_manager_thread:
                self._resource_manager_thread.join(timeout=5.0)

            # Process'lerin tamamen kapanmasını bekle
            if self._process_pool:
                self._process_pool.wait_for_shutdown(timeout=10.0)

            # Isolation manager stop: yalnızca biz sahibiysek (Axion'dan inject
            # edildiyse stop sorumluluğu çağırana aittir).
            if self._owns_isolation_manager and self._isolation_manager:
                try:
                    self._isolation_manager.stop()
                except Exception as e:
                    self._logger.warning(f"CPU isolation stop failed: {e}")

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

        with self._lock:
            if task_id in self._result_cache:
                result = self._result_cache.pop(task_id)
                self._pending_tasks.pop(task_id, None)
                return result

        start_time = time.time()

        # Artık sonuçları Result Thread topluyor ve Cache'e yazıyor.
        # Biz sadece Cache'i kontrol edeceğiz.

        while True:
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

            time.sleep(0.01)

    def _process_queue_loop(self):
        """
        Queue processing loop - Arka planda çalışan thread

        Bu metod sürekli InputQueue'dan görev alır ve ProcessPool'a gönderir.
        Load balancing ProcessPool içinde yapılır.
        """
        while not self._shutdown_event.is_set():
            try:
                task_dict = self._input_queue.get(timeout=self._config.queue_poll_timeout)

                if task_dict is None:
                    continue

                task = Task.from_dict(task_dict)
                task_type = task.task_type

                self._process_pool.submit_task(task, task_type)

            except Exception as e:
                self._logger.error(f"Queue processing hatası: {e}")
                time.sleep(0.1)

    def _process_result_loop(self):
        """
        Result processing loop - Arka planda çalışan thread

        OutputQueue'dan sonuçları alır:
        1. Result Cache'e yazar.
        2. WorkflowManager'a bildirir (yeni görevleri tetikler).
        """
        while not self._shutdown_event.is_set():
            try:
                item = self._output_queue.get(timeout=0.1)

                if item is None:
                    continue

                result = Result.from_dict(item)

                with self._lock:
                    self._result_cache[result.task_id] = result
                    if len(self._result_cache) > 5000:
                        self._result_cache.pop(next(iter(self._result_cache)))

                new_tasks = self._workflow_manager.task_completed(result)

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
        Advanced Resource Manager - Queue-Aware + Task-Count-Based Scaling

        Özellikler:
        - Input queue monitoring: Bekleyen görevlere göre scale
        - Pending task tracking: Tamamlanmamış görev sayısını izler
        - Worker load based: Mevcut worker yükünü de dikkate alır
        - Smart max limits: Makul maksimum worker limitleri
        """

        # ==================== TIMING ====================
        CHECK_INTERVAL_SEC = 2.0
        FAST_CHECK_INTERVAL_SEC = 1.0
        SCALE_COOLDOWN_SEC = 8.0
        EMERGENCY_COOLDOWN_SEC = 3.0
        HISTORY_SIZE = 8
        WORKER_WARMUP_SEC = 3.0

        # ==================== MAX WORKER LIMITS ====================
        # CPU-Bound: Daha konservatif (CPU-intensive)
        CPU_MAX_WORKERS_ABSOLUTE = min(multiprocessing.cpu_count() * 2, 16)

        # IO-Bound: Daha liberal ama sınırlı (IO-waiting)
        IO_MAX_WORKERS_ABSOLUTE = min(multiprocessing.cpu_count() * 3, 24)

        # ==================== CPU-BOUND THRESHOLDS ====================
        CPU_CRITICAL_LOAD = 10.0
        CPU_HIGH_LOAD = 6.0
        CPU_MODERATE_LOAD = 3.5
        CPU_LOW_LOAD = 1.2
        CPU_USAGE_HIGH = 0.75
        CPU_USAGE_CRITICAL = 0.90

        # Queue-based thresholds (per worker)
        CPU_QUEUE_PER_WORKER_HIGH = 100  # Worker başına 100+ görev varsa scale
        CPU_QUEUE_PER_WORKER_MODERATE = 50

        # ==================== IO-BOUND THRESHOLDS ====================
        IO_CRITICAL_LOAD = 50.0
        IO_HIGH_LOAD = 35.0
        IO_MODERATE_LOAD = 20.0
        IO_LOW_LOAD = 8.0
        IO_QUEUE_CRITICAL = 40
        IO_QUEUE_HIGH = 20

        # Queue-based thresholds (per worker)
        IO_QUEUE_PER_WORKER_HIGH = 200
        IO_QUEUE_PER_WORKER_MODERATE = 100

        # ==================== VELOCITY THRESHOLDS ====================
        VELOCITY_CRITICAL = 5.0
        VELOCITY_HIGH = 2.5

        # Stability tracking
        cpu_load_history = []
        io_load_history = []
        cpu_last_scale_time = 0
        io_last_scale_time = 0
        last_worker_add_time = {"cpu": 0, "io": 0}

        # Task injection tracking
        last_pending_count = {"cpu": 0, "io": 0}

        check_interval = CHECK_INTERVAL_SEC
        is_fast_mode = False

        while not self._shutdown_event.is_set():
            try:
                time.sleep(check_interval)

                if not self._process_pool:
                    continue

                pool_status = self._process_pool.get_status()
                metrics = getattr(pool_status, "metrics", {}) or {}
                now = time.time()

                # ================================================================
                # GLOBAL QUEUE MONITORING (Input Queue)
                # ================================================================
                input_queue_size = 0
                if self._input_queue:
                    try:
                        input_queue_size = self._input_queue.qsize()
                    except:
                        input_queue_size = 0

                # Pending tasks count (from Engine)
                with self._lock:
                    total_pending = len(self._pending_tasks)

                # Worker warm-up kontrolü
                cpu_warmup_active = (now - last_worker_add_time["cpu"]) < WORKER_WARMUP_SEC
                io_warmup_active = (now - last_worker_add_time["io"]) < WORKER_WARMUP_SEC

                should_use_fast_check = False

                # ================================================================
                # CPU-BOUND WORKER MANAGEMENT
                # ================================================================
                cpu_worker_tasks = metrics.get("cpu_worker_tasks", {})
                cpu_worker_count = self._process_pool.get_worker_count(TaskType.CPU_BOUND)

                if cpu_worker_count > 0:
                    cpu_loads = []
                    cpu_usages = []
                    cpu_queue_sizes = []

                    for w_metrics in cpu_worker_tasks.values():
                        cpu_loads.append(w_metrics.get("total_load", 0))
                        cpu_usages.append(w_metrics.get("cpu_usage", 0.0) / 100.0)
                        cpu_queue_sizes.append(w_metrics.get("queue_size", 0))

                    cpu_avg_load = sum(cpu_loads) / cpu_worker_count if cpu_loads else 0
                    cpu_max_load = max(cpu_loads) if cpu_loads else 0
                    cpu_avg_usage = sum(cpu_usages) / len(cpu_usages) if cpu_usages else 0
                    cpu_p75_load = sorted(cpu_loads)[
                        min(int(len(cpu_loads) * 0.75), len(cpu_loads) - 1)] if cpu_loads else 0
                    cpu_total_queue = sum(cpu_queue_sizes)
                    cpu_queue_per_worker = cpu_total_queue / cpu_worker_count if cpu_worker_count > 0 else 0

                    # History tracking
                    cpu_load_history.append(cpu_avg_load)
                    if len(cpu_load_history) > HISTORY_SIZE:
                        cpu_load_history.pop(0)

                    # ---- VELOCITY CALCULATION ----
                    cpu_velocity = 0
                    if len(cpu_load_history) >= 5:
                        recent_avg = sum(cpu_load_history[-3:]) / 3
                        old_avg = sum(cpu_load_history[:3]) / 3
                        time_diff = (len(cpu_load_history) - 1) * check_interval
                        cpu_velocity = (recent_avg - old_avg) / time_diff if time_diff > 0 else 0

                    # ---- INPUT QUEUE PRESSURE (CPU tasks estimated) ----
                    # Tahmin: Input queue'nun %50'si CPU-bound olabilir (ayarlanabilir)
                    estimated_cpu_pending = input_queue_size * 0.5 + cpu_total_queue
                    cpu_pending_per_worker = estimated_cpu_pending / cpu_worker_count if cpu_worker_count > 0 else 0

                    # ---- SCALE DECISION LOGIC ----
                    time_since_last_scale = now - cpu_last_scale_time
                    can_scale_normal = time_since_last_scale >= SCALE_COOLDOWN_SEC
                    can_scale_emergency = time_since_last_scale >= EMERGENCY_COOLDOWN_SEC

                    workers_to_add = 0
                    workers_to_remove = 0
                    is_emergency = False
                    reason = ""

                    # ==================== SCALE OUT LOGIC ====================

                    # PRIORITY 1: INPUT QUEUE PRESSURE (Proactive)
                    # Çok fazla görev bekliyor, hemen scale
                    if cpu_pending_per_worker >= CPU_QUEUE_PER_WORKER_HIGH:
                        if can_scale_emergency and not cpu_warmup_active:
                            workers_to_add = min(2, CPU_MAX_WORKERS_ABSOLUTE - cpu_worker_count)
                            reason = f"QUEUE PRESSURE: {cpu_pending_per_worker:.0f} tasks/worker (queue={input_queue_size})"
                            is_emergency = True
                            should_use_fast_check = True

                    # PRIORITY 2: EMERGENCY LOAD
                    elif cpu_max_load >= CPU_CRITICAL_LOAD and cpu_avg_usage >= CPU_USAGE_CRITICAL:
                        if can_scale_emergency and not cpu_warmup_active:
                            workers_to_add = min(2, CPU_MAX_WORKERS_ABSOLUTE - cpu_worker_count)
                            reason = f"EMERGENCY LOAD: max={cpu_max_load:.1f}, cpu={cpu_avg_usage:.2f}"
                            is_emergency = True
                            should_use_fast_check = True

                    # PRIORITY 3: MODERATE QUEUE + HIGH VELOCITY
                    elif cpu_pending_per_worker >= CPU_QUEUE_PER_WORKER_MODERATE and cpu_velocity >= VELOCITY_HIGH:
                        if can_scale_normal and not cpu_warmup_active:
                            workers_to_add = 1
                            reason = f"QUEUE+VEL: {cpu_pending_per_worker:.0f} tasks/worker, vel={cpu_velocity:.2f}/s"

                    # PRIORITY 4: HIGH VELOCITY
                    elif cpu_velocity >= VELOCITY_CRITICAL and cpu_avg_load >= CPU_MODERATE_LOAD:
                        if can_scale_normal and not cpu_warmup_active:
                            workers_to_add = 1
                            reason = f"HIGH VELOCITY: vel={cpu_velocity:.2f}/s, load={cpu_avg_load:.1f}"

                    # PRIORITY 5: HIGH LOAD
                    elif cpu_p75_load >= CPU_HIGH_LOAD and cpu_avg_usage >= CPU_USAGE_HIGH:
                        if can_scale_normal and not cpu_warmup_active:
                            workers_to_add = 1
                            reason = f"HIGH LOAD: p75={cpu_p75_load:.1f}, cpu={cpu_avg_usage:.2f}"

                    # PRIORITY 6: MODERATE LOAD + QUEUE
                    elif cpu_avg_load >= CPU_MODERATE_LOAD and cpu_pending_per_worker >= 20:
                        if can_scale_normal and not cpu_warmup_active:
                            workers_to_add = 1
                            reason = f"MODERATE LOAD+QUEUE: load={cpu_avg_load:.1f}, queue={cpu_pending_per_worker:.0f}/worker"

                    # ==================== SCALE IN LOGIC ====================
                    elif (cpu_avg_load < CPU_LOW_LOAD
                          and cpu_max_load < CPU_LOW_LOAD * 1.5
                          and cpu_avg_usage < 0.25
                          and cpu_velocity <= 0
                          and cpu_pending_per_worker < 5
                          and input_queue_size < 10
                          and cpu_worker_count > self._config.cpu_bound_count):
                        if can_scale_normal:
                            workers_to_remove = 1
                            reason = f"SCALE IN: load={cpu_avg_load:.1f}, queue={cpu_pending_per_worker:.0f}/worker"

                    # ==================== EXECUTE SCALING ====================
                    if workers_to_add > 0 and cpu_worker_count < CPU_MAX_WORKERS_ABSOLUTE:
                        actual_added = 0
                        for _ in range(workers_to_add):
                            if cpu_worker_count < CPU_MAX_WORKERS_ABSOLUTE:
                                self._process_pool.add_worker(TaskType.CPU_BOUND)
                                cpu_worker_count += 1
                                actual_added += 1

                        if actual_added > 0:
                            self._logger.warning(
                                f"[CPU] Scale OUT +{actual_added} → {cpu_worker_count} workers | {reason}"
                            )
                            cpu_last_scale_time = now
                            last_worker_add_time["cpu"] = now

                            if len(cpu_load_history) > 6:
                                cpu_load_history = cpu_load_history[-6:]

                    elif workers_to_remove > 0:
                        self._process_pool.remove_worker(TaskType.CPU_BOUND)
                        self._logger.info(
                            f"[CPU] Scale IN -1 → {cpu_worker_count - 1} workers | {reason}"
                        )
                        cpu_last_scale_time = now
                        if len(cpu_load_history) > 6:
                            cpu_load_history = cpu_load_history[-6:]

                # ================================================================
                # IO-BOUND WORKER MANAGEMENT
                # ================================================================
                io_worker_tasks = metrics.get("io_worker_tasks", {})
                io_worker_count = self._process_pool.get_worker_count(TaskType.IO_BOUND)

                if io_worker_count > 0:
                    io_loads = []
                    io_queue_sizes = []

                    for w_metrics in io_worker_tasks.values():
                        io_loads.append(w_metrics.get("total_load", 0))
                        io_queue_sizes.append(w_metrics.get("queue_size", 0))

                    io_avg_load = sum(io_loads) / io_worker_count if io_loads else 0
                    io_max_load = max(io_loads) if io_loads else 0
                    io_avg_queue = sum(io_queue_sizes) / io_worker_count if io_queue_sizes else 0
                    io_p90_load = sorted(io_loads)[min(int(len(io_loads) * 0.90), len(io_loads) - 1)] if io_loads else 0
                    io_total_queue = sum(io_queue_sizes)
                    io_queue_per_worker = io_total_queue / io_worker_count if io_worker_count > 0 else 0

                    # History tracking
                    io_load_history.append(io_avg_load)
                    if len(io_load_history) > HISTORY_SIZE:
                        io_load_history.pop(0)

                    # ---- VELOCITY CALCULATION ----
                    io_velocity = 0
                    if len(io_load_history) >= 5:
                        recent_avg = sum(io_load_history[-3:]) / 3
                        old_avg = sum(io_load_history[:3]) / 3
                        time_diff = (len(io_load_history) - 1) * check_interval
                        io_velocity = (recent_avg - old_avg) / time_diff if time_diff > 0 else 0

                    # ---- INPUT QUEUE PRESSURE (IO tasks estimated) ----
                    estimated_io_pending = input_queue_size * 0.5 + io_total_queue
                    io_pending_per_worker = estimated_io_pending / io_worker_count if io_worker_count > 0 else 0

                    # ---- SCALE DECISION LOGIC ----
                    time_since_last_scale = now - io_last_scale_time
                    can_scale_normal = time_since_last_scale >= SCALE_COOLDOWN_SEC
                    can_scale_emergency = time_since_last_scale >= EMERGENCY_COOLDOWN_SEC

                    workers_to_add = 0
                    workers_to_remove = 0
                    reason = ""

                    # ==================== SCALE OUT LOGIC ====================

                    # PRIORITY 1: INPUT QUEUE PRESSURE
                    if io_pending_per_worker >= IO_QUEUE_PER_WORKER_HIGH:
                        if can_scale_emergency and not io_warmup_active:
                            workers_to_add = min(2, IO_MAX_WORKERS_ABSOLUTE - io_worker_count)
                            reason = f"QUEUE PRESSURE: {io_pending_per_worker:.0f} tasks/worker"
                            should_use_fast_check = True

                    # PRIORITY 2: EMERGENCY
                    elif (io_max_load >= IO_CRITICAL_LOAD or io_avg_queue >= IO_QUEUE_CRITICAL):
                        if can_scale_emergency and not io_warmup_active:
                            workers_to_add = min(2, IO_MAX_WORKERS_ABSOLUTE - io_worker_count)
                            reason = f"EMERGENCY: max={io_max_load:.1f}, queue={io_avg_queue:.1f}"
                            should_use_fast_check = True

                    # PRIORITY 3: MODERATE QUEUE + VELOCITY
                    elif io_pending_per_worker >= IO_QUEUE_PER_WORKER_MODERATE and io_velocity >= VELOCITY_HIGH:
                        if can_scale_normal and not io_warmup_active:
                            workers_to_add = 1
                            reason = f"QUEUE+VEL: {io_pending_per_worker:.0f} tasks/worker, vel={io_velocity:.2f}/s"

                    # PRIORITY 4: HIGH VELOCITY
                    elif io_velocity >= VELOCITY_CRITICAL and io_avg_load >= IO_MODERATE_LOAD:
                        if can_scale_normal and not io_warmup_active:
                            workers_to_add = 1
                            reason = f"HIGH VELOCITY: vel={io_velocity:.2f}/s"

                    # PRIORITY 5: HIGH LOAD
                    elif io_p90_load >= IO_HIGH_LOAD or io_avg_queue >= IO_QUEUE_HIGH:
                        if can_scale_normal and not io_warmup_active:
                            workers_to_add = 1
                            reason = f"HIGH: p90={io_p90_load:.1f}, queue={io_avg_queue:.1f}"

                    # PRIORITY 6: MODERATE LOAD + QUEUE
                    elif io_avg_load >= IO_MODERATE_LOAD and io_pending_per_worker >= 50:
                        if can_scale_normal and not io_warmup_active:
                            workers_to_add = 1
                            reason = f"MODERATE+QUEUE: load={io_avg_load:.1f}, queue={io_pending_per_worker:.0f}/worker"

                    # ==================== SCALE IN LOGIC ====================
                    elif (io_avg_load < IO_LOW_LOAD
                          and io_avg_queue < 3
                          and io_velocity <= 0
                          and io_pending_per_worker < 10
                          and input_queue_size < 20
                          and io_worker_count > self._config.io_bound_count):
                        if can_scale_normal:
                            workers_to_remove = 1
                            reason = f"SCALE IN: load={io_avg_load:.1f}, queue={io_pending_per_worker:.0f}/worker"

                    # ==================== EXECUTE SCALING ====================
                    if workers_to_add > 0 and io_worker_count < IO_MAX_WORKERS_ABSOLUTE:
                        actual_added = 0
                        for _ in range(workers_to_add):
                            if io_worker_count < IO_MAX_WORKERS_ABSOLUTE:
                                self._process_pool.add_worker(TaskType.IO_BOUND)
                                io_worker_count += 1
                                actual_added += 1

                        if actual_added > 0:
                            self._logger.warning(
                                f"[IO] Scale OUT +{actual_added} → {io_worker_count} workers | {reason}"
                            )
                            io_last_scale_time = now
                            last_worker_add_time["io"] = now

                            if len(io_load_history) > 6:
                                io_load_history = io_load_history[-6:]

                    elif workers_to_remove > 0:
                        self._process_pool.remove_worker(TaskType.IO_BOUND)
                        self._logger.info(
                            f"[IO] Scale IN -1 → {io_worker_count - 1} workers | {reason}"
                        )
                        io_last_scale_time = now
                        if len(io_load_history) > 6:
                            io_load_history = io_load_history[-6:]

                # ==================== UPDATE CHECK INTERVAL ====================
                if should_use_fast_check:
                    check_interval = FAST_CHECK_INTERVAL_SEC
                    is_fast_mode = True
                elif is_fast_mode and not should_use_fast_check:
                    check_interval = CHECK_INTERVAL_SEC
                    is_fast_mode = False

            except Exception as e:
                self._logger.error(f"Resource manager hatası: {e}", exc_info=True)
                time.sleep(2.0)

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

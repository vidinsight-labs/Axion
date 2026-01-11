# Axion - Mimari Dokümantasyon

**Axion v3.0** - Detaylı Mimari Analizi

Bu dokümantasyon, Axion'un mimari yapısını, bileşenlerini ve çalışma prensiplerini detaylı olarak açıklar.

## 📑 İçindekiler

1. [Sistem Mimarisi](#sistem-mimarisi)
2. [Temel Bileşenler](#temel-bileşenler)
3. [Auto-Scaling Mekanizması](#auto-scaling-mekanizması)
4. [Workflow Yönetimi](#workflow-yönetimi)
5. [Work Stealing Algoritması](#work-stealing-algoritması)
6. [Load Balancing](#load-balancing)
7. [Queue Yönetimi](#queue-yönetimi)
8. [Process İletişimi](#process-iletişimi)

---

## 🏗️ Sistem Mimarisi

### Genel Yapı

```
┌─────────────────────────────────────────────────────────┐
│                        ENGINE                            │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Resource Manager (Auto-Scaling)                   │ │
│  │  - Queue-aware scaling                             │ │
│  │  - Velocity-based prediction                       │ │
│  │  - Worker warm-up tracking                         │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌────────────┐    ┌────────────┐    ┌──────────────┐  │
│  │InputQueue  │ →  │QueueThread │ →  │ProcessPool   │  │
│  │(Tasks)     │    │            │    │(Dispatch)    │  │
│  └────────────┘    └────────────┘    └──────┬───────┘  │
│                                               │          │
│  ┌────────────┐    ┌────────────┐            │          │
│  │OutputQueue │ ←  │ResultThread│            │          │
│  │(Results)   │    │            │            │          │
│  └────────────┘    └────────────┘            │          │
│                                               │          │
│  ┌────────────────────────────────────────┐  │          │
│  │  Workflow Manager (DAG)                │  │          │
│  │  - Dependency tracking                 │  │          │
│  │  - Task chaining                       │  │          │
│  │  - Data passing                        │  │          │
│  └────────────────────────────────────────┘  │          │
│                                               │          │
│  ┌────────────────────────────────────────┐  │          │
│  │  Backpressure Controller               │  │          │
│  │  - CPU monitoring (psutil)             │  │          │
│  │  - Memory monitoring                   │  │          │
│  │  - Task rejection policy               │  │          │
│  └────────────────────────────────────────┘  │          │
└──────────────────────────────────────────────┼──────────┘
                                               │
                     ┌─────────────────────────┘
                     │
        ┌────────────┴──────────────┐
        │                           │
   ┌────▼──────┐             ┌──────▼────┐
   │ CPU POOL  │             │  IO POOL  │
   └───────────┘             └───────────┘
        │                           │
   ┌────┴────┐                 ┌────┴────┐
   │ Queue 0 │                 │ Queue 0 │
   │ Queue 1 │                 │ Queue 1 │
   │ Queue 2 │                 │ Queue 2 │
   │ Queue 3 │                 │ Queue 3 │
   └────┬────┘                 └────┬────┘
        │                           │
   ┌────▼────────┐             ┌────▼────────┐
   │ Worker 0    │             │ Worker 0    │
   │ ┌─────────┐ │             │ ┌─────────┐ │
   │ │Thread 1 │ │             │ │Thread 1 │ │
   │ └─────────┘ │             │ │Thread 2 │ │
   │ CPU Affinity│             │ │ ...     │ │
   │ Nice: 0     │             │ │Thread 20│ │
   └─────────────┘             │ Nice: 5   │
                               └───────────┘
        │                           │
        │                           │
   ┌────▼────────┐             ┌────▼────────┐
   │PythonExecutor              │PythonExecutor│
   │ - Module cache            │ - Module cache│
   │ - Script execution        │ - Script exec│
   └─────────────┘             └─────────────┘
```

### Katmanlar

1. **Engine Layer**: Merkezi kontrol, resource management, workflow yönetimi
2. **Pool Layer**: Worker yönetimi, load balancing, work stealing
3. **Process Layer**: Individual worker processes, CPU affinity, nice level
4. **Thread Layer**: Thread pool management, task execution
5. **Executor Layer**: Script execution, module caching

---

## 🔧 Temel Bileşenler

### 1. Engine (Merkezi Kontrol)

**Dosya**: `axion/engine/engine.py`

**Sorumluluklar**:
- ✅ Task submission ve result retrieval
- ✅ Queue processing coordination
- ✅ Auto-scaling orchestration
- ✅ Workflow management
- ✅ System health monitoring

**Önemli Thread'ler**:

```python
# Queue Processing Thread
def _process_queue_loop(self):
    """InputQueue'dan görev alır, ProcessPool'a gönderir"""
    while not shutdown:
        task = input_queue.get()
        process_pool.submit_task(task)

# Result Processing Thread
def _process_result_loop(self):
    """OutputQueue'dan sonuç alır, cache'e kaydeder, workflow'ları tetikler"""
    while not shutdown:
        result = output_queue.get()
        result_cache[result.task_id] = result
        new_tasks = workflow_manager.task_completed(result)
        for task in new_tasks:
            submit_task(task)

# Resource Manager Thread
def _resource_manager_loop(self):
    """Auto-scaling: Queue, load, velocity metriklerine göre worker ekler/çıkarır"""
    while not shutdown:
        analyze_metrics()
        make_scaling_decision()
        add_or_remove_workers()
```

### 2. ProcessPool (Worker Yönetimi)

**Dosya**: `axion/worker/pool.py`

**Sorumluluklar**:
- ✅ CPU ve IO worker'ları ayrı havuzlarda yönetir
- ✅ Sharded queues (her worker'ın kendi queue'su)
- ✅ Load-based task distribution
- ✅ Dynamic worker ekleme/çıkarma
- ✅ Worker metrics collection

**Özellikler**:

```python
class ProcessPool:
    # Sharded Queues
    _cpu_queues = [Queue0, Queue1, Queue2, ...]  # Her worker için ayrı
    _io_queues = [Queue0, Queue1, Queue2, ...]
    
    # Workers
    _cpu_workers = [Worker0, Worker1, Worker2, ...]
    _io_workers = [Worker0, Worker1, Worker2, ...]
    
    # Load Balancing
    def submit_task(self, task, task_type):
        workers = cpu_workers if CPU else io_workers
        
        # Score hesapla (her worker için)
        scores = []
        for worker in workers:
            active, queue_size, thread_queue = worker.metrics()
            cpu_usage = worker.cpu_usage
            
            if CPU_BOUND:
                score = queue * 0.6 + threads * 1.2 + cpu * 0.05
            else:
                score = queue * 1.0 + threads * 0.8 + cpu * 0.02
            
            scores.append(score)
        
        # En düşük score'lu worker'a gönder
        best_worker = min(workers, key=lambda w: score)
        best_worker.submit(task)
```

### 3. WorkerProcess (Individual Worker)

**Dosya**: `axion/worker/process.py`

**Sorumluluklar**:
- ✅ Process içinde ThreadPool yönetimi
- ✅ Task queue processing
- ✅ Work stealing (diğer worker queue'larından çalma)
- ✅ CPU affinity ve nice level ayarları
- ✅ Process metrics (psutil)

**Work Stealing Algoritması**:

```python
def _run_process(my_queue, all_queues, ...):
    while not shutdown:
        task = None
        
        # 1. Önce kendi queue'dan dene
        try:
            task = my_queue.get_nowait()
        except Empty:
            pass
        
        # 2. Kendi queue boşsa, başkalarından çal
        if task is None:
            # En dolu queue'ları bul
            victim_queues = sorted(all_queues, 
                                   key=lambda q: q.qsize(), 
                                   reverse=True)
            
            # En dolu olan'dan çal
            for victim in victim_queues:
                if victim != my_queue:
                    try:
                        task = victim.get_nowait()
                        break  # Bulduğumuz an dur
                    except Empty:
                        continue
        
        # 3. İşi çalıştır
        if task:
            thread_pool.submit_task(task)
        else:
            sleep(0.001)  # Biraz bekle
```

**Process Optimizations**:

```python
# CPU Affinity (worker'ı belirli CPU core'a sabitle)
if cpu_id is not None:
    os.sched_setaffinity(0, {cpu_id})  # Linux

# Nice Level (process önceliği)
os.nice(nice_level)
# nice=0:  CPU-bound (yüksek öncelik)
# nice=5:  IO-bound (düşük öncelik, CPU'yu bırakır)
```

### 4. ThreadPool (Thread Yönetimi)

**Dosya**: `axion/worker/thread.py`

**Sorumluluklar**:
- ✅ Worker process içinde thread pool
- ✅ Task queue processing
- ✅ Executor integration
- ✅ Active task counting
- ✅ Queue size tracking

```python
class ThreadPool:
    def _worker_loop(self):
        """Her thread bu loop'ta çalışır"""
        while not shutdown:
            # Queue'dan görev al
            task = task_queue.get(timeout=0.1)
            
            # Active count'u artır
            with lock:
                active_count += 1
            
            # Shared counter'ı güncelle (multiprocessing)
            with active_task_count.get_lock():
                active_task_count.value += 1
            
            try:
                # Task'ı çalıştır
                result = executor.execute(task, context)
                output_queue.put(result)
            finally:
                # Count'ları azalt
                active_count -= 1
                active_task_count.value -= 1
```

### 5. Workflow Manager (DAG)

**Dosya**: `axion/core/workflow.py`

**Sorumluluklar**:
- ✅ Task dependency tracking
- ✅ DAG (Directed Acyclic Graph) yönetimi
- ✅ Automatic task chaining
- ✅ Data passing between tasks

```python
class WorkflowManager:
    # Yapı
    _tasks: Dict[str, Task]                    # task_id → Task
    _dependency_graph: Dict[str, List[str]]    # task_id → [dependent_ids]
    _waiting_counts: Dict[str, int]            # task_id → waiting_count
    _results: Dict[str, Result]                # task_id → Result
    
    def add_workflow(self, tasks: List[Task]):
        """Workflow ekle"""
        for task in tasks:
            # Bağımlılık sayısını kaydet
            waiting_counts[task.id] = len(task.dependencies)
            
            # Reverse graph oluştur
            for dep_id in task.dependencies:
                dependency_graph[dep_id].append(task.id)
    
    def task_completed(self, result: Result) -> List[Task]:
        """Task tamamlandı, yeni task'ları döndür"""
        results[result.task_id] = result
        
        # Bu task'a bağımlı olanları bul
        dependents = dependency_graph[result.task_id]
        
        newly_ready = []
        for dep_id in dependents:
            waiting_counts[dep_id] -= 1
            
            # Tüm bağımlılıklar bittiyse
            if waiting_counts[dep_id] == 0:
                task = tasks[dep_id]
                
                # Veri aktarımı (upstream results)
                task.params['upstream_results'] = {}
                for dep in task.dependencies:
                    task.params['upstream_results'][dep] = results[dep].data
                
                newly_ready.append(task)
        
        return newly_ready
```

**Örnek Workflow**:

```python
# Task A: Veri indir
task_a = Task.create(
    script_path="download.py",
    params={"url": "https://api.example.com/data"}
)

# Task B: Veriyi işle (A'ya bağımlı)
task_b = Task.create(
    script_path="process.py",
    params={"operation": "transform"},
    dependencies=[task_a.id]
)

# Task C: Sonucu kaydet (B'ye bağımlı)
task_c = Task.create(
    script_path="save.py",
    params={"output": "result.json"},
    dependencies=[task_b.id]
)

# Workflow olarak gönder
engine.submit_workflow([task_a, task_b, task_c])

# Akış:
# 1. task_a çalışır → tamamlanır
# 2. task_b otomatik başlar (upstream_results['task_a_id'] = task_a sonucu)
# 3. task_c otomatik başlar (upstream_results['task_b_id'] = task_b sonucu)
```

### 6. Backpressure Controller

**Dosya**: `axion/core/backpressure.py`

**Sorumluluklar**:
- ✅ System resource monitoring
- ✅ Task rejection when overloaded
- ✅ Throttled health checks

```python
class BackpressureController:
    def check_health(self) -> SystemHealth:
        """Sistem sağlığını kontrol et (1 saniyede 1 kere)"""
        # CPU usage
        cpu_percent = psutil.cpu_percent()
        
        # Memory usage
        memory_percent = psutil.virtual_memory().percent
        
        # Karar
        if cpu_percent > 100 or memory_percent > 100:
            return SystemHealth.CRITICAL  # Görev reddet
        elif cpu_percent > 80:
            return SystemHealth.WARNING   # Dikkatli kabul et
        else:
            return SystemHealth.HEALTHY   # Normal kabul
    
    def should_accept_task(self) -> bool:
        """Görev kabul edilsin mi?"""
        health = self.check_health()
        return health != SystemHealth.CRITICAL
```

---

## ⚙️ Auto-Scaling Mekanizması

### Algoritma

**Dosya**: `axion/engine/engine.py:_resource_manager_loop()`

**Özellikler**:
- ✅ Queue-aware: Input queue boyutuna göre
- ✅ Load-aware: Worker yüküne göre
- ✅ Velocity-aware: Yük artış hızına göre
- ✅ Worker warm-up tracking: Yeni worker'lar hazır olana kadar bekle

### Mekanizma

```python
def _resource_manager_loop(self):
    """Auto-scaling loop - her 2 saniyede bir çalışır"""
    
    CHECK_INTERVAL = 2.0  # seconds
    FAST_CHECK_INTERVAL = 1.0  # kritik durumda
    
    # Thresholds
    CPU_MAX_WORKERS = min(cpu_count * 2, 16)
    IO_MAX_WORKERS = min(cpu_count * 3, 24)
    
    while not shutdown:
        sleep(check_interval)
        
        # Metrikleri topla
        input_queue_size = input_queue.qsize()
        cpu_worker_count = process_pool.get_worker_count(CPU_BOUND)
        io_worker_count = process_pool.get_worker_count(IO_BOUND)
        
        # Her worker için metrics
        cpu_metrics = process_pool.get_cpu_worker_metrics()
        io_metrics = process_pool.get_io_worker_metrics()
        
        # === CPU WORKER SCALING ===
        
        # Load hesapla
        cpu_loads = [m['total_load'] for m in cpu_metrics]
        cpu_avg_load = sum(cpu_loads) / cpu_worker_count
        cpu_max_load = max(cpu_loads)
        cpu_p75_load = percentile(cpu_loads, 0.75)
        
        # Queue pressure hesapla
        estimated_cpu_pending = input_queue_size * 0.5
        cpu_pending_per_worker = estimated_cpu_pending / cpu_worker_count
        
        # Velocity hesapla (trend)
        cpu_load_history.append(cpu_avg_load)
        if len(cpu_load_history) >= 5:
            recent_avg = mean(cpu_load_history[-3:])
            old_avg = mean(cpu_load_history[:3])
            cpu_velocity = (recent_avg - old_avg) / time_elapsed
        
        # SCALE OUT DECISION
        workers_to_add = 0
        
        # Priority 1: QUEUE PRESSURE
        if cpu_pending_per_worker >= 100:  # tasks/worker
            workers_to_add = min(2, CPU_MAX_WORKERS - cpu_worker_count)
            reason = f"QUEUE PRESSURE: {cpu_pending_per_worker:.0f} tasks/worker"
        
        # Priority 2: EMERGENCY LOAD
        elif cpu_max_load >= 10 and cpu_avg_usage >= 0.90:
            workers_to_add = min(2, CPU_MAX_WORKERS - cpu_worker_count)
            reason = f"EMERGENCY LOAD: max={cpu_max_load:.1f}"
        
        # Priority 3: HIGH VELOCITY
        elif cpu_velocity >= 5.0 and cpu_avg_load >= 3.5:
            workers_to_add = 1
            reason = f"HIGH VELOCITY: {cpu_velocity:.2f}/s"
        
        # Priority 4: HIGH LOAD
        elif cpu_p75_load >= 6.0 and cpu_avg_usage >= 0.75:
            workers_to_add = 1
            reason = f"HIGH LOAD: p75={cpu_p75_load:.1f}"
        
        # SCALE IN DECISION
        elif cpu_avg_load < 1.2 and cpu_pending_per_worker < 5:
            workers_to_remove = 1
            reason = f"SCALE IN: low load"
        
        # Execute scaling
        if workers_to_add > 0:
            for _ in range(workers_to_add):
                process_pool.add_worker(CPU_BOUND)
            logger.warning(f"[CPU] Scale OUT +{workers_to_add} → {cpu_worker_count + workers_to_add} | {reason}")
        
        # === IO WORKER SCALING ===
        # (Similar logic for IO workers)
```

### Scaling Strategy

| Durumu | Trigger | Action | Örnek |
|--------|---------|--------|-------|
| **Queue Pressure** | 100+ görev/worker | +2 worker | 10,000 görev geldi → hemen scale |
| **Emergency Load** | max_load ≥ 10 | +2 worker | Bir worker aşırı yüklü |
| **High Velocity** | velocity ≥ 5/s | +1 worker | Yük hızla artıyor |
| **High Load** | p75_load ≥ 6 | +1 worker | Çoğu worker yüklü |
| **Moderate Load** | avg_load ≥ 3.5 | +1 worker | Orta seviye yük |
| **Low Load** | avg_load < 1.2 | -1 worker | Yük düştü, scale-in |

### Velocity-Based Prediction

```python
# Load history tutulur
cpu_load_history = [1.0, 1.5, 2.0, 3.0, 4.5, 6.0, ...]

# Velocity hesaplanır
recent_avg = (4.5 + 6.0 + 7.5) / 3 = 6.0
old_avg = (1.0 + 1.5 + 2.0) / 3 = 1.5
time_diff = 6 iterations * 2 seconds = 12 seconds
velocity = (6.0 - 1.5) / 12 = 0.375 load/second = 3.75 load/10s

# Eğer velocity yüksekse (trend yukarı), proaktif scale-out
if velocity >= 5.0:
    # Yük hızla artıyor, hemen worker ekle
    add_worker()
```

---

## 🔄 Load Balancing

### Score-Based Algorithm

**Dosya**: `axion/worker/pool.py:submit_task()`

```python
def submit_task(self, task, task_type):
    """En az yüklü worker'a görev gönder"""
    
    workers = cpu_workers if task_type == CPU_BOUND else io_workers
    
    best_score = float('inf')
    best_worker_idx = None
    
    for i, worker in enumerate(workers):
        # Metrics topla
        active_threads, process_queue, thread_queue = worker.active_thread_count()
        cpu_usage = worker.process_metrics[CPU]
        
        # Load components
        thread_load = active_threads + thread_queue
        process_load = process_queue
        cpu_norm = cpu_usage / 100.0
        
        # Score hesapla
        if task_type == CPU_BOUND:
            # CPU: Thread saturation kritik
            score = (
                process_load * 0.6 +    # Queue büyüklüğü
                thread_load * 1.2 +     # Thread yükü (ağırlıklı)
                cpu_norm * 0.05         # CPU kullanımı (az ağırlıklı)
            )
        else:
            # IO: Queue doluluğu kritik
            score = (
                process_load * 1.0 +    # Queue büyüklüğü (ağırlıklı)
                thread_load * 0.8 +     # Thread yükü
                cpu_norm * 0.02         # CPU kullanımı (çok az)
            )
        
        if score < best_score:
            best_score = score
            best_worker_idx = i
    
    # En düşük score'lu worker'a gönder
    target_queue = queues[best_worker_idx]
    target_queue.put(task)
```

### Örnek Senaryo

```
Worker Status:
- Worker 0: 5 active threads, 10 queued tasks, 80% CPU
- Worker 1: 2 active threads, 3 queued tasks, 40% CPU
- Worker 2: 8 active threads, 15 queued tasks, 95% CPU

Score Calculation (CPU-bound):
- Worker 0: 10*0.6 + (5+0)*1.2 + 0.8*0.05 = 6 + 6 + 0.04 = 12.04
- Worker 1: 3*0.6 + (2+0)*1.2 + 0.4*0.05 = 1.8 + 2.4 + 0.02 = 4.22 ✅ (en düşük)
- Worker 2: 15*0.6 + (8+0)*1.2 + 0.95*0.05 = 9 + 9.6 + 0.048 = 18.65

→ Task Worker 1'e gönderilir
```

---

## 📊 Queue Yönetimi

### Sharded Queues

Her worker'ın kendi queue'su var (latency optimization):

```python
# ProcessPool
_cpu_queues = [Queue0, Queue1, Queue2, Queue3]  # 4 CPU worker
_io_queues = [Queue0, Queue1, ..., Queue7]      # 8 IO worker

# Task submission
best_worker_idx = 1  # Load balancing decision
cpu_queues[best_worker_idx].put(task)  # Worker 1'in queue'suna
```

**Avantajları**:
- ✅ Lock contention azalır (her queue bağımsız)
- ✅ Worker isolation (bir worker crash olsa diğerleri etkilenmez)
- ✅ Work stealing mümkün olur

### Input/Output Queues

```python
# Engine level (global)
input_queue = InputQueue(maxsize=1000)   # Task submission
output_queue = OutputQueue(maxsize=10000) # Result collection

# Kullanım
input_queue.put(task.to_dict())      # Engine → Queue
task_dict = input_queue.get()       # Queue → ProcessPool
output_queue.put(result.to_dict())  # Worker → Queue
result_dict = output_queue.get()    # Queue → Engine
```

---

## 🔗 Process İletişimi

### Multiprocessing Mechanisms

```python
# 1. Queue (task/result passing)
task_queue = multiprocessing.Queue()
task_queue.put(task_dict)
task_dict = task_queue.get()

# 2. Pipe (command/control)
cmd_pipe, child_pipe = multiprocessing.Pipe()
cmd_pipe.send({"command": "shutdown"})
message = child_pipe.recv()

# 3. Shared Memory (metrics)
active_task_count = multiprocessing.Value('i', 0)
with active_task_count.get_lock():
    active_task_count.value += 1

# 4. Array (process metrics)
process_metrics = multiprocessing.Array('d', [0.0, 0.0])  # [CPU, MEM]
process_metrics[0] = cpu_usage
process_metrics[1] = memory_usage
```

---

## 📈 Metrikler ve İzleme

### Worker Metrics

```python
# ProcessPool.get_status()
{
    "cpu_worker_tasks": {
        "cpu-0": {
            "active_tasks": 1,
            "queue_size": 5,
            "thread_pool_queue_size": 0,
            "total_load": 6,
            "cpu_usage": 85.3,
            "memory_mb": 120.5
        },
        "cpu-1": {...}
    },
    "io_worker_tasks": {
        "io-0": {...},
        ...
    }
}
```

### Engine Metrics

```python
# Engine.get_status()
{
    "engine": {
        "is_running": true
    },
    "components": {
        "input_queue": {
            "size": 150,
            "total_put": 10000,
            "total_dropped": 5
        },
        "output_queue": {
            "size": 2,
            "total_put": 9995,
            "total_get": 9993
        },
        "process_pool": {
            "cpu_bound_workers": 6,
            "io_bound_workers": 12,
            "cpu_active_threads": 6,
            "io_active_threads": 45
        }
    }
}
```

---

## 🎯 Özet

### Temel Prensipler

1. **Separation of Concerns**: CPU ve IO işler ayrı havuzlarda
2. **Sharded Queues**: Her worker'ın kendi queue'su
3. **Work Stealing**: Boş worker'lar yüklü worker'lardan çalar
4. **Auto-Scaling**: Queue, load, velocity bazlı dinamik ölçeklendirme
5. **Workflow Management**: DAG-based task dependencies
6. **Backpressure Control**: Sistem aşırı yüklüyse görev reddi

### Performans Optimizasyonları

- ✅ CPU Affinity: Worker'ları CPU core'larına sabitleme
- ✅ Nice Level: Process önceliklendirme
- ✅ Module Caching: Script'leri cache'leme
- ✅ Shared Memory: Metric collection overhead azaltma
- ✅ Score-Based Load Balancing: Intelligent task distribution
- ✅ Predictive Scaling: Velocity-based proactive scaling

### Scalability Features

- ✅ Dynamic worker addition/removal
- ✅ Queue-aware scaling (10,000 görev → hemen scale)
- ✅ Worker warm-up tracking
- ✅ Makul maksimum limitler (CPU: 16, IO: 24)
- ✅ Independent scaling (CPU ve IO ayrı)

---

## 📚 İlgili Dokümantasyon

- [Module Overview](./module_overview.md) - Genel bakış
- [Data Flow](./data_flow.md) - Veri akışı detayları
- [Examples Guide](./examples_guide.md) - Kullanım örnekleri
- [Output Interpretation](./output_interpretation.md) - Çıktı yorumlama

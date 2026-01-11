# Axion - Veri Akışı Dokümantasyonu

**Axion v3.0** - Detaylı Veri Akışı ve Dönüşümler

Bu dokümantasyon, Axion'da verilerin nasıl aktığını, dönüştüğünü ve takip edildiğini detaylı olarak açıklar.

## 📑 İçindekiler

1. [Veri Dönüşümleri](#veri-dönüşümleri)
2. [Process İletişimi](#process-iletişimi)
3. [Queue Yönetimi](#queue-yönetimi)
4. [Takip Mekanizmaları](#takip-mekanizmaları)
5. [Örnek Akışlar](#örnek-akışlar)
6. [Workflow Akışı](#workflow-akışı)

---

## 🔄 Veri Dönüşümleri

### 1. Task → Dict → Task

**Neden Dict?**
- Multiprocessing.Queue pickle kullanır
- Task objesi pickle edilebilir olmalı
- Dict formatı daha güvenli ve esnek
- Process'ler arası veri aktarımı için ideal

**Akış:**

```
Task Objesi (Python Object)
    │
    ├─► task.to_dict()
    │       │
    │       ▼
    │   Dict (JSON serializable)
    │   {
    │       "task_id": "abc-123-def-456",
    │       "script_path": "/path/to/script.py",
    │       "params": {"value": 42, "name": "test"},
    │       "task_type": "io_bound",
    │       "max_retries": 3,
    │       "dependencies": []
    │   }
    │       │
    │       ▼
    │   InputQueue.put() (multiprocessing.Queue)
    │       │
    │       ▼
    │   Queue'da saklanır (pickle serialization)
    │       │
    │       ▼
    │   Queue'dan alınır (pickle deserialization)
    │       │
    │       ▼
    │   Task.from_dict(dict)
    │       │
    │       ▼
    │   Task Objesi (yeniden oluşturulur)
```

**Kod Örneği:**

```python
# Task oluştur
task = Task.create(
    script_path="my_script.py",
    params={"value": 42},
    task_type=TaskType.IO_BOUND
)

# Dict'e dönüştür
task_dict = task.to_dict()
# {
#     "task_id": "abc-123...",
#     "script_path": "my_script.py",
#     "params": {"value": 42},
#     "task_type": "io_bound",
#     ...
# }

# Queue'ya ekle
input_queue.put(task_dict)

# Queue'dan al
task_dict = input_queue.get()

# Task objesine dönüştür
task = Task.from_dict(task_dict)
```

### 2. Result → Dict → Result

**Akış:**

```
Result Objesi (Python Object)
    │
    ├─► result.to_dict()
    │       │
    │       ▼
    │   Dict (JSON serializable)
    │   {
    │       "task_id": "abc-123-def-456",
    │       "status": "SUCCESS",  # veya "FAILED"
    │       "data": {"result": 84, "status": "ok"},
    │       "error": None,
    │       "started_at": "2024-01-01T12:00:00.123456+00:00",
    │       "completed_at": "2024-01-01T12:00:01.234567+00:00"
    │   }
    │       │
    │       ▼
    │   OutputQueue.put() (multiprocessing.Queue)
    │       │
    │       ▼
    │   Queue'da saklanır
    │       │
    │       ▼
    │   Queue'dan alınır
    │       │
    │       ▼
    │   Result.from_dict(dict)
    │       │
    │       ▼
    │   Result Objesi (yeniden oluşturulur)
```

**Kod Örneği:**

```python
# Result oluştur
result = Result.success(
    task_id="abc-123",
    data={"result": 84}
)

# Dict'e dönüştür
result_dict = result.to_dict()
# {
#     "task_id": "abc-123",
#     "status": "SUCCESS",
#     "data": {"result": 84},
#     ...
# }

# Queue'ya ekle
output_queue.put(result_dict)

# Queue'dan al
result_dict = output_queue.get()

# Result objesine dönüştür
result = Result.from_dict(result_dict)
```

---

## 🔗 Process İletişimi

### 1. Engine → WorkerProcess (Task Gönderme)

**İletişim Yöntemi:** Multiprocessing.Pipe + Sharded Queue

**Akış:**

```
Engine (Main Process)
    │
    ├─► ProcessPool.submit_task(task, TaskType.IO_BOUND)
    │       │
    │       ├─► Load Balancing
    │       │   → En az yüklü worker seç (score-based)
    │       │   → Örnek: io-1 seçildi
    │       │
    │       └─► io_queues[1].put(task.to_dict())
    │               │
    │               ▼
    │           Sharded Queue (Worker io-1'in kendi queue'su)
    │               │
    │               ▼
WorkerProcess io-1 (Child Process)
    │
    ├─► _run_process() loop
    │       │
    │       ├─► 1. Kendi queue'dan dene
    │       │   my_queue.get_nowait()
    │       │   → task_dict alındı!
    │       │
    │       └─► 2. Work Stealing (eğer kendi queue boşsa)
    │           for victim_queue in all_queues:
    │               if victim_queue != my_queue:
    │                   task_dict = victim_queue.get_nowait()
    │                   break
    │
    └─► ThreadPool.submit_task(task_dict)
```

**Sharded Queue Avantajları:**

- ✅ **Lock contention azalır**: Her worker'ın kendi queue'su var
- ✅ **Worker isolation**: Bir worker crash olsa diğerleri etkilenmez
- ✅ **Work stealing mümkün**: Boş worker başkasından çalabilir
- ✅ **Paralel processing**: Birden fazla worker aynı anda queue'dan alabilir

### 2. WorkerProcess → Engine (Result Gönderme)

**İletişim Yöntemi:** Multiprocessing.Queue (OutputQueue)

**Akış:**

```
WorkerProcess io-1 (Child Process)
    │
    ├─► ThreadPool._worker_loop()
    │       │
    │       ├─► PythonExecutor.execute(task, context)
    │       │       │
    │       │       ├─► Script yükle (module cache'den)
    │       │       ├─► main(params, context) çağır
    │       │       └─► Result.success(task_id, data)
    │       │
    │       └─► result.to_dict()
    │               │
    │               ▼
    │           output_queue.put(result_dict)
    │               │
    │               ▼
    │           Multiprocessing.Queue (shared)
    │               │
    │               ▼
Engine (Main Process)
    │
    ├─► _process_result_loop() (Background Thread)
    │       │
    │       ├─► output_queue.get(timeout=0.1)
    │       │       │
    │       │       ▼
    │       │   result_dict alındı
    │       │
    │       ├─► Result.from_dict(result_dict)
    │       │       │
    │       │       ▼
    │       │   Result objesi oluşturuldu
    │       │
    │       ├─► _result_cache[result.task_id] = result
    │       │       │
    │       │       ▼
    │       │   Cache'e kaydedildi (batch işlemler için)
    │       │
    │       └─► WorkflowManager.task_completed(result)
    │               │
    │               ▼
    │           Yeni hazır task'lar döndürülür
    │           → engine.submit_task(new_task)
```

**Shared Queue Avantajları:**

- ✅ **Centralized collection**: Tüm sonuçlar tek yerde toplanır
- ✅ **Order-independent**: Sonuçlar farklı sırada gelebilir
- ✅ **Cache mechanism**: Result cache ile batch işlemler optimize edilir

---

## 📊 Queue Yönetimi

### Queue Hiyerarşisi

```
┌─────────────────────────────────────────┐
│         Engine Level (Global)           │
│                                         │
│  ┌──────────────┐    ┌──────────────┐  │
│  │ InputQueue   │    │ OutputQueue  │  │
│  │ (Tasks)      │    │ (Results)    │  │
│  │ maxsize=1000 │    │ maxsize=10000│  │
│  └──────┬───────┘    └──────┬───────┘  │
└─────────┼────────────────────┼──────────┘
          │                    │
          │                    │
┌─────────┼────────────────────┼──────────┐
│         │                    │           │
│  ┌──────▼───────┐    ┌───────▼──────┐   │
│  │ ProcessPool  │    │ ProcessPool  │   │
│  │              │    │              │   │
│  │ CPU Queues:  │    │ IO Queues:   │   │
│  │ [Q0, Q1, Q2]│    │ [Q0, Q1, ...]│   │
│  └──────┬───────┘    └──────┬───────┘   │
│         │                    │           │
│         │                    │           │
│  ┌──────▼────────────────────▼───────┐  │
│  │     WorkerProcess (io-1)          │  │
│  │                                    │  │
│  │  ┌─────────────────────────────┐  │  │
│  │  │ ThreadPool                  │  │  │
│  │  │                             │  │  │
│  │  │ task_queue (thread-safe)   │  │  │
│  │  │ maxsize=max_threads         │  │  │
│  │  └─────────────────────────────┘  │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### Queue Boyutları

| Queue | Tip | Boyut | Açıklama |
|-------|-----|-------|----------|
| **InputQueue** | Global | 1000-5000 | Tüm görevler buraya gelir |
| **OutputQueue** | Global | 10000 | Tüm sonuçlar buraya gelir |
| **Sharded Queues** | Per-worker | Unlimited | Her worker'ın kendi queue'su |
| **ThreadPool Queue** | Per-worker | max_threads | Worker içinde thread pool queue |

### Queue Operations

**InputQueue:**

```python
# Non-blocking put
success = input_queue.put(task_dict)
if not success:
    raise TaskError("Queue dolu")

# Blocking get (timeout ile)
task_dict = input_queue.get(timeout=1.0)
```

**OutputQueue:**

```python
# Non-blocking put
success = output_queue.put(result_dict)
if not success:
    # Queue dolu, sonuç kaybolabilir (nadir)
    logger.warning("Output queue full")

# Blocking get (timeout ile)
result_dict = output_queue.get(timeout=0.1)
```

**Sharded Queue (Worker):**

```python
# Worker'ın kendi queue'su
my_queue = io_queues[worker_idx]

# Non-blocking get (work stealing için)
try:
    task = my_queue.get_nowait()
except queue.Empty:
    # Boş, başkasından çal
    pass
```

---

## 📈 Takip Mekanizmaları

### 1. Pending Tasks

**Lokasyon:** `Engine._pending_tasks`

**Amaç:** Gönderilen ama henüz tamamlanmamış görevleri takip et

```python
# Engine içinde
_pending_tasks: Dict[str, Task] = {}

# Görev gönderildiğinde
def submit_task(self, task: Task):
    input_queue.put(task.to_dict())
    _pending_tasks[task.id] = task  # ← Takip başlar

# Sonuç alındığında
def get_result(self, task_id: str):
    result = _result_cache.pop(task_id)
    _pending_tasks.pop(task_id, None)  # ← Takip biter
    return result
```

**Kullanım Senaryoları:**

- ✅ Görev durumu kontrolü
- ✅ Timeout yönetimi
- ✅ Cleanup işlemleri
- ✅ Debugging (hangi görevler bekliyor?)

### 2. Result Cache

**Lokasyon:** `Engine._result_cache`

**Amaç:** Batch işlemler için sonuçları cache'le

```python
# Engine içinde
_result_cache: Dict[str, Result] = {}

# Result processing thread
def _process_result_loop(self):
    result = output_queue.get()
    _result_cache[result.task_id] = result  # ← Cache'e kaydet
    
    # Cache limit kontrolü
    if len(_result_cache) > 5000:
        _result_cache.pop(next(iter(_result_cache)))  # FIFO eviction

# Result alma
def get_result(self, task_id: str):
    # 1. Cache'e bak
    if task_id in _result_cache:
        return _result_cache.pop(task_id)  # ← Cache'den al
    
    # 2. Queue'dan bekle
    while True:
        result = output_queue.get()
        if result.task_id == task_id:
            return result
        else:
            _result_cache[result.task_id] = result  # ← Başka görev için cache'le
```

**Kullanım Senaryoları:**

- ✅ Batch işlemler (10,000 görev → sonuçlar farklı sırada gelir)
- ✅ Hızlı sonuç erişimi (cache'den O(1))
- ✅ Queue sırası sorununu çözer (A görevi B'den önce biterse)

### 3. Component Metrics

**InputQueue Metrics:**

```python
_total_put: int = 0        # Toplam gönderilen görev
_total_dropped: int = 0    # Queue dolu olduğunda düşen görev

def put(self, item):
    try:
        self._queue.put_nowait(item)
        _total_put += 1
        return True
    except queue.Full:
        _total_dropped += 1  # ← Metrik güncellenir
        return False
```

**OutputQueue Metrics:**

```python
_total_put: int = 0        # Toplam eklenen sonuç
_total_get: int = 0        # Toplam alınan sonuç

def put(self, item):
    self._queue.put_nowait(item)
    _total_put += 1

def get(self, timeout):
    item = self._queue.get(timeout=timeout)
    _total_get += 1
    return item
```

**Worker Metrics:**

```python
# Shared memory (multiprocessing)
_active_task_count = multiprocessing.Value('i', 0)
thread_pool_queue_size = multiprocessing.Value('i', 0)
process_metrics = multiprocessing.Array('d', [0.0, 0.0])  # [CPU, MEM]

# Worker process içinde
with _active_task_count.get_lock():
    _active_task_count.value += 1  # ← Metrik güncellenir

# Main process'ten okuma
active_count = worker._active_task_count.value
cpu_usage = worker.process_metrics[0]
```

---

## 🔄 Örnek Akışlar

### Senaryo 1: Tek Görev (Basit)

```
1. Kullanıcı
   └─► task = Task.create(script_path, params, IO_BOUND)
       task.id = "abc-123"

2. Engine
   └─► engine.submit_task(task)
       ├─► task.to_dict() → {"task_id": "abc-123", ...}
       ├─► input_queue.put(task_dict)
       └─► _pending_tasks["abc-123"] = task

3. Queue Processing Thread
   └─► input_queue.get()
       ├─► task_dict alındı
       ├─► Task.from_dict(task_dict)
       └─► process_pool.submit_task(task, IO_BOUND)

4. ProcessPool
   └─► Load balancing
       ├─► io_workers = [io-0, io-1, io-2]
       ├─► Score hesapla (her worker için)
       ├─► io-1 seçildi (en düşük score)
       └─► io_queues[1].put(task_dict)

5. WorkerProcess io-1
   └─► _run_process() loop
       ├─► my_queue.get_nowait() → task_dict alındı
       └─► thread_pool.submit_task(task_dict)

6. ThreadPool (io-1 içinde)
   └─► _worker_loop()
       ├─► task = Task.from_dict(task_dict)
       ├─► context = ExecutionContext(task_id, worker_id)
       └─► executor.execute(task, context)

7. PythonExecutor
   └─► Script çalıştır
       ├─► module = _load_module("script.py")
       ├─► data = module.main(params, context)
       └─► Result.success("abc-123", data)

8. ThreadPool
   └─► result.to_dict()
       └─► output_queue.put(result_dict)

9. Result Processing Thread
   └─► output_queue.get()
       ├─► result_dict alındı
       ├─► Result.from_dict(result_dict)
       └─► _result_cache["abc-123"] = result

10. Kullanıcı
    └─► engine.get_result("abc-123")
        ├─► Cache'e bak: "abc-123" var!
        ├─► _result_cache.pop("abc-123")
        ├─► _pending_tasks.pop("abc-123")
        └─► Result döndürülür
```

### Senaryo 2: Batch İşlem (10,000 Görev)

```
1. Kullanıcı
   └─► 10,000 görev gönderilir
       for i in range(10000):
           task = Task.create(...)
           engine.submit_task(task)
       # Tüm görevler InputQueue'da

2. Auto-Scaling
   └─► Resource Manager Loop
       ├─► input_queue_size = 10,000
       ├─► cpu_pending_per_worker = 10,000 / 4 = 2,500
       ├─► QUEUE PRESSURE detected!
       └─► +2 CPU worker ekle (4 → 6)

3. Paralel İşleme
   └─► 6 CPU worker + 8 IO worker = 14 worker
       ├─► Her worker paralel çalışır
       ├─► Work stealing aktif (boş worker'lar çalıyor)
       └─► ~400 görev/saniye throughput

4. Sonuçlar Gelir (Farklı Sırada)
   └─► Görev 5000 sonucu gelir → Cache'e kaydedilir
   └─► Görev 123 sonucu gelir → Cache'e kaydedilir
   └─► Görev 9999 sonucu gelir → Cache'e kaydedilir
   └─► ... (tüm sonuçlar cache'lenir)

5. Kullanıcı
   └─► Sonuçları al
       for task_id in task_ids:
           result = engine.get_result(task_id)
           # Cache'den hızlıca alınır (O(1))
```

### Senaryo 3: Workflow (DAG)

```
1. Kullanıcı
   └─► Workflow gönder
       task_a = Task.create("download.py")
       task_b = Task.create("process.py", deps=[task_a.id])
       task_c = Task.create("save.py", deps=[task_b.id])
       
       engine.submit_workflow([task_a, task_b, task_c])

2. WorkflowManager
   └─► DAG oluştur
       ├─► _tasks = {a.id: a, b.id: b, c.id: c}
       ├─► _dependency_graph = {a.id: [b.id], b.id: [c.id]}
       └─► _waiting_counts = {a.id: 0, b.id: 1, c.id: 1}
       
       └─► Hazır task'ları gönder
           ├─► get_ready_tasks() → [task_a] (bağımlılığı yok)
           └─► engine.submit_task(task_a)

3. Task A Çalışır
   └─► Normal akış (Senaryo 1)
       └─► Result gelir

4. Result Processing Thread
   └─► WorkflowManager.task_completed(result_a)
       ├─► _results[task_a.id] = result_a
       ├─► _dependency_graph[task_a.id] → [task_b.id]
       ├─► _waiting_counts[task_b.id] -= 1 → 0
       ├─► task_b hazır!
       ├─► task_b.params['upstream_results'][task_a.id] = result_a.data
       └─► return [task_b]

5. Engine
   └─► Yeni task'ı gönder
       └─► engine.submit_task(task_b)

6. Task B Çalışır
   └─► Normal akış
       └─► upstream_results['task_a_id'] kullanılır

7. Task C Çalışır
   └─► Task B tamamlanınca otomatik başlar
       └─► upstream_results['task_b_id'] kullanılır
```

---

## 🔍 Özet

### Veri Dönüşümleri

1. **Task**: Object → Dict → Queue → Dict → Object
2. **Result**: Object → Dict → Queue → Dict → Object
3. **Pickle**: Process'ler arası serileştirme

### İletişim Yöntemleri

1. **InputQueue**: Engine → ProcessPool (global queue)
2. **Sharded Queues**: ProcessPool → WorkerProcess (per-worker)
3. **OutputQueue**: WorkerProcess → Engine (global queue)
4. **Pipe**: ProcessPool → WorkerProcess (komutlar için, eski)

### Takip Mekanizmaları

1. **Pending Tasks**: Gönderilen görevler
2. **Result Cache**: Tamamlanan görevler (batch için)
3. **Metrics**: Queue, worker, thread metrikleri
4. **Workflow State**: DAG durumu, bağımlılıklar

### Performans Optimizasyonları

- ✅ **Sharded Queues**: Lock contention azalır
- ✅ **Work Stealing**: Load balancing iyileşir
- ✅ **Result Cache**: Batch işlemler hızlanır
- ✅ **Module Cache**: Script yükleme hızlanır
- ✅ **Shared Memory**: Metric collection optimize edilir

---

## 📚 İlgili Dokümantasyon

- [Architecture](./architecture.md) - Mimari detayları
- [Module Overview](./module_overview.md) - Genel bakış
- [Examples Guide](./examples_guide.md) - Kullanım örnekleri

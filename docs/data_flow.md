# Veri Akışı - Detaylı Açıklama

Bu dokümantasyon, CPU Load Balancer'da verilerin nasıl aktığını, dönüştüğünü ve takip edildiğini gösterir.

## Veri Dönüşümleri

### 1. Task → Dict → Task

```
Task Objesi
    │
    ├─► task.to_dict()
    │       │
    │       ▼
    │   Dict (JSON serializable)
    │   {
    │       "task_id": "uuid",
    │       "script_path": "/path/to/script.py",
    │       "params": {"value": 42},
    │       "task_type": "io_bound",
    │       "max_retries": 3
    │   }
    │       │
    │       ▼
    │   InputQueue.put() (multiprocessing.Queue)
    │       │
    │       ▼
    │   Queue'da saklanır (pickle edilir)
    │       │
    │       ▼
    │   Queue'dan alınır
    │       │
    │       ▼
    │   Task.from_dict()
    │       │
    │       ▼
    │   Task Objesi (yeniden oluşturulur)
```

**Neden Dict?**
- Multiprocessing.Queue pickle kullanır
- Task objesi pickle edilebilir olmalı
- Dict formatı daha güvenli ve esnek

### 2. Result → Dict → Result

```
Result Objesi
    │
    ├─► result.to_dict()
    │       │
    │       ▼
    │   Dict (JSON serializable)
    │   {
    │       "task_id": "uuid",
    │       "status": "SUCCESS",
    │       "data": {...},
    │       "error": None,
    │       "started_at": "2024-01-01T12:00:00",
    │       "completed_at": "2024-01-01T12:00:01"
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
    │   Result.from_dict()
    │       │
    │       ▼
    │   Result Objesi (yeniden oluşturulur)
```

---

## Process İletişimi

### 1. Engine → WorkerProcess

```
Engine (Main Process)
    │
    ├─► ProcessPool.submit_task(task, task_type)
    │       │
    │       ▼
    │   WorkerProcess.submit_task(task)
    │       │
    │       ├─► task.to_dict() (Dict'e dönüştür)
    │       │
    │       └─► cmd_pipe.send({
    │               "command": "execute_task",
    │               "task": task_dict
    │           })
    │               │
    │               ▼
    │           Multiprocessing.Pipe (pickle)
    │               │
    │               ▼
WorkerProcess (Child Process)
    │
    ├─► cmd_pipe.recv()
    │       │
    │       ▼
    │   Task.from_dict(task_dict) (Dict'ten oluştur)
    │       │
    │       ▼
    │   ThreadPool.submit_task(task_dict)
```

**İletişim Yöntemi:**
- **Pipe**: Process'ler arası iletişim
- **Pickle**: Veri serileştirme
- **Dict formatı**: Güvenli veri aktarımı

### 2. WorkerProcess → Engine

```
WorkerProcess (Child Process)
    │
    ├─► PythonExecutor.execute(task, context)
    │       │
    │       ▼
    │   Result objesi oluşturulur
    │       │
    │       ▼
    │   result.to_dict() (Dict'e dönüştür)
    │       │
    │       ▼
    │   output_queue.put(result_dict)
    │       │
    │       ▼
    │   Multiprocessing.Queue (pickle)
    │       │
    │       ▼
Engine (Main Process)
    │
    ├─► output_queue.get()
    │       │
    │       ▼
    │   Result.from_dict(result_dict) (Dict'ten oluştur)
    │       │
    │       ▼
    │   Result cache'e kaydet veya döndür
```

**İletişim Yöntemi:**
- **Multiprocessing.Queue**: Process'ler arası queue
- **Pickle**: Veri serileştirme
- **Dict formatı**: Güvenli veri aktarımı

---

## Takip Mekanizmaları

### 1. Pending Tasks

```python
# Engine içinde
_pending_tasks: Dict[str, Task] = {}

# Görev gönderildiğinde
_pending_tasks[task.id] = task

# Sonuç alındığında
_pending_tasks.pop(task_id, None)
```

**Ne Takip Edilir:**
- Gönderilen ama henüz tamamlanmamış görevler
- Görev ID → Task objesi mapping

**Kullanım:**
- Görev durumu kontrolü
- Cleanup işlemleri
- Timeout yönetimi

### 2. Result Cache

```python
# Engine içinde
_result_cache: Dict[str, Result] = {}

# Queue'dan sonuç geldiğinde (istenen task değilse)
_result_cache[result.task_id] = result

# get_result() çağrıldığında
if task_id in _result_cache:
    return _result_cache.pop(task_id)
```

**Ne Takip Edilir:**
- Tamamlanmış görevlerin sonuçları
- Batch işlemler için kritik

**Kullanım:**
- Batch işlemlerde sonuç kaybını önler
- Hızlı sonuç erişimi
- Queue sırası sorununu çözer

### 3. Component Metrics

**InputQueue:**
```python
_total_put: int = 0      # Toplam gönderilen görev
_total_dropped: int = 0  # Düşen görev (queue dolu)
```

**OutputQueue:**
```python
_total_put: int = 0      # Toplam eklenen sonuç
_total_get: int = 0      # Toplam alınan sonuç
```

**ThreadPool:**
```python
_active_count: int = 0   # Aktif thread sayısı
```

**Kullanım:**
- Performans metrikleri
- Sistem sağlığı kontrolü
- Load balancing kararları

---

## Örnek: Tek Görev Akışı

### Adım 1: Görev Oluşturma

```python
task = Task.create(
    script_path="script.py",
    params={"value": 42},
    task_type=TaskType.IO_BOUND
)
# task.id = "abc-123-def-456"
```

### Adım 2: Görev Gönderme

```python
task_id = engine.submit_task(task)
# InputQueue'ya eklenir
# _pending_tasks["abc-123-def-456"] = task
# task_id = "abc-123-def-456" döndürülür
```

### Adım 3: Queue İşleme

```python
# _process_queue_loop() thread'i
task_dict = input_queue.get()
# task_dict = {
#     "task_id": "abc-123-def-456",
#     "script_path": "script.py",
#     "params": {"value": 42},
#     "task_type": "io_bound"
# }

task = Task.from_dict(task_dict)
process_pool.submit_task(task, TaskType.IO_BOUND)
```

### Adım 4: Load Balancing

```python
# ProcessPool
workers = io_workers  # [io-0, io-1, io-2, ...]
best_worker = min(workers, key=lambda w: w.active_thread_count())
# Örnek: io-1 seçildi (en az yüklü)

best_worker.submit_task(task)
```

### Adım 5: Worker İşleme

```python
# WorkerProcess (io-1)
cmd_pipe.send({
    "command": "execute_task",
    "task": task.to_dict()
})

# WorkerProcess içinde
thread_pool.submit_task(task_dict)
```

### Adım 6: Thread İşleme

```python
# ThreadPool (io-1 içinde)
task = Task.from_dict(task_dict)
context = ExecutionContext(
    task_id="abc-123-def-456",
    worker_id="io-1"
)
result = executor.execute(task, context)
output_queue.put(result.to_dict())
```

### Adım 7: Sonuç Alma

```python
# Engine
result = engine.get_result("abc-123-def-456", timeout=30)

# 1. Cache'e bak
if "abc-123-def-456" in _result_cache:
    return _result_cache.pop("abc-123-def-456")

# 2. Queue'dan al
item = output_queue.get(timeout=1.0)
result = Result.from_dict(item)

# 3. Aranan task mı?
if result.task_id == "abc-123-def-456":
    _pending_tasks.pop("abc-123-def-456", None)
    return result
else:
    # Cache'e kaydet
    _result_cache[result.task_id] = result
```

---

## Örnek: Batch Görev Akışı

### Senaryo: 5 Görev Aynı Anda

```python
# 1. Tüm görevler gönderilir
task_ids = []
for i in range(5):
    task = Task.create(...)
    task_id = engine.submit_task(task)
    task_ids.append(task_id)
# Tüm görevler InputQueue'da

# 2. Görevler paralel işlenir
# - Görev 0 → io-0 → thread-0
# - Görev 1 → io-1 → thread-1
# - Görev 2 → io-2 → thread-2
# - Görev 3 → io-0 → thread-1
# - Görev 4 → io-1 → thread-2

# 3. Sonuçlar gelir (sıra önemli değil)
# - Görev 2 sonucu gelir → Cache'e kaydedilir
# - Görev 0 sonucu gelir → Cache'e kaydedilir
# - Görev 4 sonucu gelir → Cache'e kaydedilir
# - Görev 1 sonucu gelir → Cache'e kaydedilir
# - Görev 3 sonucu gelir → Cache'e kaydedilir

# 4. Sonuçlar alınır
for task_id in task_ids:
    result = engine.get_result(task_id)
    # Cache'den hızlıca alınır (queue'dan değil)
```

**Önemli:**
- Görevler paralel işlenir
- Sonuçlar farklı sırada gelebilir
- Cache sayesinde sonuç kaybı olmaz
- Batch işlemler çok hızlıdır

---

## Veri Güvenliği

### 1. Thread Safety

- **Lock kullanımı**: Kritik bölgelerde `Lock` kullanılır
- **Queue thread-safe**: Multiprocessing.Queue thread-safe
- **Dict operations**: Lock ile korunur

### 2. Process Safety

- **Pickle**: Process'ler arası veri aktarımı için
- **Queue**: Process'ler arası iletişim için
- **Pipe**: Process'ler arası komut gönderimi için

### 3. Error Handling

- **Try-except**: Her seviyede hata yakalanır
- **Failed Result**: Hata durumunda Result.failed() oluşturulur
- **Graceful shutdown**: Tüm kaynaklar temizlenir

---

## Özet

### Veri Akışı
1. **Task** → Dict → Queue → Dict → **Task**
2. **Result** → Dict → Queue → Dict → **Result**
3. Process'ler arası: Pipe + Queue
4. Thread'ler arası: Queue

### Takip
1. **Pending tasks**: Gönderilen görevler
2. **Result cache**: Tamamlanan görevler
3. **Metrics**: Performans metrikleri
4. **Status**: Component durumları

### Güvenlik
1. **Thread safety**: Lock kullanımı
2. **Process safety**: Pickle + Queue
3. **Error handling**: Try-except + Failed result


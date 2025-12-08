# CPU Load Balancer - Mimari Dokümantasyon

Bu dokümantasyon, CPU Load Balancer modülünün mimarisini, parçalarını, girdi/çıktı akışını ve takip mekanizmalarını detaylı olarak açıklar.

## İçindekiler

1. [Modül Yapısı](#modül-yapısı)
2. [Ana Bileşenler](#ana-bileşenler)
3. [Girdi Akışı (Input Flow)](#girdi-akışı)
4. [Çıktı Akışı (Output Flow)](#çıktı-akışı)
5. [Takip ve İzleme](#takip-ve-izleme)
6. [Veri Yapıları](#veri-yapıları)

---

## Modül Yapısı

```
cpu_load_balancer/
├── engine/              # Ana motor
│   └── engine.py       # Engine sınıfı (merkezi kontrol)
├── config/              # Yapılandırma
│   └── __init__.py      # EngineConfig
├── task/                # Görev tanımları
│   ├── task.py          # Task sınıfı
│   └── result.py        # Result sınıfı
├── queue/               # Kuyruklar
│   ├── input_queue.py  # Girdi kuyruğu
│   └── output_queue.py # Çıktı kuyruğu
├── worker/              # İşçi süreçleri
│   ├── pool.py          # ProcessPool (yönetim)
│   ├── process.py       # WorkerProcess (süreç)
│   └── thread.py        # ThreadPool (thread yönetimi)
├── executer/            # Çalıştırıcılar
│   └── python_executor.py # Python script executor
├── core/                # Temel sınıflar
│   ├── enums.py         # TaskType, TaskStatus
│   └── exceptions.py    # Hata sınıfları
└── status.py            # Durum takibi
```

---

## Ana Bileşenler

### 1. Engine (Ana Motor)

**Dosya:** `engine/engine.py`

**Sorumluluklar:**
- Sistemin merkezi kontrol noktası
- Görev gönderme (`submit_task`)
- Sonuç alma (`get_result`)
- Sistem durumu (`get_status`)
- Queue işleme thread'i yönetimi

**Önemli Özellikler:**
- Result cache (batch işlemler için)
- Pending tasks takibi
- Graceful shutdown

### 2. Config (Yapılandırma)

**Dosya:** `config/__init__.py`

**Sorumluluklar:**
- Tüm sistem ayarlarını içerir
- Worker sayıları
- Queue boyutları
- Timeout değerleri

### 3. Queue'lar

**InputQueue** (`queue/input_queue.py`):
- Görevlerin gönderildiği kuyruk
- Multiprocessing.Queue kullanır
- Non-blocking put/get

**OutputQueue** (`queue/output_queue.py`):
- Sonuçların toplandığı kuyruk
- Multiprocessing.Queue kullanır
- Blocking get (timeout ile)

### 4. Worker Pool

**ProcessPool** (`worker/pool.py`):
- CPU-bound ve IO-bound worker'ları yönetir
- Load balancing yapar
- En az yüklü worker'ı seçer

**WorkerProcess** (`worker/process.py`):
- Tek bir worker process'i
- ThreadPool'u yönetir
- Process içi iletişim (Pipe)

**ThreadPool** (`worker/thread.py`):
- Worker process içinde thread yönetimi
- Görevleri thread'lere dağıtır
- Executor'ı çağırır

### 5. Executor

**PythonExecutor** (`executer/python_executor.py`):
- Python script'lerini çalıştırır
- `main(params, context)` fonksiyonunu arar
- Module cache kullanır

### 6. Task & Result

**Task** (`task/task.py`):
- Görev tanımı
- Script path, parametreler, tip
- Dict'e dönüştürülebilir (queue için)

**Result** (`task/result.py`):
- Görev sonucu
- Başarılı/başarısız durum
- Hata bilgileri
- Dict'e dönüştürülebilir (queue için)

---

## Girdi Akışı (Input Flow)

### Adım Adım Akış

```
1. Kullanıcı
   │
   ├─► Task.create(script_path, params, task_type)
   │       │
   │       ▼
   │   Task objesi oluşturulur
   │   - id: UUID
   │   - script_path: "/path/to/script.py"
   │   - params: {"value": 42}
   │   - task_type: TaskType.IO_BOUND
   │
   ├─► Engine.submit_task(task)
   │       │
   │       ├─► InputQueue.put(task.to_dict())
   │       │       │
   │       │       ▼
   │       │   Queue'ya eklenir (multiprocessing.Queue)
   │       │
   │       └─► _pending_tasks[task.id] = task
   │               │
   │               ▼
   │           Pending listesine eklenir (takip için)
   │
   └─► task_id döndürülür
```

### Detaylı Akış

#### 1. Görev Oluşturma

```python
task = Task.create(
    script_path="my_script.py",
    params={"value": 42},
    task_type=TaskType.IO_BOUND
)
```

**Ne Olur:**
- Task objesi oluşturulur
- UUID ile benzersiz ID atanır
- Varsayılan değerler ayarlanır

#### 2. Görev Gönderme

```python
task_id = engine.submit_task(task)
```

**Ne Olur:**
1. Task → Dict'e dönüştürülür (`task.to_dict()`)
2. InputQueue'ya eklenir (`input_queue.put()`)
3. Pending listesine eklenir (`_pending_tasks[task.id] = task`)
4. Task ID döndürülür

#### 3. Queue İşleme

```python
# _process_queue_loop() thread'i sürekli çalışır
while not shutdown:
    task_dict = input_queue.get(timeout=1.0)
    task = Task.from_dict(task_dict)
    process_pool.submit_task(task, task.task_type)
```

**Ne Olur:**
1. Queue'dan görev alınır
2. Task objesi oluşturulur
3. ProcessPool'a gönderilir

#### 4. Load Balancing

```python
# ProcessPool.submit_task()
if task_type == CPU_BOUND:
    workers = cpu_workers
else:
    workers = io_workers

best_worker = min(workers, key=lambda w: w.active_thread_count())
best_worker.submit_task(task)
```

**Ne Olur:**
1. Görev tipine göre worker listesi seçilir
2. En az yüklü worker bulunur
3. Görev o worker'a gönderilir

#### 5. Worker İşleme

```python
# WorkerProcess.submit_task()
cmd_pipe.send({
    "command": "execute_task",
    "task": task.to_dict()
})

# WorkerProcess içinde
thread_pool.submit_task(task_dict)
```

**Ne Olur:**
1. Görev process içine gönderilir (Pipe ile)
2. ThreadPool'a eklenir
3. Thread pool'dan bir thread görevi alır

#### 6. Execution

```python
# ThreadPool._worker_loop()
task = Task.from_dict(task_dict)
context = ExecutionContext(task_id=task.id, worker_id=worker_id)
result = executor.execute(task, context)
output_queue.put(result.to_dict())
```

**Ne Olur:**
1. Task objesi oluşturulur
2. ExecutionContext oluşturulur
3. PythonExecutor script'i çalıştırır
4. Sonuç OutputQueue'ya eklenir

---

## Çıktı Akışı (Output Flow)

### Adım Adım Akış

```
1. Worker Thread
   │
   ├─► PythonExecutor.execute(task, context)
   │       │
   │       ├─► Script yüklenir
   │       ├─► main(params, context) çağrılır
   │       └─► Sonuç döndürülür
   │
   ├─► Result.success(task_id, data)
   │       │
   │       ▼
   │   Result objesi oluşturulur
   │   - task_id: "uuid"
   │   - status: TaskStatus.COMPLETED
   │   - data: {...}
   │
   ├─► OutputQueue.put(result.to_dict())
   │       │
   │       ▼
   │   Queue'ya eklenir (multiprocessing.Queue)
   │
   └─► Engine.get_result(task_id)
           │
           ├─► Result cache'e bak
           │       │
           │       └─► Cache'de varsa: Döndür
           │
           └─► OutputQueue.get(timeout)
                   │
                   ├─► Sonuç gelirse
                   │       │
                   │       ├─► Aranan task_id mi?
   │       │       │
   │       │       ├─► Evet: Döndür
   │       │       └─► Hayır: Cache'e kaydet
   │       │
   │       └─► Timeout: None döndür
```

### Detaylı Akış

#### 1. Script Çalıştırma

```python
# PythonExecutor.execute()
module = _load_module(script_path)
data = module.main(task.params, context)
return Result.success(task_id, data)
```

**Ne Olur:**
1. Script modül olarak yüklenir
2. `main(params, context)` fonksiyonu çağrılır
3. Sonuç alınır
4. Result objesi oluşturulur

#### 2. Sonuç Queue'ya Ekleme

```python
# ThreadPool._worker_loop()
result = executor.execute(task, context)
output_queue.put(result.to_dict())
```

**Ne Olur:**
1. Result → Dict'e dönüştürülür
2. OutputQueue'ya eklenir
3. Queue multiprocessing üzerinden paylaşılır

#### 3. Sonuç Alma

```python
# Engine.get_result(task_id)
# 1. Cache'e bak
if task_id in _result_cache:
    return _result_cache.pop(task_id)

# 2. Queue'dan al
while True:
    item = output_queue.get(timeout=1.0)
    result = Result.from_dict(item)
    
    if result.task_id == task_id:
        return result
    else:
        # Başka bir görevin sonucu, cache'e kaydet
        _result_cache[result.task_id] = result
```

**Ne Olur:**
1. Önce cache'e bakılır (batch işlemler için)
2. Cache'de yoksa queue'dan alınır
3. Aranan task_id ise döndürülür
4. Değilse cache'e kaydedilir (başka görev için)

---

## Takip ve İzleme

### 1. Pending Tasks Takibi

```python
# Engine içinde
_pending_tasks: Dict[str, Task] = {}
```

**Ne Takip Edilir:**
- Gönderilen ama henüz tamamlanmamış görevler
- Görev ID → Task objesi mapping

**Kullanım:**
- Görev durumu kontrolü
- Cleanup işlemleri

### 2. Result Cache

```python
# Engine içinde
_result_cache: Dict[str, Result] = {}
```

**Ne Takip Edilir:**
- Tamamlanmış görevlerin sonuçları
- Batch işlemler için önemli

**Kullanım:**
- Batch işlemlerde sonuç kaybını önler
- Hızlı sonuç erişimi

### 3. Component Status

Her component'in `get_status()` metodu var:

```python
# InputQueue
status = input_queue.get_status()
# {
#     "name": "input_queue",
#     "health": "healthy",
#     "metrics": {
#         "size": 5,
#         "maxsize": 1000,
#         "total_put": 100,
#         "total_dropped": 0
#     }
# }
```

**Takip Edilen Metrikler:**

**InputQueue:**
- `size`: Queue'daki görev sayısı
- `maxsize`: Maksimum kapasite
- `total_put`: Toplam gönderilen görev
- `total_dropped`: Düşen görev (queue dolu)

**OutputQueue:**
- `size`: Queue'daki sonuç sayısı
- `maxsize`: Maksimum kapasite
- `total_put`: Toplam eklenen sonuç
- `total_get`: Toplam alınan sonuç

**ProcessPool:**
- `total_workers`: Toplam worker sayısı
- `cpu_workers`: CPU-bound worker sayısı
- `io_workers`: IO-bound worker sayısı

### 4. Engine Status

```python
status = engine.get_status()
# {
#     "engine": {
#         "is_running": True
#     },
#     "components": {
#         "input_queue": {...},
#         "output_queue": {...},
#         "process_pool": {...}
#     }
# }
```

**Ne Takip Edilir:**
- Engine çalışma durumu
- Tüm component'lerin durumu
- Sistem sağlığı

---

## Veri Yapıları

### Task (Görev)

```python
@dataclass
class Task:
    id: str                    # UUID
    script_path: str           # Script dosya yolu
    params: Dict[str, Any]     # Parametreler
    task_type: TaskType        # CPU_BOUND veya IO_BOUND
    status: TaskStatus         # PENDING, RUNNING, COMPLETED, FAILED
    max_retries: int           # Maksimum deneme sayısı
    retry_count: int           # Mevcut deneme sayısı
    created_at: datetime       # Oluşturulma zamanı
```

**Queue Formatı (Dict):**
```python
{
    "task_id": "uuid",
    "script_path": "/path/to/script.py",
    "params": {"value": 42},
    "task_type": "io_bound",
    "max_retries": 3
}
```

### Result (Sonuç)

```python
@dataclass
class Result:
    task_id: str                      # Görev ID'si
    status: TaskStatus                # COMPLETED veya FAILED
    data: Any                         # Sonuç verisi
    error: Optional[str]              # Hata mesajı (varsa)
    error_details: Optional[Dict]     # Detaylı hata (varsa)
    started_at: Optional[datetime]    # Başlangıç zamanı
    completed_at: datetime            # Bitiş zamanı
```

**Queue Formatı (Dict):**
```python
{
    "task_id": "uuid",
    "status": "SUCCESS",  # veya "FAILED"
    "data": {...},
    "error": None,
    "started_at": "2024-01-01T12:00:00",
    "completed_at": "2024-01-01T12:00:01"
}
```

### ExecutionContext

```python
class ExecutionContext:
    task_id: str      # Görev ID'si
    worker_id: str    # Worker ID'si (örn: "io-0")
```

**Kullanım:**
- Script'lere geçirilir
- Script içinde görev ve worker bilgisine erişim sağlar

---

## Tam Akış Diyagramı

```
┌─────────────┐
│  Kullanıcı  │
└──────┬──────┘
       │
       │ 1. Task.create()
       ▼
┌─────────────┐
│    Task     │ (id, script_path, params, task_type)
└──────┬──────┘
       │
       │ 2. engine.submit_task(task)
       ▼
┌─────────────┐
│   Engine    │
│             │
│  ┌────────┐ │
│  │InputQ  │ │ 3. input_queue.put(task_dict)
│  └────┬───┘ │
│       │     │
│       │     │ 4. _process_queue_loop() (Thread)
│       │     │    input_queue.get() → process_pool.submit_task()
│       │     │
└───────┼─────┘
        │
        │ 5. ProcessPool (Load Balancing)
        ▼
┌─────────────┐
│ProcessPool │
│            │
│ ┌────────┐ │
│ │CPU     │ │ 6. En az yüklü worker seç
│ │Workers │ │
│ └───┬────┘ │
│     │      │
│ ┌───▼────┐ │
│ │IO      │ │
│ │Workers │ │
│ └───┬────┘ │
└─────┼──────┘
      │
      │ 7. WorkerProcess.submit_task()
      ▼
┌─────────────┐
│WorkerProcess│
│             │
│ ┌─────────┐ │
│ │ThreadPool│ │ 8. thread_pool.submit_task()
│ └────┬────┘ │
│      │      │
│      │      │ 9. Thread alır görevi
│      │      │
│      │      │ 10. PythonExecutor.execute()
│      │      │
│      │      │ 11. Script çalıştırılır
│      │      │    main(params, context)
│      │      │
│      │      │ 12. Result oluşturulur
│      │      │
│      └──────┼──► 13. output_queue.put(result_dict)
│             │
└─────────────┘
      │
      │ 14. output_queue.get()
      ▼
┌─────────────┐
│   Engine    │
│             │
│  ┌────────┐ │
│  │OutputQ │ │ 15. Result cache'e kaydet (batch için)
│  └────┬───┘ │
│       │     │
│       │     │ 16. engine.get_result(task_id)
│       │     │    Cache'den veya queue'dan al
│       │     │
└───────┼─────┘
        │
        │ 17. Result döndür
        ▼
┌─────────────┐
│  Kullanıcı  │
└─────────────┘
```

---

## Önemli Noktalar

### 1. Paralel İşleme

- **Process seviyesi**: Her worker ayrı bir process
- **Thread seviyesi**: Her worker içinde birden fazla thread
- **Load balancing**: Görevler en az yüklü worker'a gönderilir

### 2. Queue Yönetimi

- **InputQueue**: Görevlerin gönderildiği yer
- **OutputQueue**: Sonuçların toplandığı yer
- **Multiprocessing.Queue**: Process'ler arası iletişim

### 3. Result Cache

- Batch işlemler için kritik
- Queue'dan gelen sonuçlar cache'lenir
- İstenen task_id değilse cache'e kaydedilir

### 4. Takip Mekanizmaları

- **Pending tasks**: Gönderilen görevler
- **Result cache**: Tamamlanan görevler
- **Component status**: Her component'in durumu
- **Metrics**: Queue boyutları, görev sayıları

---

## Özet

### Girdi (Input)
1. Task oluştur → `Task.create()`
2. Engine'e gönder → `engine.submit_task()`
3. InputQueue'ya ekle
4. Queue processing thread alır
5. ProcessPool'a gönder (load balancing)
6. Worker'a dağıt
7. Thread'e ver
8. Executor çalıştır

### Çıktı (Output)
1. Executor sonuç döndürür
2. Result objesi oluşturulur
3. OutputQueue'ya eklenir
4. Engine queue'dan alır
5. Cache'e kaydedilir (batch için)
6. Kullanıcı `get_result()` ile alır

### Takip
- Pending tasks: Gönderilen görevler
- Result cache: Tamamlanan görevler
- Component status: Sistem durumu
- Metrics: Performans metrikleri


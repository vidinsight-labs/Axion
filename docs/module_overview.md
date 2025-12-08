# CPU Load Balancer - Modül Özeti

Bu dokümantasyon, CPU Load Balancer modülünün hızlı bir özetini sunar.

## 📦 Modül Parçaları

### Ana Bileşenler

```
cpu_load_balancer/
│
├── 🔧 Engine (engine/)
│   └── engine.py          # Ana kontrol merkezi
│
├── ⚙️ Config (config/)
│   └── __init__.py        # EngineConfig - tüm ayarlar
│
├── 📋 Task (task/)
│   ├── task.py            # Task - görev tanımı
│   └── result.py          # Result - sonuç tanımı
│
├── 📬 Queue (queue/)
│   ├── input_queue.py     # InputQueue - görev kuyruğu
│   └── output_queue.py    # OutputQueue - sonuç kuyruğu
│
├── 👷 Worker (worker/)
│   ├── pool.py            # ProcessPool - worker yönetimi
│   ├── process.py         # WorkerProcess - tek worker process
│   └── thread.py          # ThreadPool - thread yönetimi
│
├── 🚀 Executer (executer/)
│   └── python_executor.py # PythonExecutor - script çalıştırıcı
│
├── 🎯 Core (core/)
│   ├── enums.py           # TaskType, TaskStatus
│   └── exceptions.py      # Hata sınıfları
│
└── 📊 Status (status.py)
    └── ComponentStatus    # Component durumu
```

---

## 🔄 Girdi Nasıl Oluyor?

### 1. Görev Oluşturma

```python
task = Task.create(
    script_path="my_script.py",
    params={"value": 42},
    task_type=TaskType.IO_BOUND
)
```

**Ne Olur:**
- Task objesi oluşturulur
- Benzersiz ID atanır (UUID)
- Parametreler ve tip belirlenir

### 2. Görev Gönderme

```python
task_id = engine.submit_task(task)
```

**Akış:**
```
Task → Dict → InputQueue → Queue Processing Thread
                                    ↓
                            ProcessPool (Load Balancing)
                                    ↓
                            WorkerProcess (En az yüklü)
                                    ↓
                            ThreadPool (Thread seçimi)
                                    ↓
                            PythonExecutor (Script çalıştırma)
```

**Adımlar:**
1. Task → Dict'e dönüştürülür
2. InputQueue'ya eklenir
3. Queue processing thread alır
4. ProcessPool'a gönderilir (load balancing)
5. En az yüklü worker seçilir
6. Worker process'e gönderilir
7. Thread pool'dan thread alınır
8. Executor script'i çalıştırır

---

## 📤 Çıktı Nasıl Oluyor?

### 1. Sonuç Oluşturma

```python
# PythonExecutor içinde
result = Result.success(task_id, data)
# veya
result = Result.failed(task_id, error)
```

**Ne Olur:**
- Result objesi oluşturulur
- Başarılı/başarısız durum belirlenir
- Veri veya hata mesajı eklenir

### 2. Sonuç Queue'ya Ekleme

```python
# ThreadPool içinde
output_queue.put(result.to_dict())
```

**Akış:**
```
Result → Dict → OutputQueue → Engine.get_result()
                                        ↓
                                Cache veya Queue'dan al
                                        ↓
                                Result objesi döndürülür
```

**Adımlar:**
1. Result → Dict'e dönüştürülür
2. OutputQueue'ya eklenir
3. Engine queue'dan alır
4. Cache'e kaydedilir (batch için)
5. Kullanıcı `get_result()` ile alır

### 3. Sonuç Alma

```python
result = engine.get_result(task_id, timeout=30.0)
```

**Akış:**
1. Önce cache'e bakılır
2. Cache'de yoksa queue'dan alınır
3. Aranan task_id ise döndürülür
4. Değilse cache'e kaydedilir (başka görev için)

---

## 📊 Nasıl Takip Ediliyor?

### 1. Pending Tasks

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
- Batch işlemler için kritik

**Kullanım:**
- Batch işlemlerde sonuç kaybını önler
- Hızlı sonuç erişimi

### 3. Component Status

Her component'in `get_status()` metodu var:

```python
status = engine.get_status()
# {
#     "engine": {"is_running": True},
#     "components": {
#         "input_queue": {
#             "health": "healthy",
#             "metrics": {
#                 "size": 5,
#                 "total_put": 100,
#                 "total_dropped": 0
#             }
#         },
#         "output_queue": {...},
#         "process_pool": {...}
#     }
# }
```

**Takip Edilen Metrikler:**

| Component | Metrikler |
|-----------|-----------|
| **InputQueue** | size, total_put, total_dropped |
| **OutputQueue** | size, total_put, total_get |
| **ProcessPool** | total_workers, cpu_workers, io_workers |
| **Engine** | is_running |

### 4. Worker Metrics

```python
# ThreadPool içinde
_active_count: int = 0  # Aktif thread sayısı
```

**Kullanım:**
- Load balancing kararları
- Worker yükü hesaplama

---

## 🔄 Tam Akış Özeti

### Girdi → İşleme → Çıktı

```
┌─────────────┐
│  Kullanıcı  │
└──────┬──────┘
       │
       │ 1. Task.create()
       │    script_path, params, task_type
       ▼
┌─────────────┐
│    Task     │
└──────┬──────┘
       │
       │ 2. engine.submit_task(task)
       │    → task.to_dict()
       │    → InputQueue.put()
       │    → _pending_tasks[task.id] = task
       ▼
┌─────────────┐
│ InputQueue  │ (Multiprocessing.Queue)
└──────┬──────┘
       │
       │ 3. _process_queue_loop() (Thread)
       │    → InputQueue.get()
       │    → Task.from_dict()
       │    → ProcessPool.submit_task()
       ▼
┌─────────────┐
│ProcessPool  │
│             │
│ Load Balance│ → En az yüklü worker seç
│             │
└──────┬──────┘
       │
       │ 4. WorkerProcess.submit_task()
       │    → Pipe ile gönder
       │    → ThreadPool.submit_task()
       ▼
┌─────────────┐
│ThreadPool   │
│             │
│ Thread seç  │ → Boş thread bul
│             │
└──────┬──────┘
       │
       │ 5. PythonExecutor.execute()
       │    → Script yükle
       │    → main(params, context) çağır
       │    → Result oluştur
       ▼
┌─────────────┐
│   Result    │
└──────┬──────┘
       │
       │ 6. OutputQueue.put()
       │    → result.to_dict()
       │    → Queue'ya ekle
       ▼
┌─────────────┐
│OutputQueue  │ (Multiprocessing.Queue)
└──────┬──────┘
       │
       │ 7. engine.get_result(task_id)
       │    → Cache'e bak
       │    → Queue'dan al
       │    → Cache'e kaydet (gerekirse)
       ▼
┌─────────────┐
│   Result    │
└──────┬──────┘
       │
       │ 8. Kullanıcıya döndür
       ▼
┌─────────────┐
│  Kullanıcı  │
└─────────────┘
```

---

## 📈 Takip Noktaları

### 1. Görev Takibi

```python
# Görev gönderildiğinde
_pending_tasks[task_id] = task

# Sonuç alındığında
_pending_tasks.pop(task_id, None)
```

**Ne Takip Edilir:**
- Gönderilen görevler
- Tamamlanma durumu

### 2. Sonuç Takibi

```python
# Sonuç geldiğinde
_result_cache[task_id] = result

# Sonuç alındığında
result = _result_cache.pop(task_id)
```

**Ne Takip Edilir:**
- Tamamlanan görevler
- Batch işlemler için cache

### 3. Metrik Takibi

```python
# InputQueue
_total_put += 1        # Görev gönderildi
_total_dropped += 1    # Queue dolu, görev düştü

# OutputQueue
_total_put += 1        # Sonuç eklendi
_total_get += 1        # Sonuç alındı

# ThreadPool
_active_count += 1    # Thread aktif
_active_count -= 1     # Thread boşta
```

**Ne Takip Edilir:**
- Queue istatistikleri
- Worker yükü
- Performans metrikleri

---

## 🎯 Önemli Noktalar

### 1. Paralel İşleme

- **Process seviyesi**: Her worker ayrı process
- **Thread seviyesi**: Her worker içinde birden fazla thread
- **Load balancing**: En az yüklü worker seçilir

### 2. Queue Yönetimi

- **InputQueue**: Görevlerin gönderildiği yer
- **OutputQueue**: Sonuçların toplandığı yer
- **Multiprocessing.Queue**: Process'ler arası iletişim

### 3. Result Cache

- Batch işlemler için kritik
- Queue sırası sorununu çözer
- Hızlı sonuç erişimi sağlar

### 4. Takip Mekanizmaları

- **Pending tasks**: Gönderilen görevler
- **Result cache**: Tamamlanan görevler
- **Component status**: Sistem durumu
- **Metrics**: Performans metrikleri

---

## 📚 Daha Fazla Bilgi

- **Detaylı Mimari**: [architecture.md](./architecture.md)
- **Veri Akışı**: [data_flow.md](./data_flow.md)
- **Örnekler**: [examples_guide.md](./examples_guide.md)
- **Çıktı Yorumlama**: [output_interpretation.md](./output_interpretation.md)


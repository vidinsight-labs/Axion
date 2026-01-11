# Axion - Modül Özeti

**Axion v3.0** - Hızlı Başlangıç Rehberi

Bu dokümantasyon, Axion'un temel yapısını ve kullanımını hızlıca anlamanız için hazırlanmıştır.

## 🎯 Axion Nedir?

**Axion**, Python için geliştirilmiş, yüksek performanslı bir **Task Execution Engine**'dir.

### Temel Özellikler

✅ **CPU/IO Ayrımı**: CPU-intensive ve IO-intensive işleri ayrı havuzlarda optimize eder  
✅ **Auto-Scaling**: Sistem yüküne göre otomatik worker ekleme/çıkarma  
✅ **Workflow Support**: DAG-based task dependencies (A → B → C)  
✅ **Work Stealing**: Boş worker'lar yüklü worker'lardan görev çalar  
✅ **Load Balancing**: Intelligent score-based task distribution  
✅ **Backpressure Control**: Sistem aşırı yüklüyse görev reddi  

---

## 📦 Modül Bileşenleri

```
axion/
│
├── 🔧 engine/
│   ├── engine.py              # Ana Engine (merkezi kontrol)
│   │   ├─ Resource Manager    # Auto-scaling loop
│   │   ├─ Queue Processor     # Task distribution
│   │   └─ Result Processor    # Result collection + workflow trigger
│
├── ⚙️ config/
│   └── __init__.py            # EngineConfig (tüm ayarlar)
│
├── 📋 task/
│   ├── task.py                # Task tanımı
│   └── result.py              # Result tanımı
│
├── 📬 queue/
│   ├── input_queue.py         # Görev kuyruğu
│   └── output_queue.py        # Sonuç kuyruğu
│
├── 👷 worker/
│   ├── pool.py                # ProcessPool (worker yönetimi + load balancing)
│   ├── process.py             # WorkerProcess (work stealing, CPU affinity)
│   └── thread.py              # ThreadPool (thread management)
│
├── 🚀 executer/
│   └── python_executor.py     # Script çalıştırıcı (module cache)
│
├── 🎯 core/
│   ├── enums.py               # TaskType, TaskStatus
│   ├── exceptions.py          # Hata sınıfları
│   ├── workflow.py            # WorkflowManager (DAG)
│   └── backpressure.py        # BackpressureController
│
└── 📊 status.py                # ComponentStatus
```

---

## 🚀 Hızlı Başlangıç

### 1. Basit Kullanım

```python
from axion import Engine, Task, TaskType

# Engine başlat
engine = Engine()
engine.start()

try:
    # Görev oluştur
    task = Task.create(
        script_path="my_script.py",
        params={"value": 42},
        task_type=TaskType.IO_BOUND
    )
    
    # Görevi gönder
    task_id = engine.submit_task(task)
    
    # Sonucu al
    result = engine.get_result(task_id, timeout=30)
    
    if result and result.is_success:
        print(f"✅ Sonuç: {result.data}")
    else:
        print(f"❌ Hata: {result.error if result else 'Timeout'}")

finally:
    # Engine'i kapat
    engine.shutdown()
```

### 2. Context Manager ile Kullanım

```python
from axion import Engine, Task, TaskType

with Engine() as engine:
    task = Task.create(
        script_path="my_script.py",
        params={"value": 42},
        task_type=TaskType.IO_BOUND
    )
    
    task_id = engine.submit_task(task)
    result = engine.get_result(task_id, timeout=30)
    
    print(f"Sonuç: {result.data}")
```

### 3. Script Formatı

```python
# my_script.py

def main(params, context):
    """
    Axion tarafından çağrılan main fonksiyonu
    
    Args:
        params (dict): Görev parametreleri
        context (ExecutionContext): Worker bilgisi (task_id, worker_id)
    
    Returns:
        any: JSON serializable sonuç
    """
    value = params.get("value", 0)
    result = value * 2
    
    # Context bilgisi
    print(f"Task ID: {context.task_id}")
    print(f"Worker ID: {context.worker_id}")
    
    return {"result": result, "status": "success"}
```

---

## 🔄 Temel Akış

### Görev Gönderme → İşleme → Sonuç Alma

```
┌─────────────┐
│  Kullanıcı  │
└──────┬──────┘
       │
       │ 1. Task.create(script_path, params, task_type)
       ▼
┌─────────────┐
│    Task     │ (id, script_path, params, TaskType.IO_BOUND)
└──────┬──────┘
       │
       │ 2. engine.submit_task(task)
       │    → task.to_dict()
       │    → InputQueue.put()
       │    → _pending_tasks[task.id] = task
       ▼
┌─────────────┐
│ InputQueue  │ (Multiprocessing.Queue - görev kuyruğu)
└──────┬──────┘
       │
       │ 3. _process_queue_loop() (Background Thread)
       │    → InputQueue.get()
       │    → Task.from_dict()
       │    → ProcessPool.submit_task(task, task_type)
       ▼
┌─────────────┐
│ProcessPool  │
│             │
│ Load Balance│ → En az yüklü worker'ı seç (score-based)
│             │
└──────┬──────┘
       │
       │ 4. Sharded Queue
       │    → cpu_queues[best_worker_idx].put(task)
       │    → veya io_queues[best_worker_idx].put(task)
       ▼
┌─────────────┐
│WorkerProcess│ (Ayrı process, CPU affinity, nice level)
│             │
│ Work Steal  │ → Kendi queue'dan al veya başkasından çal
│             │
└──────┬──────┘
       │
       │ 5. ThreadPool.submit_task()
       ▼
┌─────────────┐
│ThreadPool   │ (Process içinde thread pool)
│             │
│ Thread Pick │ → Boş thread bul
│             │
└──────┬──────┘
       │
       │ 6. PythonExecutor.execute(task, context)
       │    → Module yükle (cache'den veya dosyadan)
       │    → main(params, context) çağır
       │    → Result oluştur
       ▼
┌─────────────┐
│   Result    │ (task_id, status, data/error)
└──────┬──────┘
       │
       │ 7. OutputQueue.put(result.to_dict())
       ▼
┌─────────────┐
│OutputQueue  │ (Multiprocessing.Queue - sonuç kuyruğu)
└──────┬──────┘
       │
       │ 8. _process_result_loop() (Background Thread)
       │    → OutputQueue.get()
       │    → Result.from_dict()
       │    → _result_cache[result.task_id] = result
       │    → WorkflowManager.task_completed(result)
       ▼
┌─────────────┐
│Result Cache │ + Workflow Trigger
└──────┬──────┘
       │
       │ 9. engine.get_result(task_id, timeout)
       │    → Cache'e bak: cache.pop(task_id)
       │    → Yoksa döngüde bekle
       ▼
┌─────────────┐
│   Result    │
└──────┬──────┘
       │
       │ 10. Kullanıcıya döndür
       ▼
┌─────────────┐
│  Kullanıcı  │
└─────────────┘
```

---

## 🎯 Temel Özellikler

### 1. Auto-Scaling

**Resource Manager Loop** her 2 saniyede bir çalışır ve worker sayısını ayarlar:

```python
# Queue Pressure (Proactive)
input_queue_size = 10,000
cpu_pending_per_worker = 10,000 / 4 = 2,500 tasks/worker
→ QUEUE PRESSURE: +2 worker ekle (acil)

# Load-Based (Reactive)
cpu_avg_load = 5.8
cpu_p75_load = 6.5
→ HIGH LOAD: +1 worker ekle

# Velocity-Based (Predictive)
cpu_velocity = 3.5 load/second (trend yukarı)
→ HIGH VELOCITY: +1 worker ekle (önceden)

# Scale-In
cpu_avg_load = 0.8
cpu_pending_per_worker = 2
→ SCALE IN: -1 worker çıkar (boşta)
```

### 2. Work Stealing

Boş worker'lar, yüklü worker'ların queue'sundan görev çalar:

```python
# Worker A: 50 görev bekliyor
# Worker B: 0 görev bekliyor

# Worker B'nin run loop'u:
task = None

# 1. Kendi queue'dan dene
task = my_queue.get_nowait()  # Empty!

# 2. Başkalarının queue'larından çal
for victim_queue in all_queues:
    if victim_queue != my_queue:
        task = victim_queue.get_nowait()  # Worker A'dan çaldı!
        break

# 3. İşi çalıştır
if task:
    thread_pool.submit_task(task)
```

### 3. Load Balancing

Score-based intelligent task distribution:

```python
# Her worker için score hesapla
for worker in workers:
    active_threads = worker.active_thread_count()
    queue_size = worker.queue_size()
    cpu_usage = worker.cpu_usage / 100.0
    
    if TaskType.CPU_BOUND:
        # CPU: Thread saturation odaklı
        score = queue * 0.6 + threads * 1.2 + cpu * 0.05
    else:
        # IO: Queue doluluğu odaklı
        score = queue * 1.0 + threads * 0.8 + cpu * 0.02

# En düşük score'lu worker'a gönder
best_worker = min(workers, key=lambda w: w.score)
best_worker.submit(task)
```

### 4. Workflow Management (DAG)

```python
# Task A: Veri indir
task_a = Task.create(script_path="download.py")

# Task B: İşle (A'ya bağımlı)
task_b = Task.create(
    script_path="process.py",
    dependencies=[task_a.id]  # A tamamlanınca başla
)

# Task C: Kaydet (B'ye bağımlı)
task_c = Task.create(
    script_path="save.py",
    dependencies=[task_b.id]
)

# Workflow olarak gönder
engine.submit_workflow([task_a, task_b, task_c])

# Otomatik akış:
# task_a çalışır → tamamlanır
# → task_b otomatik başlar (upstream_results['task_a_id'] alır)
# → task_c otomatik başlar (upstream_results['task_b_id'] alır)
```

### 5. Backpressure Control

```python
# Sistem aşırı yüklü mü?
cpu_percent = psutil.cpu_percent()  # %105
memory_percent = psutil.virtual_memory().percent  # %98

if cpu_percent > 100 or memory_percent > 100:
    # Yeni görev kabul etme
    raise TaskError("Sistem aşırı yüklü (Backpressure Active)")
```

---

## 📊 İzleme ve Metrikler

### Sistem Durumu

```python
status = engine.get_status()

# Engine durumu
print(status['engine']['is_running'])  # True

# Queue'lar
print(status['components']['input_queue']['metrics']['size'])        # 150
print(status['components']['input_queue']['metrics']['total_put'])   # 10000
print(status['components']['input_queue']['metrics']['total_dropped']) # 0

# Worker'lar
print(status['components']['process_pool']['metrics']['cpu_bound_workers'])  # 6
print(status['components']['process_pool']['metrics']['io_bound_workers'])   # 12
print(status['components']['process_pool']['metrics']['cpu_active_threads']) # 6
print(status['components']['process_pool']['metrics']['io_active_threads'])  # 45
```

### Worker Metrikleri

```python
pool_status = engine.get_component_status("process_pool")

# Her worker'ın durumu
for worker_id, metrics in pool_status.metrics['cpu_worker_tasks'].items():
    print(f"{worker_id}:")
    print(f"  Active: {metrics['active_tasks']}")
    print(f"  Queue: {metrics['queue_size']}")
    print(f"  CPU: {metrics['cpu_usage']}%")
    print(f"  Total Load: {metrics['total_load']}")
```

---

## ⚙️ Yapılandırma

### Temel Config

```python
from axion import Engine, EngineConfig

config = EngineConfig(
    # Queue boyutları
    input_queue_size=2000,      # Görev kuyruğu
    output_queue_size=10000,    # Sonuç kuyruğu
    
    # Worker sayıları
    cpu_bound_count=4,          # CPU-intensive işler
    io_bound_count=8,           # IO-intensive işler
    
    # Thread limitleri
    cpu_bound_task_limit=1,     # CPU worker başına 1 thread (GIL)
    io_bound_task_limit=20,     # IO worker başına 20 thread
    
    # Genel
    log_level="INFO",
    queue_poll_timeout=1.0
)

engine = Engine(config)
```

### Senaryoya Göre Config

**CPU-Intensive İşler**:
```python
config = EngineConfig(
    cpu_bound_count=multiprocessing.cpu_count(),
    cpu_bound_task_limit=1,      # GIL nedeniyle
    io_bound_count=2             # Az sayıda IO worker
)
```

**IO-Intensive İşler**:
```python
config = EngineConfig(
    cpu_bound_count=2,           # Az sayıda CPU worker
    io_bound_count=multiprocessing.cpu_count() * 3,
    io_bound_task_limit=50       # Yüksek thread limiti
)
```

**Mixed Workload**:
```python
config = EngineConfig(
    cpu_bound_count=4,
    io_bound_count=12,
    cpu_bound_task_limit=1,
    io_bound_task_limit=20
)
# Auto-scaling bu dengeyi optimize eder
```

---

## 🎓 Önemli Kavramlar

### Task Types

| TaskType | Açıklama | Örnek | Worker Config |
|----------|----------|-------|---------------|
| **CPU_BOUND** | CPU-yoğun işler | Matrix multiplication, prime calculation | count=CPU_COUNT, threads=1 |
| **IO_BOUND** | IO-yoğun işler | File I/O, network requests, database | count=CPU_COUNT*3, threads=20-50 |

### Worker Pool

- **CPU Pool**: CPU-intensive işler için
  - Az sayıda worker (CPU core sayısı)
  - Thread limit = 1 (GIL nedeniyle)
  - CPU affinity (core'a sabitleme)
  - Nice level = 0 (yüksek öncelik)

- **IO Pool**: IO-intensive işler için
  - Çok sayıda worker (CPU * 3)
  - Yüksek thread limit (20-50)
  - Nice level = 5 (düşük öncelik, CPU'yu bırakır)

### Load Metrics

- **Active Tasks**: Şu an çalışan thread sayısı
- **Queue Size**: Worker'ın kendi queue'sunda bekleyen görev sayısı
- **Thread Pool Queue**: ThreadPool'da bekleyen görev sayısı
- **Total Load**: active + queue + thread_pool_queue
- **CPU Usage**: Worker process'in CPU kullanımı

---

## 📚 Sonraki Adımlar

### Detaylı Dokümantasyon

- **[Architecture](./architecture.md)** - Mimari detayları
  - Auto-scaling algoritması
  - Work stealing mekanizması
  - Load balancing stratejisi

- **[Data Flow](./data_flow.md)** - Veri akışı
  - Görev gönderme akışı
  - Sonuç alma akışı
  - Process iletişimi

- **[Examples Guide](./examples_guide.md)** - Kullanım örnekleri
  - Basit örnekler
  - Workflow örnekleri
  - Batch işlemler

- **[Output Interpretation](./output_interpretation.md)** - Çıktı yorumlama
  - Log mesajları
  - Hata mesajları
  - Performans metrikleri

### Kod Örnekleri

```bash
# Basit kullanım
python examples/simple_example.py

# Gelişmiş özellikler
python examples/advanced_example.py

# Benchmark testleri
python benchmarks/throughput_test.py
python benchmarks/scalability_test.py
python benchmarks/cpu_bound_performance_test.py
```

---

## 🔍 Özet

### Axion Nedir?
Python için yüksek performanslı task execution engine

### Temel Özellikler
✅ Auto-scaling (queue, load, velocity-based)  
✅ Work stealing (idle worker'lar busy'lerden çalar)  
✅ Load balancing (intelligent score-based)  
✅ Workflow support (DAG, dependencies)  
✅ Backpressure control (overload protection)  

### Kullanım
```python
with Engine() as engine:
    task = Task.create(script_path, params, task_type)
    task_id = engine.submit_task(task)
    result = engine.get_result(task_id)
```

### Performans
- **10,000 görev** → Auto-scaling ile hemen adapt
- **Throughput**: 400+ görev/saniye (IO-bound)
- **Latency**: <100ms (düşük yük)
- **Scalability**: 1-16 CPU workers, 1-24 IO workers

### İzleme
```python
status = engine.get_status()
# Queue sizes, worker counts, active tasks, CPU usage
```

**Axion ile yüksek performanslı, scalable task execution sistemleri kurun!** 🚀

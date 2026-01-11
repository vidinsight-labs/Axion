# Axion - Örnekler Kılavuzu

**Axion v3.0** - Kullanım Örnekleri ve Senaryolar

Bu dokümantasyon, Axion'un nasıl kullanılacağını örneklerle açıklar.

## 📑 İçindekiler

1. [Basit Örnek](#basit-örnek)
2. [Gelişmiş Örnek](#gelişmiş-örnek)
3. [Workflow Örneği](#workflow-örneği)
4. [Batch İşlemler](#batch-işlemler)
5. [Auto-Scaling Örneği](#auto-scaling-örneği)
6. [Yaygın Senaryolar](#yaygın-senaryolar)

---

## 🚀 Basit Örnek

### Dosya: `examples/simple_example.py`

### Ne Yapar?

Axion'un en temel kullanımını gösterir:
- Engine oluşturma ve başlatma
- Tek bir görev gönderme
- Sonuç alma

### Kod

```python
from axion import Engine, Task, TaskType

# Engine başlat
with Engine() as engine:
    # Görev oluştur
    task = Task.create(
        script_path="simple_task.py",
        params={"value": 42, "test": True},
        task_type=TaskType.IO_BOUND
    )
    
    # Görevi gönder
    task_id = engine.submit_task(task)
    print(f"✅ Görev gönderildi: {task_id[:8]}...")
    
    # Sonucu al
    result = engine.get_result(task_id, timeout=30)
    
    if result and result.is_success:
        print(f"✅ Sonuç: {result.data}")
    else:
        print(f"❌ Hata: {result.error if result else 'Timeout'}")
```

### Script Formatı

```python
# simple_task.py
def main(params, context):
    """
    Axion tarafından çağrılan main fonksiyonu
    """
    value = params.get("value", 0)
    result = value * 2
    
    return {
        "result": result,
        "original_value": value,
        "test_mode": params.get("test", False),
        "task_id": context.task_id,
        "worker_id": context.worker_id,
        "status": "success"
    }
```

### Çıktı

```
============================================================
BASİT KULLANIM ÖRNEĞİ
============================================================

📊 Config:
   CPU-bound workers: 1
   IO-bound workers: 7

🔧 Engine başlatılıyor...
✅ Engine başlatıldı

📤 Görev gönderiliyor: fcccdf0b...
✅ Görev gönderildi: fcccdf0b...

⏳ Sonuç bekleniyor...

✅ Görev başarılı!
   Sonuç: {
       'result': 84,
       'original_value': 42,
       'test_mode': True,
       'task_id': 'fcccdf0b-562d-4985-a019-568dacd04ae7',
       'worker_id': 'io-0',
       'status': 'success'
   }

🛑 Engine kapatılıyor...
✅ Engine kapatıldı
```

### Çıktı Yorumlama

- **Config**: Varsayılan worker sayıları (CPU: 1, IO: 7)
- **Görev gönderildi**: Task ID'nin ilk 8 karakteri gösterilir
- **Sonuç**: Script'in döndürdüğü veri
- **worker_id**: Görevi işleyen worker (`io-0` = IO-bound worker 0)

---

## 🎯 Gelişmiş Örnek

### Dosya: `examples/advanced_example.py`

### Ne Yapar?

Gelişmiş özellikleri gösterir:
- Özel config ile engine
- Birden fazla CPU-bound görev
- Birden fazla IO-bound görev
- Batch işlemler
- Sistem durumu takibi

### Kod

```python
from axion import Engine, EngineConfig, Task, TaskType

# Özel config
config = EngineConfig(
    cpu_bound_count=2,
    io_bound_count=4,
    cpu_bound_task_limit=1,
    io_bound_task_limit=10,
    input_queue_size=5000,
    output_queue_size=10000
)

with Engine(config) as engine:
    # Sistem durumu
    status = engine.get_status()
    print(f"Engine: {'🟢 Çalışıyor' if status['engine']['is_running'] else '🔴 Durdu'}")
    
    # CPU-bound görevler
    cpu_tasks = []
    for i in range(3):
        task = Task.create(
            script_path="cpu_task.py",
            params={"n": 1000 * (i + 1)},
            task_type=TaskType.CPU_BOUND
        )
        cpu_tasks.append(task)
        engine.submit_task(task)
    
    # IO-bound görevler
    io_tasks = []
    for i in range(5):
        task = Task.create(
            script_path="io_task.py",
            params={"delay": 0.1 * (i + 1)},
            task_type=TaskType.IO_BOUND
        )
        io_tasks.append(task)
        engine.submit_task(task)
    
    # Sonuçları topla
    for task in cpu_tasks + io_tasks:
        result = engine.get_result(task.id, timeout=30)
        if result and result.is_success:
            print(f"✅ {task.id[:8]}...: {result.data}")
```

### Çıktı

```
======================================================================
GELİŞMİŞ KULLANIM ÖRNEĞİ
======================================================================

📊 Özel Config:
   CPU-bound workers: 2 (her biri 1 thread)
   IO-bound workers: 4 (her biri 10 thread)
   Queue sizes: 5000/10000

📊 Sistem Durumu:
   Engine: 🟢 Çalışıyor
   input_queue: healthy
   output_queue: healthy
   process_pool: healthy

======================================================================
CPU-BOUND GÖREVLER
======================================================================
   ✓ Görev 1 gönderildi: 44bfa228... (n=1000)
   ✓ Görev 2 gönderildi: a0a25259... (n=2000)
   ✓ Görev 3 gönderildi: 3900caf5... (n=3000)

======================================================================
IO-BOUND GÖREVLER
======================================================================
   ✓ Görev 1 gönderildi: 97e81457... (delay=0.1s)
   ✓ Görev 2 gönderildi: 324f586c... (delay=0.2s)
   ✓ Görev 3 gönderildi: eee0afa5... (delay=0.3s)
   ✓ Görev 4 gönderildi: c8c1dead... (delay=0.4s)
   ✓ Görev 5 gönderildi: 18b382d1... (delay=0.5s)

======================================================================
SONUÇLAR
======================================================================

📊 CPU-bound sonuçları:
   ✅ 44bfa228...: 332833500
   ✅ a0a25259...: 2664667000
   ✅ 3900caf5...: 8995500500

🌐 IO-bound sonuçları:
   ✅ 97e81457...: completed
   ✅ 324f586c...: completed
   ✅ eee0afa5...: completed
   ✅ c8c1dead...: completed
   ✅ 18b382d1...: completed

======================================================================
İSTATİSTİKLER
======================================================================

📈 Özet:
   Toplam görev: 8
   Başarılı: 8
   Başarısız: 0
```

---

## 🔗 Workflow Örneği

### Senaryo: Veri İndirme → İşleme → Kaydetme

### Kod

```python
from axion import Engine, Task, TaskType

with Engine() as engine:
    # Task A: Veri indir
    task_a = Task.create(
        script_path="download.py",
        params={"url": "https://api.example.com/data"},
        task_type=TaskType.IO_BOUND
    )
    
    # Task B: Veriyi işle (A'ya bağımlı)
    task_b = Task.create(
        script_path="process.py",
        params={"operation": "transform"},
        task_type=TaskType.CPU_BOUND,
        dependencies=[task_a.id]  # A tamamlanınca başla
    )
    
    # Task C: Sonucu kaydet (B'ye bağımlı)
    task_c = Task.create(
        script_path="save.py",
        params={"output": "result.json"},
        task_type=TaskType.IO_BOUND,
        dependencies=[task_b.id]  # B tamamlanınca başla
    )
    
    # Workflow olarak gönder
    task_ids = engine.submit_workflow([task_a, task_b, task_c])
    
    # Sonuçları bekle
    for task_id in task_ids:
        result = engine.get_result(task_id, timeout=60)
        if result and result.is_success:
            print(f"✅ {task_id[:8]}...: Tamamlandı")
```

### Script Örnekleri

```python
# download.py
def main(params, context):
    import requests
    url = params["url"]
    data = requests.get(url).json()
    return {"data": data, "size": len(data)}

# process.py
def main(params, context):
    # Upstream result'u al
    upstream = params.get("upstream_results", {})
    task_a_id = list(upstream.keys())[0]  # İlk bağımlılık
    data = upstream[task_a_id]["data"]
    
    # İşle
    processed = [item * 2 for item in data]
    return {"processed": processed, "count": len(processed)}

# save.py
def main(params, context):
    upstream = params.get("upstream_results", {})
    task_b_id = list(upstream.keys())[0]
    processed = upstream[task_b_id]["processed"]
    
    # Kaydet
    import json
    with open(params["output"], "w") as f:
        json.dump(processed, f)
    return {"saved": True, "file": params["output"]}
```

### Akış

```
1. task_a çalışır → Veri indirilir → Tamamlanır
2. task_b otomatik başlar → upstream_results['task_a_id'] kullanılır → İşlenir → Tamamlanır
3. task_c otomatik başlar → upstream_results['task_b_id'] kullanılır → Kaydedilir → Tamamlanır
```

---

## 📦 Batch İşlemler

### Senaryo: 10,000 Görev Paralel İşleme

### Kod

```python
from axion import Engine, Task, TaskType
import time

with Engine() as engine:
    # 10,000 görev oluştur
    task_ids = []
    start_time = time.time()
    
    for i in range(10000):
        task = Task.create(
            script_path="process_item.py",
            params={"item_id": i, "data": f"item_{i}"},
            task_type=TaskType.IO_BOUND
        )
        task_id = engine.submit_task(task)
        task_ids.append(task_id)
    
    submission_time = time.time() - start_time
    print(f"✅ 10,000 görev {submission_time:.2f}s'de gönderildi")
    
    # Sonuçları topla
    results = []
    start_time = time.time()
    
    for task_id in task_ids:
        result = engine.get_result(task_id, timeout=60)
        if result and result.is_success:
            results.append(result.data)
    
    processing_time = time.time() - start_time
    print(f"✅ 10,000 sonuç {processing_time:.2f}s'de alındı")
    print(f"📊 Throughput: {10000/processing_time:.1f} görev/saniye")
```

### Auto-Scaling Davranışı

```
[CPU] Scale OUT +2 → 6 workers | QUEUE PRESSURE: 2500 tasks/worker (queue=10000)
[IO] Scale OUT +1 → 8 workers | HIGH: p90=35.0, queue=22.0
[CPU] Scale OUT +1 → 7 workers | MODERATE+VEL: load=4.2, vel=2.8/s
[IO] Scale OUT +1 → 9 workers | QUEUE PRESSURE: 1111 tasks/worker
...
[CPU] Scale IN -1 → 6 workers | SCALE IN: avg=0.8, queue=2/worker
```

### Beklenen Performans

- **Submission**: ~1-2 saniye (10,000 görev)
- **Processing**: ~25-30 saniye (auto-scaling ile)
- **Throughput**: ~300-400 görev/saniye
- **Auto-scaling**: 4 → 16 CPU workers, 8 → 24 IO workers

---

## ⚡ Auto-Scaling Örneği

### Senaryo: Ani Yük Artışı

### Kod

```python
from axion import Engine, Task, TaskType
import time

config = EngineConfig(
    cpu_bound_count=2,  # Başlangıç: 2 worker
    io_bound_count=4    # Başlangıç: 4 worker
)

with Engine(config) as engine:
    # İlk durum
    status = engine.get_status()
    print(f"Başlangıç: {status['components']['process_pool']['metrics']['cpu_bound_workers']} CPU workers")
    
    # 10,000 görev gönder (ani yük)
    task_ids = []
    for i in range(10000):
        task = Task.create(
            script_path="task.py",
            params={"id": i},
            task_type=TaskType.CPU_BOUND
        )
        task_ids.append(engine.submit_task(task))
    
    # Auto-scaling'i izle
    for _ in range(10):
        time.sleep(2)
        status = engine.get_status()
        cpu_workers = status['components']['process_pool']['metrics']['cpu_bound_workers']
        queue_size = status['components']['input_queue']['metrics']['size']
        print(f"CPU Workers: {cpu_workers}, Queue: {queue_size}")
    
    # Sonuçları bekle
    for task_id in task_ids:
        engine.get_result(task_id, timeout=60)
```

### Beklenen Çıktı

```
Başlangıç: 2 CPU workers

[CPU] Scale OUT +2 → 4 workers | QUEUE PRESSURE: 2500 tasks/worker (queue=10000)
CPU Workers: 4, Queue: 8500

[CPU] Scale OUT +2 → 6 workers | QUEUE PRESSURE: 1416 tasks/worker
CPU Workers: 6, Queue: 6000

[CPU] Scale OUT +2 → 8 workers | QUEUE PRESSURE: 750 tasks/worker
CPU Workers: 8, Queue: 3000

[CPU] Scale OUT +2 → 10 workers | MODERATE+VEL: load=4.2, vel=3.1/s
CPU Workers: 10, Queue: 500

CPU Workers: 10, Queue: 0

[CPU] Scale IN -1 → 9 workers | SCALE IN: avg=0.8, queue=0/worker
CPU Workers: 9, Queue: 0
```

---

## 🎓 Yaygın Senaryolar

### Senaryo 1: Web Scraping

```python
# 1000 URL'i paralel olarak scrape et
with Engine() as engine:
    urls = [...]  # 1000 URL
    
    task_ids = []
    for url in urls:
        task = Task.create(
            script_path="scrape.py",
            params={"url": url},
            task_type=TaskType.IO_BOUND  # Network I/O
        )
        task_ids.append(engine.submit_task(task))
    
    results = []
    for task_id in task_ids:
        result = engine.get_result(task_id, timeout=30)
        if result and result.is_success:
            results.append(result.data)
```

### Senaryo 2: Image Processing

```python
# 500 görüntüyü paralel işle
with Engine() as engine:
    images = [...]  # 500 görüntü path'i
    
    task_ids = []
    for image_path in images:
        task = Task.create(
            script_path="process_image.py",
            params={"image_path": image_path, "operation": "resize"},
            task_type=TaskType.CPU_BOUND  # CPU-intensive
        )
        task_ids.append(engine.submit_task(task))
    
    processed = []
    for task_id in task_ids:
        result = engine.get_result(task_id, timeout=60)
        if result and result.is_success:
            processed.append(result.data)
```

### Senaryo 3: Data Pipeline

```python
# ETL Pipeline: Extract → Transform → Load
with Engine() as engine:
    # Extract
    extract_tasks = []
    for source in sources:
        task = Task.create(
            script_path="extract.py",
            params={"source": source},
            task_type=TaskType.IO_BOUND
        )
        extract_tasks.append(task)
    
    # Transform (Extract'lara bağımlı)
    transform_tasks = []
    for extract_task in extract_tasks:
        task = Task.create(
            script_path="transform.py",
            params={"operation": "clean"},
            task_type=TaskType.CPU_BOUND,
            dependencies=[extract_task.id]
        )
        transform_tasks.append(task)
    
    # Load (Transform'lara bağımlı)
    load_tasks = []
    for transform_task in transform_tasks:
        task = Task.create(
            script_path="load.py",
            params={"target": "database"},
            task_type=TaskType.IO_BOUND,
            dependencies=[transform_task.id]
        )
        load_tasks.append(task)
    
    # Workflow gönder
    all_tasks = extract_tasks + transform_tasks + load_tasks
    task_ids = engine.submit_workflow(all_tasks)
    
    # Sonuçları bekle
    for task_id in task_ids:
        result = engine.get_result(task_id, timeout=120)
```

---

## 🔍 Sorun Giderme

### Görev Timeout

**Sorun:** `result = None` (timeout)

**Çözüm:**
```python
# 1. Timeout süresini artır
result = engine.get_result(task_id, timeout=120.0)

# 2. Worker sayısını artır
config = EngineConfig(io_bound_count=16)

# 3. Auto-scaling limitlerini kontrol et
# Auto-scaling otomatik çalışıyor, ama max limiti aşıyor olabilir
```

### Görev Başarısız

**Sorun:** `result.is_success = False`

**Çözüm:**
```python
if result and not result.is_success:
    print(f"Hata: {result.error}")
    print(f"Detaylar: {result.error_details}")
    
    # Script'i kontrol et
    # - main() fonksiyonu var mı?
    # - Parametreler doğru mu?
    # - Script'te syntax hatası var mı?
```

### Queue Dolu

**Sorun:** `TaskError: Queue dolu, görev eklenemedi`

**Çözüm:**
```python
# 1. Queue boyutunu artır
config = EngineConfig(input_queue_size=10000)

# 2. Daha fazla worker ekle (auto-scaling otomatik yapar)
config = EngineConfig(cpu_bound_count=8)

# 3. Batch gönderim hızını azalt
for task in tasks:
    engine.submit_task(task)
    time.sleep(0.001)  # Biraz bekle
```

---

## 📚 Özet

### Temel Kullanım

1. **Engine başlat**: `with Engine() as engine:`
2. **Görev oluştur**: `Task.create(script_path, params, task_type)`
3. **Görevi gönder**: `engine.submit_task(task)`
4. **Sonucu al**: `engine.get_result(task_id, timeout)`

### Gelişmiş Özellikler

- ✅ **Workflow**: DAG-based task dependencies
- ✅ **Batch İşlemler**: 10,000+ görev paralel işleme
- ✅ **Auto-Scaling**: Otomatik worker ekleme/çıkarma
- ✅ **Mixed Workload**: CPU ve IO görevleri aynı anda

### Performans İpuçları

- ✅ **Task Type**: Doğru tipi seç (CPU_BOUND vs IO_BOUND)
- ✅ **Batch Size**: 1000-10000 görev optimal
- ✅ **Timeout**: Görev süresine göre ayarla
- ✅ **Config**: Senaryoya göre optimize et

---

## 🔗 İlgili Dokümantasyon

- [Module Overview](./module_overview.md) - Genel bakış
- [Architecture](./architecture.md) - Mimari detayları
- [Output Interpretation](./output_interpretation.md) - Çıktı yorumlama

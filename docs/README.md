# Axion - Dokümantasyon

**Axion v3.0** - Gelişmiş Task Execution Engine

Bu klasör, Axion projesinin kapsamlı dokümantasyonunu içerir.

## 📚 İçindekiler

### 🚀 Hızlı Başlangıç

1. **[Module Overview](./module_overview.md)** - Modül özeti (İLK OKUMA)
   - Axion nedir?
   - Temel bileşenler
   - Basit kullanım örneği
   - Hızlı başlangıç

### 🏗️ Mimari ve Akış

2. **[Architecture](./architecture.md)** - Mimari detayları
   - Sistem mimarisi
   - Bileşen açıklamaları
   - Auto-scaling mekanizması
   - Workflow yönetimi
   - Work stealing algoritması

3. **[Data Flow](./data_flow.md)** - Veri akışı
   - Görev gönderme akışı
   - Sonuç alma akışı
   - Process iletişimi
   - Queue yönetimi

### 📖 Kullanım Kılavuzları

4. **[Examples Guide](./examples_guide.md)** - Örnekler
   - Basit kullanım
   - Gelişmiş özellikler
   - Workflow örnekleri
   - Batch işlemler

5. **[Output Interpretation](./output_interpretation.md)** - Çıktı yorumlama
   - Log mesajları
   - Metrikler
   - Hata mesajları
   - Performans analizi

6. **[Integration Guide](./integration_guide.md)** - Entegrasyon rehberi ⭐ YENİ
   - Gerçek hayat senaryoları
   - Projeye entegrasyon
   - Best practices
   - Web framework entegrasyonu
   - Service wrapper desenleri

7. **[Demo Guide](./demo_guide.md)** - Demo kılavuzu
   - Demo senaryoları
   - Performans testleri
   - Benchmark sonuçları

---

## 🎯 Hızlı Başlangıç

### Temel Kullanım

```python
from axion import Engine, Task, TaskType

# Engine başlat
with Engine() as engine:
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
        print(f"Sonuç: {result.data}")
    else:
        print(f"Hata: {result.error if result else 'Timeout'}")
```

### Script Formatı

```python
# my_script.py
def main(params, context):
    """
    Axion tarafından çağrılan main fonksiyonu
    
    Args:
        params (dict): Görev parametreleri
        context (ExecutionContext): Worker bilgisi
    
    Returns:
        any: Sonuç verisi (JSON serializable)
    """
    value = params.get("value", 0)
    result = value * 2
    
    return {"result": result, "status": "success"}
```

---

## 🔧 Yapılandırma

### EngineConfig

```python
from axion import Engine, EngineConfig

config = EngineConfig(
    # Queue boyutları
    input_queue_size=2000,
    output_queue_size=10000,
    
    # Worker sayıları
    cpu_bound_count=4,          # CPU-intensive işler için
    io_bound_count=8,           # IO-intensive işler için
    
    # Thread limitleri
    cpu_bound_task_limit=1,     # CPU worker başına thread
    io_bound_task_limit=20,     # IO worker başına thread
    
    # Genel ayarlar
    log_level="INFO",
    queue_poll_timeout=1.0
)

engine = Engine(config)
```

### Config Parametreleri

| Parametre | Açıklama | Varsayılan |
|-----------|----------|------------|
| `input_queue_size` | Görev kuyruğu boyutu | 1000 |
| `output_queue_size` | Sonuç kuyruğu boyutu | 10000 |
| `cpu_bound_count` | CPU worker sayısı | 1 |
| `io_bound_count` | IO worker sayısı | CPU_COUNT-1 |
| `cpu_bound_task_limit` | CPU worker thread limiti | 1 |
| `io_bound_task_limit` | IO worker thread limiti | 20 |
| `log_level` | Log seviyesi | "INFO" |
| `queue_poll_timeout` | Queue polling timeout | 1.0 |

---

## 🌟 Temel Özellikler

### 1. Auto-Scaling

Axion, sistem yüküne göre otomatik olarak worker sayısını artırır/azaltır:

```python
# Queue-aware scaling
# 10,000 görev geldiğinde otomatik scale-out

# Velocity-based scaling
# Yük hızlı artıyorsa proaktif scale-out

# Intelligent scale-in
# Yük azaldığında güvenli scale-in
```

**Özellikler:**
- ✅ Queue pressure detection
- ✅ Load-based scaling
- ✅ Velocity tracking
- ✅ Worker warm-up awareness

### 2. Workflow Management (DAG)

Birbirine bağımlı görevleri yönetir:

```python
# Görevler arası bağımlılık
task_a = Task.create(...)
task_b = Task.create(..., dependencies=[task_a.id])
task_c = Task.create(..., dependencies=[task_b.id])

# Workflow olarak gönder
task_ids = engine.submit_workflow([task_a, task_b, task_c])

# task_a tamamlanınca task_b otomatik başlar
# task_b tamamlanınca task_c otomatik başlar
```

### 3. Work Stealing

Boş worker'lar, yüklü worker'ların queue'sundan görev çalar:

```python
# Worker A: 50 görev bekliyor
# Worker B: 0 görev bekliyor
# → Worker B, Worker A'nın queue'sundan görev çalar
```

### 4. Load Balancing

Intelligent score-based task distribution:

```python
# CPU-bound: Thread saturation odaklı
score_cpu = process_load * 0.6 + thread_load * 1.2 + cpu_usage * 0.05

# IO-bound: Queue doluluğu odaklı
score_io = process_load * 1.0 + thread_load * 0.8 + cpu_usage * 0.02
```

### 5. Backpressure Control

Sistem aşırı yüklüyse yeni görev kabul etmez:

```python
# CPU > %100 veya RAM > %100
# → TaskError: "Sistem aşırı yüklü (Backpressure Active)"
```

---

## 📊 İzleme ve Metrikler

### Sistem Durumu

```python
status = engine.get_status()

print(f"Engine: {status['engine']['is_running']}")
print(f"Input Queue: {status['components']['input_queue']['metrics']['size']}")
print(f"CPU Workers: {status['components']['process_pool']['metrics']['cpu_bound_workers']}")
print(f"IO Workers: {status['components']['process_pool']['metrics']['io_bound_workers']}")
```

### Worker Metrikleri

```python
pool_status = engine.get_component_status("process_pool")

for worker_id, metrics in pool_status.metrics['cpu_worker_tasks'].items():
    print(f"{worker_id}: {metrics['active_tasks']} active, {metrics['queue_size']} queued")
```

---

## 🔍 Çıktı Örnekleri

### Başarılı Görev

```
[CPU] Scale OUT +2 → 6 workers | QUEUE PRESSURE: 500 tasks/worker
✅ Görev başarılı!
   Sonuç: {'result': 84, 'status': 'success'}
   Süre: 0.15s
```

### Auto-Scaling Log

```
[CPU] Scale OUT +2 → 4 workers | QUEUE PRESSURE: 2500 tasks/worker (queue=10000)
[IO] Scale OUT +1 → 8 workers | HIGH: p90=35.0, queue=22.0
[CPU] Scale IN -1 → 3 workers | SCALE IN: avg=0.8, cpu=0.15
```

### Hata Mesajı

```
❌ Görev başarısız
   Hata: Script'te 'main' fonksiyonu bulunamadı: my_script.py
   Task ID: abc123...
```

---

## 🛠️ Sorun Giderme

### Görev Timeout

**Sorun:** Görev timeout alıyor

**Çözüm:**
```python
# 1. Timeout süresini artır
result = engine.get_result(task_id, timeout=120.0)

# 2. Worker sayısını artır
config = EngineConfig(io_bound_count=16)

# 3. Auto-scaling limitlerini kontrol et
# Auto-scaling otomatik çalışıyor, ama max limiti aşıyor olabilir
```

### Queue Dolu

**Sorun:** `TaskError: Queue dolu, görev eklenemedi`

**Çözüm:**
```python
# Queue boyutunu artır
config = EngineConfig(input_queue_size=5000)

# Veya daha fazla worker ekle (auto-scaling otomatik yapar)
config = EngineConfig(cpu_bound_count=8)
```

### High Memory Usage

**Sorun:** Memory kullanımı yüksek

**Kontrol Noktaları:**
```python
# 1. Result cache boyutu
# Engine result_cache'i 5000 sonuçta sınırlı
# get_result() çağrısından sonra sonuçlar temizleniyor

# 2. Workflow results
# Workflow sonuçları bellekte tutuluyor
# Büyük workflow'larda dikkat

# 3. Worker sayısı
# Çok fazla worker → Çok fazla memory
# Auto-scaling maksimum limitlere dikkat
```

### Slow Performance

**Sorun:** Performans düşük

**Çözüm:**
```python
# 1. Task tipini kontrol et
# CPU-intensive → TaskType.CPU_BOUND
# IO-intensive → TaskType.IO_BOUND

# 2. Worker limitlerini kontrol et
config = EngineConfig(
    cpu_bound_count=4,           # CPU core sayısına göre
    io_bound_count=16,           # IO için daha fazla
    io_bound_task_limit=30       # Thread limiti artır
)

# 3. Auto-scaling metriklerini izle
status = engine.get_status()
# Queue size, worker counts, active tasks
```

---

## 📈 Performans Optimizasyonu

### CPU-Bound İşler

```python
config = EngineConfig(
    cpu_bound_count=multiprocessing.cpu_count(),  # Core sayısı kadar
    cpu_bound_task_limit=1,                       # Thread=1 (GIL nedeniyle)
    io_bound_count=2                              # IO için az sayıda
)
```

### IO-Bound İşler

```python
config = EngineConfig(
    cpu_bound_count=2,                            # CPU için az sayıda
    io_bound_count=multiprocessing.cpu_count()*3, # IO için çok sayıda
    io_bound_task_limit=50                        # Yüksek thread limiti
)
```

### Mixed Workload

```python
config = EngineConfig(
    cpu_bound_count=4,
    io_bound_count=12,
    cpu_bound_task_limit=1,
    io_bound_task_limit=20
)

# Auto-scaling bu dengeyi dinamik olarak optimize eder
```

---

## 🔗 Daha Fazla Bilgi

### Dokümantasyon

- **[Module Overview](./module_overview.md)** - Modül özeti
- **[Architecture](./architecture.md)** - Mimari detayları
- **[Data Flow](./data_flow.md)** - Veri akışı
- **[Examples Guide](./examples_guide.md)** - Kullanım örnekleri
- **[Output Interpretation](./output_interpretation.md)** - Çıktı yorumlama
- **[Demo Guide](./demo_guide.md)** - Demo kılavuzu

### Kod Örnekleri

- `examples/simple_example.py` - Basit kullanım
- `examples/advanced_example.py` - Gelişmiş özellikler
- `benchmarks/` - Performance testleri

### Benchmark

```bash
# Performans testleri
python benchmarks/throughput_test.py
python benchmarks/scalability_test.py
python benchmarks/cpu_bound_performance_test.py
python benchmarks/io_bound_performance_test.py
```

---

## 🤝 Katkıda Bulunma

Dokümantasyonu geliştirmek için:

1. **Eksik bilgileri ekleyin**
   - Yeni özellikler
   - Use case'ler
   - Best practices

2. **Örnekleri güncelleyin**
   - Gerçek dünya senaryoları
   - Performans testleri
   - Troubleshooting rehberi

3. **Hata düzeltmeleri**
   - Yanlış bilgiler
   - Güncel olmayan örnekler
   - Broken links

---

## 📄 Lisans

MIT License - Detaylar için ana README'ye bakın.

## ⚡ Hızlı Linkler

- 📦 [PyPI Package](https://pypi.org/project/axion/) (yakında)
- 🐛 [Issue Tracker](https://github.com/your-repo/axion/issues)
- 💬 [Discussions](https://github.com/your-repo/axion/discussions)
- 📚 [API Reference](https://axion.readthedocs.io/) (yakında)

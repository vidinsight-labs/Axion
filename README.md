# CPU Load Balancer v3

**Basit, temiz ve takip edilebilir task execution engine**

CPU-bound ve IO-bound görevleri optimize eden, her component'in durumunu takip edebilen basit ve bakımı kolay bir Python execution engine.

## 🎯 Özellikler

- **Basit ve Temiz**: Gereksiz abstraction yok, anlaşılır kod
- **Modüler Yapı**: Her component kendi dosyası ve klasöründe
- **Takip Edilebilir**: Her component'in `get_status()` metodu var
- **Tek Interface**: Sadece `Engine` kullanılır
- **CPU/IO-Bound Optimizasyonu**: Görev tipine göre ayrı process havuzları
- **Otomatik Load Balancing**: En az yüklü worker'a görev yönlendirme
- **Graceful Shutdown**: Güvenli kapatma
- **Cross-Platform**: Windows, macOS, Linux desteği

## 📦 Kurulum

### Gereksinimler

- Python 3.8 veya üzeri
- **psutil>=5.9.0** (sistem kaynaklarını izlemek için - zorunlu)
- **requests>=2.31.0** (sadece network I/O benchmark testleri için - opsiyonel)

### Kurulum

```bash
# Geliştirme için
git clone <repo-url>
cd cpu-load-balancer
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Projeyi kur (editable mode)
pip install -e .

# Bağımlılıkları kur
pip install -r requirements.txt
```

### Geliştirme Bağımlılıkları (Opsiyonel)

Test ve geliştirme için:

```bash
pip install -r requirements-dev.txt
```

## 🚀 Hızlı Başlangıç

### Basit Kullanım

```python
from axion import Engine, Task, TaskType

# Engine oluştur ve başlat
engine = Engine()
engine.start()

# Görev oluştur
task = Task(
    script_path="/path/to/script.py",
    params={"key": "value"},
    task_type=TaskType.IO_BOUND
)

# Görev gönder
task_id = engine.submit_task(task)

# Sonuç al
result = engine.get_result(task_id, timeout=30)

if result and result.is_success:
    print(f"Sonuç: {result.data}")
else:
    print(f"Hata: {result.error if result else 'Timeout'}")

# Engine'i kapat
engine.shutdown()
```

### Context Manager ile Kullanım

```python
from axion import Engine, Task, TaskType

with Engine() as engine:
    task = Task(
        script_path="/path/to/script.py",
        params={"value": 10},
        task_type=TaskType.IO_BOUND
    )

    task_id = engine.submit_task(task)
    result = engine.get_result(task_id, timeout=30)

    if result:
        print(f"Sonuç: {result.data}")
```

### Sistem Durumunu İzleme

```python
from axion import Engine

engine = Engine()
engine.start()

# Tüm sistem durumu
status = engine.get_status()
print(f"Engine running: {status['engine']['is_running']}")
print(f"Input queue size: {status['components']['input_queue']['metrics']['size']}")
print(f"Active tasks: {status['components']['process_pool']['metrics']['active_tasks']}")

# Belirli component durumu
queue_status = engine.get_component_status("input_queue")
print(f"Queue health: {queue_status.health.value}")
print(f"Queue metrics: {queue_status.metrics}")

# Sistem sağlık durumu
health = engine.get_health()
print(f"Overall health: {health.overall_health.value}")
print(f"Healthy components: {health.healthy_count}")
```

## 📁 Proje Yapısı

```
src/cpu-load-balancer/
├── __init__.py              # Public API
├── core/                    # Ana engine ve temel sınıflar
│   ├── engine.py            # Engine (tek interface)
│   ├── task.py              # Task ve Result
│   ├── enums.py             # Enum'lar
│   ├── exceptions.py        # Exception'lar
│   └── queue_controller.py  # Queue controller
├── config/                  # Yapılandırma
│   └── engine_config.py     # Tek config sınıfı
├── queue/                   # Queue component'leri
│   ├── input_queue.py       # InputQueue + get_status()
│   └── output_queue.py      # OutputQueue + get_status()
├── worker/                  # Worker component'leri
│   ├── pool.py              # ProcessPool + get_status()
│   ├── process.py            # WorkerProcess + get_status()
│   └── thread.py            # WorkerThread
├── executor/                # Executor component'leri
│   ├── base.py              # BaseExecutor
│   └── python_executor.py   # PythonExecutor + get_status()
└── monitoring/              # Monitoring
    └── status.py            # ComponentStatus, SystemStatus
```

## 🏗️ Mimari

### Genel Akış

```
Kullanıcı
    │
    ├─► Engine.submit_task(task)
    │       │
    │       ▼
    │   InputQueue.put(task)
    │       │
    │       ▼
    │   QueueController (izler)
    │       │
    │       ▼
    │   ProcessPool.submit_task(task)
    │       │
    │       ▼
    │   WorkerProcess → WorkerThread
    │       │
    │       ▼
    │   PythonExecutor.execute(task)
    │       │
    │       ▼
    │   OutputQueue.put(result)
    │
    └─◄ Engine.get_result(task_id)
            │
            └─► OutputQueue.get(result)
```

### Component Yapısı

Her component:
- Kendi dosyası ve klasöründe
- `get_status()` metodu var
- Kendi metriklerini tutar
- Sağlık durumunu hesaplar

## 📝 Script Interface

Python script'leri şu interface'i uygulamalıdır:

```python
# my_script.py

def module():
    """Module factory fonksiyonu"""
    return MyModule()


class MyModule:
    """Görev modülü"""
    
    def run(self, params):
        """
        Görev çalıştırma fonksiyonu
        
        Args:
            params: Parametreler dict'i
            
        Returns:
            Any: Sonuç (JSON serializable olmalı)
        """
        value = params.get("value", 0)
        result = value * 2
        return {"result": result, "status": "ok"}
```

## ⚙️ Yapılandırma

### EngineConfig

```python
from axion import Engine, EngineConfig

# Varsayılan config
engine = Engine()

# Özel config
config = EngineConfig(
    input_queue_size=2000,
    output_queue_size=5000,
    cpu_bound_count=2,
    io_bound_count=4,
    cpu_bound_task_limit=1,
    io_bound_task_limit=20,
    log_level="INFO"
)

engine = Engine(config)
```

### Config Parametreleri

- **Queue Ayarları**:
  - `input_queue_size`: Input queue boyutu (varsayılan: 1000)
  - `output_queue_size`: Output queue boyutu (varsayılan: 10000)
  - `queue_poll_timeout`: Queue polling timeout (varsayılan: 1.0)
  - `max_queue_full_retries`: Queue dolu olduğunda retry sayısı (varsayılan: 3)

- **Worker Ayarları**:
  - `cpu_bound_count`: CPU-bound worker sayısı (None = otomatik)
  - `io_bound_count`: IO-bound worker sayısı (None = otomatik)
  - `cpu_bound_task_limit`: CPU-bound worker başına thread limiti (varsayılan: 1)
  - `io_bound_task_limit`: IO-bound worker başına thread limiti (varsayılan: 20)
  - `health_check_interval`: Health check aralığı (varsayılan: 0.2)

- **Monitoring**:
  - `enable_metrics`: Metrik toplama (varsayılan: True)
  - `log_level`: Log seviyesi (varsayılan: "INFO")

## 🧪 Test

```bash
# Tüm testleri çalıştır
pytest tests/ -v

# Sadece core testler
pytest tests/test_core_classes.py -v

# Sadece engine testler
pytest tests/test_engine.py -v
```

## 📊 Benchmark

Sistem performansını ölçmek için benchmark testleri mevcuttur:

```bash
# Throughput testi
python benchmarks/throughput_test.py

# Ölçeklenebilirlik testi
python benchmarks/scalability_test.py

# Batch işlem testi
python benchmarks/batch_test.py
```

### Benchmark Sonuçlarını Yorumlama

Benchmark sonuçlarını nasıl yorumlayacağınızı öğrenmek için:

📖 **[Benchmark Sonuçlarını Yorumlama Kılavuzu](./benchmarks/benchmark_results_interpretation.md)**

Bu kılavuz şunları içerir:
- Throughput sonuçlarını yorumlama
- Latency sonuçlarını yorumlama
- Başarı oranı analizi
- Ölçeklenebilirlik değerlendirmesi
- Batch işlem analizi
- Kırmızı bayraklar (red flags)
- Optimizasyon önerileri

Daha fazla bilgi için: [Benchmark Dokümantasyonu](./benchmarks/README.md)

## 📊 Monitoring

### Component Durumları

Her component'in durumunu takip edebilirsiniz:

```python
# Tüm component durumları
status = engine.get_status()
for name, comp_status in status["components"].items():
    print(f"{name}: {comp_status['health']}")

# Belirli component
queue_status = engine.get_component_status("input_queue")
print(f"Queue size: {queue_status.metrics['size']}")
print(f"Queue fullness: {queue_status.metrics['fullness']}")
```

### Sağlık Durumu

```python
health = engine.get_health()
print(f"Overall: {health.overall_health.value}")
print(f"Healthy: {health.healthy_count}")
print(f"Unhealthy: {health.unhealthy_count}")
```

## 🔧 Geliştirme

### Proje Yapısı

- **Modüler**: Her component ayrı dosya ve klasör
- **Takip Edilebilir**: Her component'in `get_status()` metodu
- **Basit**: Gereksiz abstraction yok
- **Temiz**: Anlaşılır ve bakımı kolay kod

### Yeni Component Ekleme

1. Component'i kendi klasöründe oluştur
2. `get_status()` metodunu implement et
3. Engine'e ekle

## 📄 Lisans

MIT License

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Commit yapın (`git commit -m 'Add amazing feature'`)
4. Push yapın (`git push origin feature/amazing-feature`)
5. Pull Request açın

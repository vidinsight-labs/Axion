<div align="center">

# Axion

**Gelişmiş Task Execution Engine**

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

*Yüksek performanslı, otomatik ölçeklenen, workflow destekli paralel işlem motoru*

[Hızlı Başlangıç](#-hızlı-başlangıç) •
[Özellikler](#-temel-özellikler) •
[Kurulum](#-kurulum) •
[Dokümantasyon](#-dokümantasyon) •
[Örnekler](#-kullanım-örnekleri)

</div>

---

## 🎯 Nedir?

**Axion**, Python için geliştirilmiş, production-ready bir **Task Execution Engine**'dir. CPU-bound ve IO-bound işlemleri optimize eden, otomatik ölçeklenen worker pool'ları ve DAG tabanlı workflow desteği ile karmaşık paralel işlemleri basitleştirir.

### Neden Axion?

- 🚀 **Yüksek Performans**: Work-stealing algoritması ve intelligent load balancing
- 🔄 **Otomatik Ölçekleme**: Sistem yüküne göre worker'ları dinamik olarak yönetir
- 📊 **Workflow Desteği**: DAG tabanlı görev bağımlılıkları ve veri aktarımı
- 💪 **Production Ready**: Kapsamlı hata yönetimi, logging ve monitoring
- 🎛️ **Esnek Yapılandırma**: CPU/IO ayrımı, queue boyutları, backpressure kontrolü

---

## ✨ Temel Özellikler

### 🔥 Core Features

| Özellik | Açıklama |
|---------|----------|
| **CPU/IO Ayrımı** | CPU-intensive ve IO-intensive işleri ayrı havuzlarda optimize eder |
| **Auto-Scaling** | Sistem yüküne ve queue durumuna göre otomatik worker ekleme/çıkarma |
| **Work Stealing** | Boş worker'lar yüklü worker'lardan görev çalarak load balancing sağlar |
| **Workflow (DAG)** | Görevler arası bağımlılıklar ve otomatik veri aktarımı |
| **Backpressure** | Sistem aşırı yüklüyken akıllı görev reddi ve throttling |

### 🎨 Advanced Features

- ✅ **Multi-level Queue System**: Sharded queues per worker
- ✅ **CPU Affinity**: Process'leri belirli CPU core'larına sabitleme
- ✅ **Process Priority**: Nice level ayarlama
- ✅ **Result Caching**: FIFO result cache (5000 limit)
- ✅ **Module Caching**: Script module'lerini cache'leyerek hızlandırma
- ✅ **Metrics & Monitoring**: Velocity tracking, throughput, latency metrikleri

---

## 📦 Kurulum

### Gereksinimler

- **Python**: 3.8 veya üzeri
- **İşletim Sistemi**: Windows, Linux, macOS
- **Bağımlılıklar**: `psutil`

### Hızlı Kurulum

```bash
# Repository'yi klonlayın
git clone https://github.com/vidinsight-labs/axion.git
cd axion

# Temel kurulum
pip install -e .
```

### Opsiyonel Bağımlılıklar

```bash
# Machine Learning özellikleri (TensorFlow)
pip install -e ".[ml]"

# Geliştirme araçları (pytest, black, mypy, vb.)
pip install -e ".[dev]"

# Dokümantasyon araçları (Sphinx)
pip install -e ".[docs]"

# Benchmark araçları (matplotlib, pandas)
pip install -e ".[benchmark]"

# Tümünü yükle
pip install -e ".[all]"
```

### Manuel Kurulum

```bash
# Sadece temel bağımlılıklar
pip install psutil>=5.9.0
```

---

## 🚀 Hızlı Başlangıç

### Basit Kullanım

```python
from axion import Engine, Task, TaskType

# Engine'i başlat
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
        print(f"✅ Sonuç: {result.data}")
    else:
        print(f"❌ Hata: {result.error if result else 'Timeout'}")
```

### Task Script Formatı

```python
# my_script.py
def main(params, context):
    """
    Axion tarafından çağrılan ana fonksiyon
    
    Args:
        params (dict): Görev parametreleri
        context (ExecutionContext): Worker bilgisi (task_id, worker_id)
    
    Returns:
        dict: JSON serializable sonuç
    """
    value = params.get("value", 0)
    result = value * 2
    
    # Worker bilgisini kullanabilirsiniz
    print(f"Task {context.task_id} running on {context.worker_id}")
    
    return {
        "result": result,
        "processed_by": context.worker_id
    }
```

---

## 💡 Kullanım Örnekleri

### 1. CPU-Bound ve IO-Bound Görevler

```python
from axion import Engine, EngineConfig, Task, TaskType

# Özel yapılandırma (8 çekirdekli CPU için)
config = EngineConfig(
    cpu_bound_count=4,      # 4 CPU worker (4 process = 4 çekirdek)
    io_bound_count=2,       # 2 IO worker (2 process = 2 çekirdek)
    cpu_bound_task_limit=1, # CPU worker başına 1 thread
    io_bound_task_limit=25  # IO worker başına 25 thread (toplam 50 IO thread)
)

with Engine(config) as engine:
    # CPU-bound görev (hesaplama yoğun)
    cpu_task = Task.create(
        script_path="heavy_computation.py",
        params={"n": 1000000},
        task_type=TaskType.CPU_BOUND
    )
    
    # IO-bound görev (network, dosya işlemleri)
    io_task = Task.create(
        script_path="download_file.py",
        params={"url": "https://example.com/data.json"},
        task_type=TaskType.IO_BOUND
    )
    
    # Görevleri gönder
    cpu_id = engine.submit_task(cpu_task)
    io_id = engine.submit_task(io_task)
    
    # Sonuçları al
    cpu_result = engine.get_result(cpu_id)
    io_result = engine.get_result(io_id)
```

### 2. Workflow (DAG) Kullanımı

```python
from axion import Engine, Task, TaskType

with Engine() as engine:
    # Task A: Veri yükle
    task_a = Task.create(
        script_path="load_data.py",
        params={"source": "data.csv"},
        task_type=TaskType.IO_BOUND
    )
    
    # Task B: Veriyi işle (A'ya bağımlı)
    task_b = Task.create(
        script_path="process_data.py",
        params={"operation": "transform"},
        task_type=TaskType.CPU_BOUND,
        dependencies=[task_a.id]  # A tamamlanınca başla
    )
    
    # Task C: Sonucu kaydet (B'ye bağımlı)
    task_c = Task.create(
        script_path="save_result.py",
        params={"output": "result.json"},
        task_type=TaskType.IO_BOUND,
        dependencies=[task_b.id]  # B tamamlanınca başla
    )
    
    # Workflow olarak gönder
    task_ids = engine.submit_workflow([task_a, task_b, task_c])
    
    # Otomatik akış:
    # task_a çalışır → tamamlanır
    # → task_b otomatik başlar → tamamlanır
    # → task_c otomatik başlar
    
    # Son sonucu bekle
    final_result = engine.get_result(task_c.id, timeout=60)
```

### 3. Batch İşlemler

```python
from axion import Engine, Task, TaskType

with Engine() as engine:
    # 100 görev oluştur
    tasks = []
    for i in range(100):
        task = Task.create(
            script_path="process_item.py",
            params={"item_id": i},
            task_type=TaskType.CPU_BOUND
        )
        tasks.append(task)
    
    # Hepsini gönder
    task_ids = [engine.submit_task(task) for task in tasks]
    
    # Hepsinin bitmesini bekle
    results = []
    for task_id in task_ids:
        result = engine.get_result(task_id, timeout=120)
        if result and result.is_success:
            results.append(result.data)
    
    print(f"✅ {len(results)}/100 görev başarılı")
```

### 4. Status Monitoring

```python
from axion import Engine
import time

with Engine() as engine:
    # Görevleri gönder...
    
    # Status'u periyodik kontrol et
    while True:
        status = engine.get_status()
        
        print(f"""
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        Workers:
          CPU: {status.cpu_workers} (aktif: {status.cpu_active_threads})
          IO:  {status.io_workers} (aktif: {status.io_active_threads})
        
        Görevler:
          Bekleyen:    {status.pending_tasks}
          Çalışan:     {status.running_tasks}
          Tamamlanan:  {status.completed_tasks}
          Başarısız:   {status.failed_tasks}
        
        Sistem:
          Backpressure: {status.backpressure_state}
          Throughput:   {status.throughput:.2f} görev/s
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """)
        
        if status.pending_tasks == 0 and status.running_tasks == 0:
            break
        
        time.sleep(2)
```

---

## 📚 Dokümantasyon

### 🚀 Başlangıç Kılavuzları

| Doküman | İçerik |
|---------|--------|
| **[Module Overview](docs/module_overview.md)** | Axion'a genel bakış, temel kavramlar, hızlı başlangıç |
| **[Examples Guide](docs/examples_guide.md)** | Detaylı kullanım örnekleri, best practices |
| **[Integration Guide](docs/integration_guide.md)** | Mevcut projelere entegrasyon, gerçek senaryolar |

### 🏗️ Mimari ve İç Yapı

| Doküman | İçerik |
|---------|--------|
| **[Architecture](docs/architecture.md)** | Sistem mimarisi, bileşenler, algoritmalar |
| **[Data Flow](docs/data_flow.md)** | Veri akışı, queue yönetimi, process iletişimi |

### 🔧 Operasyon ve Troubleshooting

| Doküman | İçerik |
|---------|--------|
| **[Output Interpretation](docs/output_interpretation.md)** | Log mesajları, metrikler, performans analizi |
| **[Troubleshooting](docs/troubleshooting.md)** | Yaygın sorunlar ve çözümleri |

### 📊 Demo ve Benchmark

| Doküman | İçerik |
|---------|--------|
| **[Demo Guide](docs/demo_guide.md)** | Demo senaryoları, örnek projeler |
| **[Benchmark Guide](benchmarks/benchmark_guide.md)** | Performans testleri, benchmark sonuçları |

---

## ⚙️ Yapılandırma

### Mimari Anlayışı

**Axion'da 2 seviyeli paralellik vardır:**

```
┌─────────────────────────────────────────────────┐
│  Engine                                         │
│  ├─ CPU Workers (Processes)                     │
│  │  ├─ Process 1 → ThreadPool (N threads)      │
│  │  ├─ Process 2 → ThreadPool (N threads)      │
│  │  └─ Process 3 → ThreadPool (N threads)      │
│  │                                               │
│  └─ IO Workers (Processes)                      │
│     ├─ Process 1 → ThreadPool (M threads)      │
│     └─ Process 2 → ThreadPool (M threads)      │
└─────────────────────────────────────────────────┘

Process Sayısı = Çekirdek Kullanımı
Thread Sayısı = Eşzamanlı İşlem Kapasitesi
```

**Kritik Noktalar:**
- ⚠️ **1 worker = 1 process = 1 CPU çekirdeği**
- ✅ **Thread'ler process içinde çalışır (hafif, ucuz)**
- 🎯 **CPU-bound**: Az process, az thread (çekirdek başına 1)
- 🎯 **IO-bound**: Az process, çok thread (IO beklerken thread ucuz)

**Örnek Hesaplama (8 çekirdekli CPU):**
```python
config = EngineConfig(
    cpu_bound_count=4,        # 4 çekirdek
    io_bound_count=2,         # 2 çekirdek
    # Toplam: 6 çekirdek (2 çekirdek reserve)
    
    cpu_bound_task_limit=1,   # 4 × 1 = 4 eşzamanlı CPU görevi
    io_bound_task_limit=25    # 2 × 25 = 50 eşzamanlı IO görevi
)
```

### EngineConfig Parametreleri

```python
from axion import EngineConfig

config = EngineConfig(
    # Worker Sayıları (Her worker = 1 process = 1 çekirdek!)
    cpu_bound_count=4,              # CPU worker sayısı (varsayılan: 1)
    io_bound_count=2,               # IO worker sayısı (varsayılan: CPU-1)
    
    # Thread Limitleri
    cpu_bound_task_limit=1,         # CPU worker başına thread (varsayılan: 1)
    io_bound_task_limit=50,         # IO worker başına thread (varsayılan: 20)
    
    # Queue Boyutları
    input_queue_size=5000,          # Input queue boyutu (varsayılan: 1000)
    output_queue_size=20000,        # Output queue boyutu (varsayılan: 10000)
    
    # Logging
    log_level="INFO",               # Log seviyesi: DEBUG, INFO, WARNING, ERROR
    
    # Diğer
    queue_poll_timeout=1.0,         # Queue polling timeout (saniye)
)
```

### Önerilen Yapılandırmalar

> ⚠️ **ÖNEMLİ**: Her worker bir PROCESS'tir, yani bir çekirdek kullanır!
> - `cpu_bound_count=4` → 4 process = 4 çekirdek
> - `io_bound_count=2` → 2 process = 2 çekirdek
> - Toplam çekirdek kullanımı = cpu_bound_count + io_bound_count

**CPU-Bound Ağırlıklı İşler (Data Processing, ML) - 8 çekirdekli CPU:**
```python
config = EngineConfig(
    cpu_bound_count=6,        # 6 çekirdek CPU işleri için
    io_bound_count=2,         # 2 çekirdek IO işleri için
    cpu_bound_task_limit=1,   # CPU worker başına 1 thread (CPU-bound için ideal)
    io_bound_task_limit=20    # 2 process × 20 thread = 40 eşzamanlı IO işlemi
)
```

**IO-Bound Ağırlıklı İşler (Web Scraping, API Calls) - 8 çekirdekli CPU:**
```python
config = EngineConfig(
    cpu_bound_count=2,        # 2 çekirdek CPU işleri için (az)
    io_bound_count=4,         # 4 çekirdek IO işleri için (çoğunluk)
    cpu_bound_task_limit=1,   # CPU worker başına 1 thread
    io_bound_task_limit=50    # 4 process × 50 thread = 200 eşzamanlı IO işlemi
)
```

**Dengeli İş Yükü (ETL, Mixed Workloads) - 8 çekirdekli CPU:**
```python
config = EngineConfig(
    cpu_bound_count=4,        # 4 çekirdek CPU işleri için
    io_bound_count=3,         # 3 çekirdek IO işleri için (toplam 7)
    cpu_bound_task_limit=1,   # CPU worker başına 1 thread
    io_bound_task_limit=30    # 3 process × 30 thread = 90 eşzamanlı IO işlemi
)
```

> 💡 **İpucu**: IO-bound işler için thread sayısını artırın, process sayısını değil!

---

## 🧪 Test ve Development

### Testleri Çalıştırma

```bash
# Tüm testleri çalıştır
pytest

# Coverage ile
pytest --cov=axion --cov-report=html

# Sadece hızlı testler
pytest -m "not slow"

# Paralel test
pytest -n auto

# Verbose mode
pytest -vv
```

### Code Quality Checks

```bash
# Format kontrolü
black --check axion/ tests/

# Otomatik format
black axion/ tests/

# Import sıralama
isort axion/ tests/

# Linting
flake8 axion/ tests/
pylint axion/

# Type checking
mypy axion/
```

### Benchmark Çalıştırma

```bash
# Throughput testi
python benchmarks/throughput_test.py

# Scalability testi
python benchmarks/scalability_test.py

# IO performans testi
python benchmarks/io_bound_performance_test.py

# Complex workflow testi
python benchmarks/complex_workflow_test.py
```

---

## 🎯 Performans

### Benchmark Sonuçları

**Throughput** (Intel Core i7-10700K, 8 cores):
- **CPU-Bound**: ~200-400 görev/saniye
- **IO-Bound**: ~1,000-2,000 görev/saniye
- **Mixed**: ~500-800 görev/saniye

**Latency**:
- **P50**: <50ms
- **P95**: <100ms
- **P99**: <200ms

**Scalability**:
- Linear scaling 1-8 CPU workers (CPU-bound, 8 çekirdek sınırı)
- Linear scaling 1-4 IO workers (IO-bound, 4 process yeterli)
- Thread scaling: 1-100 threads per IO worker
- Auto-scaling response time: <500ms

> 📊 Detaylı benchmark sonuçları için: [Benchmark Guide](benchmarks/benchmark_guide.md)

---

## 🤝 Katkıda Bulunma

Katkılarınızı bekliyoruz! Lütfen şu adımları izleyin:

1. **Fork** edin
2. **Feature branch** oluşturun (`git checkout -b feature/amazing-feature`)
3. Değişikliklerinizi **commit** edin (`git commit -m 'feat: Add amazing feature'`)
4. Branch'inizi **push** edin (`git push origin feature/amazing-feature`)
5. **Pull Request** açın

### Development Setup

```bash
# Repository'yi klonlayın
git clone https://github.com/vidinsight-labs/axion.git
cd axion

# Development bağımlılıklarını kurun
pip install -e ".[dev]"

# Pre-commit hooks (opsiyonel)
pip install pre-commit
pre-commit install

# Testleri çalıştırın
pytest
```

### Code Standards

- ✅ Python 3.8+ uyumlu
- ✅ Type hints kullanın
- ✅ Docstring'ler Türkçe
- ✅ Test coverage >70%
- ✅ Black formatting
- ✅ Flake8 compliant

---

## 📄 Lisans

Bu proje **Apache License 2.0** altında lisanslanmıştır. Detaylar için [LICENSE](LICENSE) dosyasına bakın.

### Lisans Özellikleri

- ✅ Ticari kullanım izni
- ✅ Modifikasyon izni
- ✅ Dağıtım izni
- ✅ Patent hakları koruması
- ✅ Özel kullanım izni
- ⚠️ Trademark kullanımı kısıtlı
- ⚠️ Sorumluluk reddi
- ℹ️ Değişiklikleri belgeleme zorunluluğu

---

## 📞 İletişim ve Destek

- 📧 **Email**: development@vidinsight.com.tr
- 🐛 **Issues**: [GitHub Issues](https://github.com/vidinsight-labs/axion/issues)
- 📖 **Documentation**: [GitHub Docs](https://github.com/vidinsight-labs/axion/tree/main/docs)

---

## 🙏 Teşekkürler

Axion'u kullandığınız için teşekkür ederiz! Geri bildirimleriniz bizim için çok değerli.

⭐ Projeyi beğendiyseniz **star** vermeyi unutmayın!

---

## ⚡ Hızlı Linkler

- 📦 [PyPI Package](https://pypi.org/project/axion/) (yakında)
- 🐛 [Issue Tracker](https://github.com/vidinsight-labs/Axion/issues)
- 📚 [API Reference](https://axion.readthedocs.io/) (yakında)

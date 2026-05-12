<div align="center">

# Axion

**Gelişmiş Görev Yürütme Motoru**

[![Python Versiyonu](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Lisans](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Kod Stili: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

*Yüksek performanslı, otomatik ölçeklenen, iş akışı destekli paralel işlem motoru*

[Hızlı Başlangıç](#-hızlı-başlangıç) •
[Özellikler](#-temel-özellikler) •
[Kurulum](#-kurulum) •
[Dokümantasyon](#-dokümantasyon) •
[Örnekler](#-kullanım-örnekleri)

</div>

---

## 🎯 Nedir?

**Axion**, Python için geliştirilmiş, production-ready bir **Görev Yürütme Motoru**'dur. CPU-yoğun ve IO-yoğun işlemleri optimize eden, otomatik ölçeklenen worker havuzları ve DAG tabanlı iş akışı desteği ile karmaşık paralel işlemleri basitleştirir.

### Neden Axion?

- 🚀 **Yüksek Performans**: Work-stealing algoritması ve akıllı yük dengeleme
- 🔄 **Otomatik Ölçekleme**: Sistem yüküne göre worker'ları dinamik olarak yönetir
- 📊 **İş Akışı Desteği**: DAG tabanlı görev bağımlılıkları ve veri aktarımı
- 💪 **Production Hazır**: Kapsamlı hata yönetimi, loglama ve izleme
- 🎛️ **Esnek Yapılandırma**: CPU/IO ayrımı, kuyruk boyutları, arka basınç kontrolü

---

## ✨ Temel Özellikler

### 🔥 Çekirdek Özellikler

| Özellik | Açıklama |
|---------|----------|
| **CPU/IO Ayrımı** | CPU-yoğun ve IO-yoğun işleri ayrı havuzlarda optimize eder |
| **Otomatik Ölçekleme** | Sistem yüküne ve kuyruk durumuna göre otomatik worker ekleme/çıkarma |
| **Work Stealing** | Boş worker'lar yüklü worker'lardan görev çalarak yük dengeleme sağlar |
| **İş Akışı (DAG)** | Görevler arası bağımlılıklar ve otomatik veri aktarımı |
| **Arka Basınç** | Sistem aşırı yüklüyken akıllı görev reddi ve kısıtlama |

### 🎨 Gelişmiş Özellikler

- ✅ **Çok Seviyeli Kuyruk Sistemi**: Worker başına ayrı kuyruklar
- ✅ **CPU İlgisi**: Process'leri belirli CPU çekirdeklerine sabitleme
- ✅ **Process Önceliği**: Nice seviyesi ayarlama
- ✅ **Sonuç Önbellekleme**: FIFO sonuç önbelleği (5000 limit)
- ✅ **Modül Önbellekleme**: Script modüllerini önbelleğe alarak hızlandırma
- ✅ **Metrikler ve İzleme**: Hız takibi, verimlilik, gecikme metrikleri

---

## 📦 Kurulum

### Gereksinimler

- **Python**: 3.8 veya üzeri
- **İşletim Sistemi**: Windows, Linux, macOS
- **Bağımlılıklar**: `psutil`

### Hızlı Kurulum

```bash
# Depoyu klonlayın
git clone https://github.com/vidinsight-labs/axion.git
cd axion

# Temel kurulum
pip install -e .
```

### Opsiyonel Bağımlılıklar

```bash
# Makine öğrenimi özellikleri (TensorFlow)
pip install -e ".[ml]"

# Geliştirme araçları (pytest, black, mypy, vb.)
pip install -e ".[dev]"

# Dokümantasyon araçları (Sphinx)
pip install -e ".[docs]"

# Performans test araçları (matplotlib, pandas)
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

# Motor'u başlat
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

### Görev Script Formatı

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
    print(f"Görev {context.task_id}, {context.worker_id} üzerinde çalışıyor")
    
    return {
        "result": result,
        "processed_by": context.worker_id
    }
```

---

## 💡 Kullanım Örnekleri

### 1. CPU-Yoğun ve IO-Yoğun Görevler

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
    # CPU-yoğun görev (hesaplama yoğun)
    cpu_task = Task.create(
        script_path="heavy_computation.py",
        params={"n": 1000000},
        task_type=TaskType.CPU_BOUND
    )
    
    # IO-yoğun görev (ağ, dosya işlemleri)
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

### 2. İş Akışı (DAG) Kullanımı

```python
from axion import Engine, Task, TaskType

with Engine() as engine:
    # Görev A: Veri yükle
    task_a = Task.create(
        script_path="load_data.py",
        params={"source": "data.csv"},
        task_type=TaskType.IO_BOUND
    )
    
    # Görev B: Veriyi işle (A'ya bağımlı)
    task_b = Task.create(
        script_path="process_data.py",
        params={"operation": "transform"},
        task_type=TaskType.CPU_BOUND,
        dependencies=[task_a.id]  # A tamamlanınca başla
    )
    
    # Görev C: Sonucu kaydet (B'ye bağımlı)
    task_c = Task.create(
        script_path="save_result.py",
        params={"output": "result.json"},
        task_type=TaskType.IO_BOUND,
        dependencies=[task_b.id]  # B tamamlanınca başla
    )
    
    # İş akışı olarak gönder
    task_ids = engine.submit_workflow([task_a, task_b, task_c])
    
    # Otomatik akış:
    # task_a çalışır → tamamlanır
    # → task_b otomatik başlar → tamamlanır
    # → task_c otomatik başlar
    
    # Son sonucu bekle
    final_result = engine.get_result(task_c.id, timeout=60)
```

### 3. Toplu İşlemler

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

### 4. Durum İzleme

```python
from axion import Engine
import time

with Engine() as engine:
    # Görevleri gönder...
    
    # Durumu periyodik kontrol et
    while True:
        status = engine.get_status()
        
        print(f"""
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        Worker'lar:
          CPU: {status.cpu_workers} (aktif: {status.cpu_active_threads})
          IO:  {status.io_workers} (aktif: {status.io_active_threads})
        
        Görevler:
          Bekleyen:    {status.pending_tasks}
          Çalışan:     {status.running_tasks}
          Tamamlanan:  {status.completed_tasks}
          Başarısız:   {status.failed_tasks}
        
        Sistem:
          Arka Basınç: {status.backpressure_state}
          Verimlilik:  {status.throughput:.2f} görev/s
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
| **[Modül Özeti](docs/module_overview.md)** | Axion'a genel bakış, temel kavramlar, hızlı başlangıç |
| **[Örnek Kılavuzu](docs/examples_guide.md)** | Detaylı kullanım örnekleri, en iyi uygulamalar |
| **[Entegrasyon Kılavuzu](docs/integration_guide.md)** | Mevcut projelere entegrasyon, gerçek senaryolar |

### 🏗️ Mimari ve İç Yapı

| Doküman | İçerik |
|---------|--------|
| **[Mimari](docs/architecture.md)** | Sistem mimarisi, bileşenler, algoritmalar |
| **[Veri Akışı](docs/data_flow.md)** | Veri akışı, kuyruk yönetimi, process iletişimi |

### 🔧 Operasyon ve Sorun Giderme

| Doküman | İçerik |
|---------|--------|
| **[Çıktı Yorumlama](docs/output_interpretation.md)** | Log mesajları, metrikler, performans analizi |
| **[Sorun Giderme](docs/troubleshooting.md)** | Yaygın sorunlar ve çözümleri |

### 📊 Demo ve Performans Testi

| Doküman | İçerik |
|---------|--------|
| **[Demo Kılavuzu](docs/demo_guide.md)** | Demo senaryoları, örnek projeler |
| **[Performans Testi Kılavuzu](benchmarks/benchmark_guide.md)** | Performans testleri, test sonuçları |

---

## ⚙️ Yapılandırma

### Mimari Anlayışı

**Axion'da 2 seviyeli paralellik vardır:**

```
┌─────────────────────────────────────────────────┐
│  Motor (Engine)                                 │
│  ├─ CPU Worker'ları (Process'ler)              │
│  │  ├─ Process 1 → Thread Havuzu (N thread)   │
│  │  ├─ Process 2 → Thread Havuzu (N thread)   │
│  │  └─ Process 3 → Thread Havuzu (N thread)   │
│  │                                               │
│  └─ IO Worker'ları (Process'ler)               │
│     ├─ Process 1 → Thread Havuzu (M thread)   │
│     └─ Process 2 → Thread Havuzu (M thread)   │
└─────────────────────────────────────────────────┘

Process Sayısı = Çekirdek Kullanımı
Thread Sayısı = Eşzamanlı İşlem Kapasitesi
```

**Kritik Noktalar:**
- ⚠️ **1 worker = 1 process = 1 CPU çekirdeği**
- ✅ **Thread'ler process içinde çalışır (hafif, ucuz)**
- 🎯 **CPU-yoğun**: Az process, az thread (çekirdek başına 1)
- 🎯 **IO-yoğun**: Az process, çok thread (IO beklerken thread ucuz)

**Örnek Hesaplama (8 çekirdekli CPU):**
```python
config = EngineConfig(
    cpu_bound_count=4,        # 4 çekirdek
    io_bound_count=2,         # 2 çekirdek
    # Toplam: 6 çekirdek (2 çekirdek rezerv)
    
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
    io_bound_task_limit=25,         # IO worker başına thread (varsayılan: 20)
    
    # Kuyruk Boyutları
    input_queue_size=5000,          # Giriş kuyruğu boyutu (varsayılan: 1000)
    output_queue_size=20000,        # Çıkış kuyruğu boyutu (varsayılan: 10000)
    
    # Loglama
    log_level="INFO",               # Log seviyesi: DEBUG, INFO, WARNING, ERROR
    
    # Diğer
    queue_poll_timeout=1.0,         # Kuyruk polling timeout (saniye)
)
```

### Önerilen Yapılandırmalar

> ⚠️ **ÖNEMLİ**: Her worker bir PROCESS'tir, yani bir çekirdek kullanır!
> - `cpu_bound_count=4` → 4 process = 4 çekirdek
> - `io_bound_count=2` → 2 process = 2 çekirdek
> - Toplam çekirdek kullanımı = cpu_bound_count + io_bound_count

**CPU-Yoğun İşler (Veri İşleme, ML) - 8 çekirdekli CPU:**
```python
config = EngineConfig(
    cpu_bound_count=6,        # 6 çekirdek CPU işleri için
    io_bound_count=2,         # 2 çekirdek IO işleri için
    cpu_bound_task_limit=1,   # CPU worker başına 1 thread (CPU-yoğun için ideal)
    io_bound_task_limit=20    # 2 process × 20 thread = 40 eşzamanlı IO işlemi
)
```

**IO-Yoğun İşler (Web Kazıma, API Çağrıları) - 8 çekirdekli CPU:**
```python
config = EngineConfig(
    cpu_bound_count=2,        # 2 çekirdek CPU işleri için (az)
    io_bound_count=4,         # 4 çekirdek IO işleri için (çoğunluk)
    cpu_bound_task_limit=1,   # CPU worker başına 1 thread
    io_bound_task_limit=50    # 4 process × 50 thread = 200 eşzamanlı IO işlemi
)
```

**Dengeli İş Yükü (ETL, Karışık İşler) - 8 çekirdekli CPU:**
```python
config = EngineConfig(
    cpu_bound_count=4,        # 4 çekirdek CPU işleri için
    io_bound_count=3,         # 3 çekirdek IO işleri için (toplam 7)
    cpu_bound_task_limit=1,   # CPU worker başına 1 thread
    io_bound_task_limit=30    # 3 process × 30 thread = 90 eşzamanlı IO işlemi
)
```

> 💡 **İpucu**: IO-yoğun işler için thread sayısını artırın, process sayısını değil!

---

## 🧪 Test ve Geliştirme

### Testleri Çalıştırma

```bash
# Tüm testleri çalıştır
pytest

# Kapsama (coverage) ile
pytest --cov=axion --cov-report=html

# Sadece hızlı testler
pytest -m "not slow"

# Paralel test
pytest -n auto

# Ayrıntılı mod
pytest -vv
```

### Kod Kalitesi Kontrolleri

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

# Tip kontrolü
mypy axion/
```

### Performans Testi Çalıştırma

```bash
# Verimlilik testi
python benchmarks/throughput_test.py

# Ölçeklenebilirlik testi
python benchmarks/scalability_test.py

# IO performans testi
python benchmarks/io_bound_performance_test.py

# Karmaşık iş akışı testi
python benchmarks/complex_workflow_test.py
```

---

## 🎯 Performans

### Test Sonuçları

**Verimlilik** (Intel Core i7-10700K, 8 çekirdek):
- **CPU-Yoğun**: ~200-400 görev/saniye
- **IO-Yoğun**: ~1,000-2,000 görev/saniye
- **Karışık**: ~500-800 görev/saniye

**Gecikme**:
- **P50**: <50ms
- **P95**: <100ms
- **P99**: <200ms

**Ölçeklenebilirlik**:
- Doğrusal ölçekleme 1-8 CPU worker (CPU-yoğun, 8 çekirdek sınırı)
- Doğrusal ölçekleme 1-4 IO worker (IO-yoğun, 4 process yeterli)
- Thread ölçekleme: IO worker başına 1-100 thread
- Otomatik ölçekleme yanıt süresi: <500ms

> 📊 Detaylı test sonuçları için: [Performans Testi Kılavuzu](benchmarks/benchmark_guide.md)

---

## 🤝 Katkıda Bulunma

Katkılarınızı bekliyoruz! Lütfen şu adımları izleyin:

1. **Fork** edin
2. **Özellik branch'i** oluşturun (`git checkout -b feature/harika-ozellik`)
3. Değişikliklerinizi **commit** edin (`git commit -m 'feat: Harika özellik eklendi'`)
4. Branch'inizi **push** edin (`git push origin feature/harika-ozellik`)
5. **Pull Request** açın

### Geliştirme Ortamı Kurulumu

```bash
# Depoyu klonlayın
git clone https://github.com/vidinsight-labs/axion.git
cd axion

# Geliştirme bağımlılıklarını kurun
pip install -e ".[dev]"

# Pre-commit hooks (opsiyonel)
pip install pre-commit
pre-commit install

# Testleri çalıştırın
pytest
```

### Kod Standartları

- ✅ Python 3.8+ uyumlu
- ✅ Type hint'ler kullanın
- ✅ Docstring'ler Türkçe
- ✅ Test kapsama >70%
- ✅ Black formatlaması
- ✅ Flake8 uyumlu

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

## ⚠️ Sorumluluk Reddi

Axion "OLDUĞU GİBİ" sunulmaktadır. Hiçbir garanti verilmemektedir. Production kullanımından doğan riskler kullanıcıya aittir. Yazılım Apache License 2.0 kapsamında sorumluluk sınırlamaları ile dağıtılmaktadır.

---

## 📞 İletişim ve Destek

- 📧 **E-posta**: development@vidinsight.com.tr
- 🐛 **Sorunlar**: [GitHub Issues](https://github.com/vidinsight-labs/axion/issues)
- 📖 **Dokümantasyon**: [GitHub Docs](https://github.com/vidinsight-labs/axion/tree/main/docs)

---

## 🙏 Teşekkürler

Axion'u kullandığınız için teşekkür ederiz! Geri bildirimleriniz bizim için çok değerli.

⭐ Projeyi beğendiyseniz **yıldız** vermeyi unutmayın!

---

<div align="center">

**[⬆ Başa Dön](#axion)**

❤️ ile yapıldı - [VidInsight Labs](https://github.com/vidinsight-labs)

</div>

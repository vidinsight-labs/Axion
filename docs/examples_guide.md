# Examples Kılavuzu - Örnekler Nasıl Çalışır?

Bu dokümantasyon, CPU Load Balancer örneklerinin nasıl çalıştığını, ne çıktı verdiklerini ve bu çıktıların nasıl yorumlanacağını açıklar.

## İçindekiler

1. [Basit Örnek (Simple Example)](#basit-örnek)
2. [Gelişmiş Örnek (Advanced Example)](#gelişmiş-örnek)
3. [Çıktı Yorumlama](#çıktı-yorumlama)
4. [Yaygın Senaryolar](#yaygın-senaryolar)

---

## Basit Örnek

### Dosya: `examples/simple_example.py`

### Ne Yapar?

Bu örnek, CPU Load Balancer'ın en temel kullanımını gösterir:
- Engine oluşturma ve başlatma
- Tek bir görev gönderme
- Sonuç alma

### Nasıl Çalıştırılır?

```bash
cd examples
python3 simple_example.py
```

### Çıktı Örneği

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
   Sonuç: {'result': 84, 'original_value': 42, 'test_mode': True, 'task_id': 'fcccdf0b-562d-4985-a019-568dacd04ae7', 'worker_id': 'io-0', 'status': 'success'}

🛑 Engine kapatılıyor...
✅ Engine kapatıldı
```

### Çıktı Yorumlama

#### 1. Config Bilgisi
```
📊 Config:
   CPU-bound workers: 1
   IO-bound workers: 7
```
- **CPU-bound workers**: CPU yoğun görevler için worker sayısı
- **IO-bound workers**: IO yoğun görevler için worker sayısı (otomatik hesaplanır: CPU sayısı - 1)

#### 2. Engine Başlatma
```
🔧 Engine başlatılıyor...
✅ Engine başlatıldı
```
- Engine başarıyla başlatıldı
- Worker process'leri ve thread'ler hazır

#### 3. Görev Gönderme
```
📤 Görev gönderiliyor: fcccdf0b...
✅ Görev gönderildi: fcccdf0b...
```
- Görev oluşturuldu ve queue'ya eklendi
- `fcccdf0b...` görevin benzersiz ID'si (UUID'nin ilk 8 karakteri)

#### 4. Sonuç
```
✅ Görev başarılı!
   Sonuç: {'result': 84, 'original_value': 42, ...}
```
- **result**: İşlem sonucu (42 * 2 = 84)
- **original_value**: Gönderilen parametre (42)
- **test_mode**: Test modu aktif (True)
- **task_id**: Görevin tam ID'si
- **worker_id**: Görevi işleyen worker'ın ID'si (`io-0` = IO-bound worker 0)
- **status**: Görev durumu (`success`)

### Kod Akışı

```python
# 1. Config oluştur
config = EngineConfig()  # Varsayılan ayarlar

# 2. Engine başlat
engine = Engine(config)
engine.start()

# 3. Görev oluştur
task = Task.create(
    script_path="examples/simple_task.py",
    params={"value": 42, "test": True},
    task_type=TaskType.IO_BOUND
)

# 4. Görevi gönder
task_id = engine.submit_task(task)

# 5. Sonucu bekle
result = engine.get_result(task_id, timeout=30.0)

# 6. Engine'i kapat
engine.shutdown()
```

---

## Gelişmiş Örnek

### Dosya: `examples/advanced_example.py`

### Ne Yapar?

Bu örnek, gelişmiş özellikleri gösterir:
- Özel config ile engine oluşturma
- Birden fazla CPU-bound görev
- Birden fazla IO-bound görev
- Batch işlemler
- Durum takibi ve istatistikler

### Nasıl Çalıştırılır?

```bash
cd examples
python3 advanced_example.py
```

### Çıktı Örneği

```
======================================================================
GELİŞMİŞ KULLANIM ÖRNEĞİ
======================================================================

📊 Özel Config:
   CPU-bound workers: 2 (her biri 1 thread)
   IO-bound workers: 4 (her biri 10 thread)
   Queue sizes: 5000/10000

📝 Test script'leri oluşturuluyor...
✅ Script'ler oluşturuldu

🔧 Engine başlatılıyor...
✅ Engine başlatıldı

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

📊 Final Durum:
   input_queue: 8 görev işlendi
   output_queue: 0 görev işlendi

🧹 Temizlik yapılıyor...
🛑 Engine kapatılıyor...
✅ Engine kapatıldı
```

### Çıktı Yorumlama

#### 1. Özel Config
```
📊 Özel Config:
   CPU-bound workers: 2 (her biri 1 thread)
   IO-bound workers: 4 (her biri 10 thread)
   Queue sizes: 5000/10000
```
- **CPU-bound workers**: 2 worker, her biri 1 thread (toplam 2 paralel CPU görevi)
- **IO-bound workers**: 4 worker, her biri 10 thread (toplam 40 paralel IO görevi)
- **Queue sizes**: Input 5000, Output 10000

#### 2. Sistem Durumu
```
📊 Sistem Durumu:
   Engine: 🟢 Çalışıyor
   input_queue: healthy
   output_queue: healthy
   process_pool: healthy
```
- **Engine**: Çalışıyor durumda
- **input_queue**: Sağlıklı (görevler alınıyor)
- **output_queue**: Sağlıklı (sonuçlar yazılıyor)
- **process_pool**: Sağlıklı (worker'lar aktif)

#### 3. CPU-Bound Görevler
```
✓ Görev 1 gönderildi: 44bfa228... (n=1000)
✓ Görev 2 gönderildi: a0a25259... (n=2000)
✓ Görev 3 gönderildi: 3900caf5... (n=3000)
```
- Her görev farklı `n` değeri ile gönderildi
- Görevler CPU-bound worker'lara dağıtılacak

#### 4. IO-Bound Görevler
```
✓ Görev 1 gönderildi: 97e81457... (delay=0.1s)
✓ Görev 2 gönderildi: 324f586c... (delay=0.2s)
...
```
- Her görev farklı `delay` değeri ile gönderildi
- Görevler IO-bound worker'lara dağıtılacak

#### 5. Sonuçlar

**CPU-bound sonuçları:**
```
✅ 44bfa228...: 332833500
✅ a0a25259...: 2664667000
✅ 3900caf5...: 8995500500
```
- Her görev başarıyla tamamlandı
- Sonuçlar: `sum(i * i for i in range(n))` hesaplaması
- Görevler paralel çalıştı (neredeyse aynı anda tamamlandı)

**IO-bound sonuçları:**
```
✅ 97e81457...: completed
✅ 324f586c...: completed
...
```
- Tüm görevler başarıyla tamamlandı
- Her görev belirtilen `delay` süresince bekledi
- Görevler paralel çalıştı

#### 6. İstatistikler
```
📈 Özet:
   Toplam görev: 8
   Başarılı: 8
   Başarısız: 0
```
- **Toplam görev**: Gönderilen görev sayısı
- **Başarılı**: Başarıyla tamamlanan görev sayısı
- **Başarısız**: Hata alan görev sayısı

```
📊 Final Durum:
   input_queue: 8 görev işlendi
   output_queue: 0 görev işlendi
```
- **input_queue**: Queue'ya eklenen görev sayısı
- **output_queue**: Queue'dan alınan sonuç sayısı (cache'den alındığı için 0 görünebilir)

### Kod Akışı

```python
# 1. Özel config
config = EngineConfig(
    cpu_bound_count=2,
    io_bound_count=4,
    cpu_bound_task_limit=1,
    io_bound_task_limit=10
)

# 2. Engine başlat
engine = Engine(config)
engine.start()

# 3. Birden fazla görev gönder
cpu_tasks = []
for i in range(3):
    task = Task.create(
        script_path="cpu_task.py",
        params={"n": 1000 * (i + 1)},
        task_type=TaskType.CPU_BOUND
    )
    cpu_tasks.append(task)
    engine.submit_task(task)

# 4. Sonuçları topla
for task in cpu_tasks:
    result = engine.get_result(task.id, timeout=30)
    if result and result.is_success:
        print(f"Sonuç: {result.data}")

# 5. Engine'i kapat
engine.shutdown()
```

---

## Çıktı Yorumlama

### Başarılı Görev

```
✅ Görev başarılı!
   Sonuç: {'result': 84, ...}
```

**Yorumlama:**
- ✅ işareti: Görev başarıyla tamamlandı
- `result.data`: Script'in döndürdüğü veri
- `task_id`: Görevin benzersiz ID'si
- `worker_id`: Görevi işleyen worker

### Başarısız Görev

```
❌ Görev başarısız
   Hata: Script'te 'main' fonksiyonu bulunamadı
```

**Yorumlama:**
- ❌ işareti: Görev başarısız oldu
- `result.error`: Hata mesajı
- `result.error_details`: Detaylı hata bilgisi (varsa)

### Timeout

```
❌ Timeout - sonuç alınamadı
```

**Yorumlama:**
- Görev belirtilen timeout süresi içinde tamamlanamadı
- Olası nedenler:
  - Görev çok uzun sürüyor
  - Worker'lar meşgul
  - Sistem yavaş

### Sistem Durumu

```
📊 Sistem Durumu:
   Engine: 🟢 Çalışıyor
   input_queue: healthy
   output_queue: healthy
```

**Yorumlama:**
- 🟢: Sistem sağlıklı çalışıyor
- 🔴: Sistem durmuş veya hata var
- **healthy**: Component sağlıklı
- **unhealthy**: Component'te sorun var

---

## Yaygın Senaryolar

### Senaryo 1: Tek Görev

```python
task = Task.create(
    script_path="my_script.py",
    params={"value": 42},
    task_type=TaskType.IO_BOUND
)
task_id = engine.submit_task(task)
result = engine.get_result(task_id, timeout=30)
```

**Beklenen çıktı:**
- Görev gönderildi mesajı
- Sonuç bekleme mesajı
- Başarılı/başarısız sonuç

### Senaryo 2: Batch İşlemler

```python
task_ids = []
for i in range(10):
    task = Task.create(...)
    task_id = engine.submit_task(task)
    task_ids.append(task_id)

# Sonuçları topla
for task_id in task_ids:
    result = engine.get_result(task_id, timeout=30)
```

**Beklenen çıktı:**
- Tüm görevler hızlıca gönderilir (batch)
- Sonuçlar paralel olarak gelir
- Toplam süre: Tek tek göndermekten çok daha hızlı

### Senaryo 3: Karışık Görev Tipleri

```python
# CPU-bound görev
cpu_task = Task.create(..., task_type=TaskType.CPU_BOUND)

# IO-bound görev
io_task = Task.create(..., task_type=TaskType.IO_BOUND)
```

**Beklenen çıktı:**
- CPU-bound görevler CPU worker'larına gider
- IO-bound görevler IO worker'larına gider
- Her görev tipi kendi worker pool'unda işlenir

---

## Sorun Giderme

### Görev Timeout Alıyor

**Neden:**
- Görev çok uzun sürüyor
- Worker'lar meşgul
- Timeout süresi çok kısa

**Çözüm:**
```python
# Timeout süresini artır
result = engine.get_result(task_id, timeout=60.0)

# Veya worker sayısını artır
config = EngineConfig(
    io_bound_count=10,  # Daha fazla worker
    io_bound_task_limit=20  # Worker başına daha fazla thread
)
```

### Görev Başarısız Oluyor

**Neden:**
- Script'te hata var
- `main` fonksiyonu bulunamadı
- Parametreler yanlış

**Çözüm:**
```python
if result and not result.is_success:
    print(f"Hata: {result.error}")
    print(f"Detaylar: {result.error_details}")
```

### Queue Dolu

**Neden:**
- Çok fazla görev gönderildi
- Queue boyutu yetersiz

**Çözüm:**
```python
config = EngineConfig(
    input_queue_size=10000,  # Queue boyutunu artır
    output_queue_size=20000
)
```

---

## Özet

- **Basit örnek**: Tek görev gönderme ve sonuç alma
- **Gelişmiş örnek**: Batch işlemler, durum takibi, istatistikler
- **Çıktılar**: Başarılı/başarısız durumlar, hata mesajları, sistem durumu
- **Yorumlama**: Her çıktı satırı ne anlama geliyor
- **Sorun giderme**: Yaygın sorunlar ve çözümleri

Daha fazla bilgi için `examples/README.md` dosyasına bakın.


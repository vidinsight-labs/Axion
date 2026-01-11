# Axion - Demo Kılavuzu

**Axion v3.0** - Demo Senaryoları ve Performans Testleri

Bu dokümantasyon, Axion demo script'lerinin nasıl çalıştırılacağını ve sonuçlarının nasıl yorumlanacağını açıklar.

## 📑 İçindekiler

1. [Demo Senaryoları](#demo-senaryoları)
2. [Çalıştırma](#çalıştırma)
3. [Çıktı Yorumlama](#çıktı-yorumlama)
4. [Performans Metrikleri](#performans-metrikleri)
5. [Auto-Scaling Gözlemi](#auto-scaling-gözlemi)

---

## 🎬 Demo Senaryoları

### Demo Dosyaları

```
demo/
├── run_demo.py           # Ana demo script
├── data_processor.py     # CPU-bound: Veri işleme
├── api_client.py         # IO-bound: API çağrıları
└── image_processor.py    # CPU-bound: Görüntü işleme
```

### Senaryo 1: Veri İşleme (CPU-Bound)

**Script:** `demo/data_processor.py`

**Görevler:**
- Toplama: 1'den 100'e kadar sayıların toplamı
- Çarpma: 1'den 10'a kadar sayıların çarpımı (10!)
- Filtreleme: 1'den 20'ye kadar çift sayıları bul

**Beklenen Davranış:**
- ✅ CPU-bound worker'lara gönderilir
- ✅ Paralel çalışır (3 görev → 3 worker thread)
- ✅ Hızlı tamamlanır (~0.1-0.2s)

### Senaryo 2: API Çağrıları (IO-Bound)

**Script:** `demo/api_client.py`

**Görevler:**
- GET Request: Veri çekme (simüle edilmiş)
- POST Request: Veri oluşturma (simüle edilmiş)

**Beklenen Davranış:**
- ✅ IO-bound worker'lara gönderilir
- ✅ Network latency simüle edilir (0.5s delay)
- ✅ Paralel çalışır (2 görev → 2 worker thread)

### Senaryo 3: Görüntü İşleme (CPU-Bound)

**Script:** `demo/image_processor.py`

**Görevler:**
- 3 görüntü işleme görevi
- Her biri 1920x1080 boyutunda simüle edilmiş işlem

**Beklenen Davranış:**
- ✅ CPU-bound worker'lara gönderilir
- ✅ Paralel çalışır (3 görev → 3 worker thread)
- ✅ CPU-intensive işlem simülasyonu

### Senaryo 4: Batch İşlemler (Karışık)

**Görevler:**
- 5 görev (3 IO-bound, 2 CPU-bound)
- Karışık görev tipleri

**Beklenen Davranış:**
- ✅ Her görev tipine göre uygun pool'a gönderilir
- ✅ Auto-scaling tetiklenebilir
- ✅ Load balancing çalışır

---

## 🚀 Çalıştırma

### Temel Kullanım

```bash
cd demo
python run_demo.py
```

### Özel Config ile

```python
# run_demo.py içinde
config = EngineConfig(
    cpu_bound_count=4,
    io_bound_count=8,
    log_level="INFO"
)
```

### Debug Modu

```python
config = EngineConfig(log_level="DEBUG")
```

Daha detaylı log mesajları için.

---

## 📊 Çıktı Yorumlama

### Örnek Çıktı

```
======================================================================
🎬 AXION DEMO - Gerçek Hayat Senaryoları
======================================================================

📊 Config:
   CPU-bound workers: 2
   IO-bound workers: 8
   Queue sizes: 1000/10000

======================================================================
📊 SENARYO 1: Veri İşleme (CPU-bound)
======================================================================
   ✓ Toplama görevi gönderildi: f0444cf8...
   ✓ Çarpma görevi gönderildi: 349b757a...
   ✓ Filtreleme görevi gönderildi: a55d437e...

   ⏳ Sonuçlar bekleniyor...
   ✅ Toplama: 5050
   ✅ Çarpma: 3628800
   ✅ Filtreleme: [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]

======================================================================
🌐 SENARYO 2: API Çağrıları (IO-bound)
======================================================================
   ✓ API GET görevi gönderildi: 918c099e...
   ✓ API POST görevi gönderildi: c3cab1cb...

   ⏳ Sonuçlar bekleniyor...
   ✅ API GET: success (3 items)
   ✅ API POST: created

======================================================================
🖼️  SENARYO 3: Görüntü İşleme (CPU-bound)
======================================================================
   ✓ Görüntü 1 görevi gönderildi: 69997c91...
   ✓ Görüntü 2 görevi gönderildi: f0c1322e...
   ✓ Görüntü 3 görevi gönderildi: d3ec8341...

   ⏳ Sonuçlar bekleniyor...
   ✅ Görüntü 1: 1920x1080
   ✅ Görüntü 2: 1920x1080
   ✅ Görüntü 3: 1920x1080

======================================================================
📦 SENARYO 4: Batch İşlemler (Karışık)
======================================================================
   ✓ 5 görev batch olarak gönderildi

   ⏳ Sonuçlar bekleniyor...
   ✅ 5/5 görev başarıyla tamamlandı

======================================================================
📊 FİNAL DURUM
======================================================================

📈 İstatistikler:
   Toplam görev: 13
   Başarılı: 13
   Başarısız: 0
   Toplam süre: 0.65 saniye

📊 Sistem Durumu:
   Engine: 🟢 Çalışıyor
   input_queue: healthy (size: 0)
   output_queue: healthy (size: 0)
   process_pool: healthy
      CPU workers: 2
      IO workers: 8
      Total active threads: 5

🛑 Engine kapatılıyor...
✅ Engine kapatıldı
```

### Çıktı Bölümleri

#### 1. Config Bilgisi

```
📊 Config:
   CPU-bound workers: 2
   IO-bound workers: 8
   Queue sizes: 1000/10000
```

**Yorumlama:**
- Demo için özel config kullanılıyor
- CPU: 2 worker, IO: 8 worker
- Queue boyutları: Input 1000, Output 10000

#### 2. Senaryo Sonuçları

Her senaryo için:
- ✅ Görev gönderildi mesajları
- ⏳ Sonuç bekleniyor mesajı
- ✅ Sonuçlar (başarılı görevler)

**Yorumlama:**
- Tüm görevler başarılı
- Paralel işleme çalışıyor
- Sonuçlar doğru

#### 3. Final Durum

```
📈 İstatistikler:
   Toplam görev: 13
   Başarılı: 13
   Başarısız: 0
   Toplam süre: 0.65 saniye
```

**Yorumlama:**
- ✅ **%100 başarı oranı**: Tüm görevler başarılı
- ✅ **Hızlı işleme**: 0.65 saniyede 13 görev
- ✅ **Sistem sağlıklı**: Tüm component'ler healthy

---

## 📈 Performans Metrikleri

### Throughput

```
📊 Throughput: 20 görev/saniye
```

**Yorumlama:**
- Demo'da 13 görev 0.65 saniyede tamamlandı
- Throughput = 13 / 0.65 = 20 görev/saniye
- ✅ **İyi**: Demo senaryoları için yeterli

### Latency

```
📊 Ortalama Latency: 50ms
📊 Min Latency: 20ms
📊 Max Latency: 150ms
```

**Yorumlama:**
- ✅ **Düşük latency**: Görevler hızlı tamamlanıyor
- ✅ **Tutarlı**: Min ve max arasındaki fark küçük

### Hızlanma (Speedup)

```
Eğer sırayla çalışsaydı: ~10 saniye
Gerçek süre: 0.65 saniye
Hızlanma: ~15.4x
```

**Yorumlama:**
- ✅ **Büyük hızlanma**: Paralel işleme etkili
- ✅ **Verimli**: Worker'lar iyi kullanılıyor

---

## ⚡ Auto-Scaling Gözlemi

### Demo'da Auto-Scaling

Demo'da genellikle auto-scaling tetiklenmez çünkü:
- Görev sayısı az (13 görev)
- Görevler hızlı tamamlanıyor
- Queue dolmuyor

### Auto-Scaling'i Gözlemlemek İçin

**Yüksek Yük Demo:**

```python
# run_demo.py'yi modifiye et
with Engine() as engine:
    # 10,000 görev gönder
    task_ids = []
    for i in range(10000):
        task = Task.create(...)
        task_ids.append(engine.submit_task(task))
    
    # Auto-scaling loglarını izle
    # Terminal'de şunları göreceksiniz:
    # [CPU] Scale OUT +2 → 4 workers | QUEUE PRESSURE: ...
    # [IO] Scale OUT +1 → 9 workers | HIGH: ...
```

**Beklenen Loglar:**

```
WARNING:engine:[CPU] Scale OUT +2 → 4 workers | QUEUE PRESSURE: 2500 tasks/worker (queue=10000)
WARNING:engine:[CPU] Scale OUT +2 → 6 workers | QUEUE PRESSURE: 1666 tasks/worker
INFO:engine:[CPU] Scale OUT +1 → 7 workers | HIGH LOAD: p75=6.2, cpu=0.78
...
INFO:engine:[CPU] Scale IN -1 → 6 workers | SCALE IN: avg=0.8, queue=2/worker
```

---

## 🔍 Senaryo Detayları

### Senaryo 1: Veri İşleme

**Script İçeriği:**

```python
# data_processor.py
def main(params, context):
    operation = params.get("operation")
    
    if operation == "sum":
        result = sum(range(1, 101))  # 5050
    elif operation == "product":
        result = 1
        for i in range(1, 11):
            result *= i  # 3628800
    elif operation == "filter":
        result = [x for x in range(1, 21) if x % 2 == 0]
    
    return {"result": result, "operation": operation}
```

**Beklenen Sonuçlar:**
- Toplama: `5050`
- Çarpma: `3628800`
- Filtreleme: `[2, 4, 6, 8, 10, 12, 14, 16, 18, 20]`

### Senaryo 2: API Çağrıları

**Script İçeriği:**

```python
# api_client.py
def main(params, context):
    method = params.get("method")
    endpoint = params.get("endpoint")
    
    # Simüle edilmiş network delay
    import time
    time.sleep(0.5)
    
    if method == "GET":
        return {"status": "success", "items": 3}
    elif method == "POST":
        return {"status": "created", "id": "new-item-123"}
```

**Beklenen Sonuçlar:**
- GET: `{"status": "success", "items": 3}`
- POST: `{"status": "created", "id": "new-item-123"}`

### Senaryo 3: Görüntü İşleme

**Script İçeriği:**

```python
# image_processor.py
def main(params, context):
    image_id = params.get("image_id")
    
    # Simüle edilmiş görüntü işleme
    width = 1920
    height = 1080
    
    # CPU-intensive işlem simülasyonu
    pixels = width * height
    processed = sum(range(pixels)) % 1000000  # Simüle edilmiş işlem
    
    return {
        "image_id": image_id,
        "size": f"{width}x{height}",
        "processed": processed
    }
```

**Beklenen Sonuçlar:**
- Her görüntü: `{"image_id": "...", "size": "1920x1080", "processed": ...}`

---

## 🎯 Performans Beklentileri

### Normal Demo (13 Görev)

| Metrik | Beklenen Değer |
|--------|----------------|
| **Toplam Süre** | 0.5-1.0 saniye |
| **Throughput** | 15-25 görev/saniye |
| **Ortalama Latency** | 30-80ms |
| **Başarı Oranı** | %100 |

### Yüksek Yük Demo (10,000 Görev)

| Metrik | Beklenen Değer |
|--------|----------------|
| **Toplam Süre** | 25-35 saniye |
| **Throughput** | 300-400 görev/saniye |
| **Ortalama Latency** | 50-150ms |
| **Auto-Scaling Events** | 10-20 |
| **Max Workers** | CPU: 10-16, IO: 15-24 |

---

## 🛠️ Sorun Giderme

### Bazı Görevler Timeout Alıyor

**Sorun:** Demo'da bazı görevler timeout alıyor

**Çözüm:**
```python
# run_demo.py içinde timeout süresini artır
result = engine.get_result(task_id, timeout=60.0)  # 30 → 60
```

### Görevler Sırayla Tamamlanıyor

**Sorun:** Görevler paralel değil, sırayla çalışıyor

**Neden:**
- Worker sayısı yetersiz
- Thread limiti yetersiz

**Çözüm:**
```python
config = EngineConfig(
    cpu_bound_count=4,      # Daha fazla CPU worker
    io_bound_count=12,      # Daha fazla IO worker
    io_bound_task_limit=30  # Daha fazla thread
)
```

### Auto-Scaling Çalışmıyor

**Sorun:** Yüksek yükte auto-scaling tetiklenmiyor

**Kontrol:**
```python
# Log seviyesini INFO veya WARNING yap
config = EngineConfig(log_level="INFO")

# Resource Manager loop çalışıyor mu kontrol et
# Her 2 saniyede bir log mesajı görmelisiniz
```

---

## 📚 Özet

### Demo Senaryoları

1. ✅ **Veri İşleme**: CPU-bound hesaplamalar
2. ✅ **API Çağrıları**: IO-bound network işlemleri
3. ✅ **Görüntü İşleme**: CPU-bound görüntü işleme
4. ✅ **Batch İşlemler**: Karışık görev tipleri

### Beklenen Sonuçlar

- ✅ Tüm görevler başarılı
- ✅ Paralel işleme çalışıyor
- ✅ Hızlı tamamlanma (< 1 saniye)
- ✅ Sistem sağlıklı

### Performans

- ✅ **Throughput**: 15-25 görev/saniye (demo)
- ✅ **Latency**: 30-80ms (düşük yük)
- ✅ **Hızlanma**: 10-20x (paralel vs sıralı)

---

## 🔗 İlgili Dokümantasyon

- [Examples Guide](./examples_guide.md) - Kullanım örnekleri
- [Output Interpretation](./output_interpretation.md) - Çıktı yorumlama
- [Architecture](./architecture.md) - Mimari detayları

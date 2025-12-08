# Demo Kılavuzu - Gerçek Hayat Senaryoları

Bu dokümantasyon, `demo/run_demo.py` script'inin nasıl çalıştığını ve çıktılarının nasıl yorumlanacağını açıklar.

## Demo Nedir?

Demo script'i, CPU Load Balancer'ın gerçek hayat senaryolarını simüle eder:
- Veri işleme (CPU-bound)
- API çağrıları (IO-bound)
- Görüntü işleme (CPU-bound)
- Batch işlemler (karışık)

## Nasıl Çalıştırılır?

```bash
cd demo
python3 run_demo.py
```

## Çıktı Yapısı

Demo çıktısı 4 ana senaryodan oluşur:

### Senaryo 1: Veri İşleme (CPU-bound)

```
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
```

**Yorumlama:**
- **Toplama**: 1'den 100'e kadar sayıların toplamı (5050)
- **Çarpma**: 1'den 10'a kadar sayıların çarpımı (10! = 3628800)
- **Filtreleme**: 1'den 20'ye kadar çift sayılar

**Ne Gösterir:**
- CPU-bound görevler CPU worker'larında çalışır
- Hesaplama işlemleri paralel yapılır
- Her görev farklı bir işlem tipini simüle eder

### Senaryo 2: API Çağrıları (IO-bound)

```
======================================================================
🌐 SENARYO 2: API Çağrıları (IO-bound)
======================================================================
   ✓ API GET görevi gönderildi: 918c099e...
   ✓ API POST görevi gönderildi: c3cab1cb...

   ⏳ Sonuçlar bekleniyor...
   ✅ API GET: success (3 items)
   ✅ API POST: created
```

**Yorumlama:**
- **API GET**: Veri çekme işlemi (3 öğe döndü)
- **API POST**: Veri oluşturma işlemi (created)

**Ne Gösterir:**
- IO-bound görevler IO worker'larında çalışır
- Network işlemleri simüle edilir
- Farklı HTTP metodları test edilir

### Senaryo 3: Görüntü İşleme (CPU-bound)

```
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
```

**Yorumlama:**
- Her görüntü 1920x1080 boyutunda işlendi
- Tüm görüntüler paralel işlendi

**Ne Gösterir:**
- CPU-bound görevlerin batch işlenmesi
- Görüntü işleme senaryosu
- Paralel işleme performansı

### Senaryo 4: Batch İşlemler (Karışık)

```
======================================================================
📦 SENARYO 4: Batch İşlemler (Karışık)
======================================================================
   ✓ 5 görev batch olarak gönderildi

   ⏳ Sonuçlar bekleniyor...
   ✅ 5/5 görev başarıyla tamamlandı
```

**Yorumlama:**
- 5 görev aynı anda gönderildi (batch)
- Tüm görevler başarıyla tamamlandı
- CPU ve IO görevleri karışık olarak işlendi

**Ne Gösterir:**
- Batch gönderim performansı
- Karışık görev tiplerinin işlenmesi
- Load balancing çalışması

## Final Durum

```
======================================================================
📊 FİNAL DURUM
======================================================================

📈 İstatistikler:
   Input Queue: 13 görev gönderildi
   Output Queue: 0 sonuç alındı
   Process Pool: 8 worker aktif
```

**Yorumlama:**
- **Input Queue**: Toplam gönderilen görev sayısı
- **Output Queue**: Queue'dan alınan sonuç sayısı (cache kullanıldığı için 0 olabilir)
- **Process Pool**: Aktif worker sayısı (2 CPU + 6 IO = 8)

## Performans Metrikleri

### Gönderim Hızı

```
Tüm görevler 0.001 saniyede gönderildi
```

→ Batch gönderim çok hızlı (tüm görevler aynı anda queue'ya eklendi)

### İşleme Hızı

```
Tüm görevler ~0.6 saniyede tamamlandı
```

→ Paralel işleme sayesinde çok hızlı

### Hızlanma

```
Eğer sırayla çalışsaydı: ~10 saniye
Gerçek süre: 0.6 saniye
Hızlanma: ~17x
```

→ Paralel işleme büyük bir hız artışı sağlıyor

## Senaryo Detayları

### Senaryo 1: Veri İşleme

**Script:** `demo/data_processor.py`

**Görevler:**
1. **Toplama**: `sum([1, 2, ..., 100])` = 5050
2. **Çarpma**: `1 * 2 * ... * 10` = 3628800
3. **Filtreleme**: `[x for x in range(1,21) if x % 2 == 0]`

**Beklenen süre:** ~0.1-0.2 saniye (paralel)

### Senaryo 2: API Çağrıları

**Script:** `demo/api_client.py`

**Görevler:**
1. **GET**: Veri çekme (3 öğe döndürür)
2. **POST**: Veri oluşturma (created döndürür)

**Beklenen süre:** ~0.5 saniye (her biri 0.5s network latency)

### Senaryo 3: Görüntü İşleme

**Script:** `demo/image_processor.py`

**Görevler:**
- 3 görüntü işleme görevi
- Her biri 1920x1080 boyutunda

**Beklenen süre:** ~0.6 saniye (paralel)

### Senaryo 4: Batch İşlemler

**Görevler:**
- 5 görev (3 IO-bound, 2 CPU-bound)
- Karışık görev tipleri

**Beklenen süre:** ~0.6 saniye (tüm görevler paralel)

## Sorun Giderme

### Bazı Görevler Timeout Alıyor

**Neden:**
- Çok fazla görev aynı anda
- Worker'lar meşgul
- Timeout süresi yetersiz

**Çözüm:**
```python
# Demo'da timeout 30 saniye
# Eğer yeterli değilse, worker sayısını artırın
config = EngineConfig(
    io_bound_count=10,  # Daha fazla worker
    cpu_bound_count=4
)
```

### Görevler Sırayla Tamamlanıyor

**Neden:**
- Worker sayısı yetersiz
- Thread sayısı yetersiz

**Çözüm:**
```python
config = EngineConfig(
    io_bound_count=10,
    io_bound_task_limit=20  # Worker başına daha fazla thread
)
```

## Özet

Demo script'i şunları gösterir:

1. ✅ **CPU-bound görevler**: Hesaplama işlemleri
2. ✅ **IO-bound görevler**: Network/IO işlemleri
3. ✅ **Batch işlemler**: Çoklu görev gönderimi
4. ✅ **Paralel işleme**: Görevlerin aynı anda çalışması
5. ✅ **Load balancing**: Görevlerin worker'lara dağıtılması
6. ✅ **Performans**: Hızlanma ve verimlilik

Tüm senaryolar başarıyla çalışmalı ve görevler paralel olarak tamamlanmalıdır.


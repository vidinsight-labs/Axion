# CPU Load Balancer - Benchmark Kılavuzu

Bu dokümantasyon, CPU Load Balancer için yapılması gereken benchmark'ları açıklar.

## İlgili Dokümantasyon

- **[Benchmark Sonuçlarını Yorumlama](./benchmark_results_interpretation.md)** - Benchmark sonuçlarını nasıl yorumlayacağınızı öğrenin

## Benchmark Kategorileri

### 1. Performans Benchmark'ları

#### 1.1 Throughput (İşlem Hızı)
- **Ne ölçülür**: Saniyede işlenen görev sayısı
- **Neden önemli**: Sistemin ne kadar hızlı çalıştığını gösterir
- **Metrikler**:
  - Görevler/saniye
  - Toplam işlenen görev sayısı
  - Ortalama işlem süresi

#### 1.2 Latency (Gecikme)
- **Ne ölçülür**: Görev gönderilmesinden sonuç alınana kadar geçen süre
- **Neden önemli**: Kullanıcı deneyimini etkiler
- **Metrikler**:
  - Ortalama latency
  - Min/Max latency
  - P50, P95, P99 latency (percentile)

#### 1.3 Queue Processing Time
- **Ne ölçülür**: Görevin queue'da bekleme süresi
- **Neden önemli**: Queue bottleneck'lerini gösterir
- **Metrikler**:
  - Queue'da bekleme süresi
  - Queue boyutu değişimi

### 2. Ölçeklenebilirlik Benchmark'ları

#### 2.1 Worker Sayısı Ölçeklenebilirliği
- **Ne ölçülür**: Farklı worker sayıları ile performans
- **Neden önemli**: Sistemin ölçeklenebilirliğini gösterir
- **Test Senaryoları**:
  - 1 CPU, 1 IO worker
  - 1 CPU, 4 IO worker
  - 1 CPU, 8 IO worker
  - 2 CPU, 8 IO worker

#### 2.2 Queue Boyutu Ölçeklenebilirliği
- **Ne ölçülür**: Farklı queue boyutları ile performans
- **Neden önemli**: Queue bottleneck'lerini gösterir
- **Test Senaryoları**:
  - Küçük queue (100)
  - Orta queue (1000)
  - Büyük queue (10000)

#### 2.3 Batch İşlem Performansı
- **Ne ölçülür**: Aynı anda gönderilen görevlerin işlenme hızı
- **Neden önemli**: Gerçek kullanım senaryolarını yansıtır
- **Test Senaryoları**:
  - 10 görev batch
  - 100 görev batch
  - 1000 görev batch

### 3. Kaynak Kullanımı Benchmark'ları

#### 3.1 CPU Kullanımı
- **Ne ölçülür**: CPU kullanım yüzdesi
- **Neden önemli**: Sistem verimliliğini gösterir
- **Metrikler**:
  - Ortalama CPU kullanımı
  - Peak CPU kullanımı
  - CPU-bound vs IO-bound kullanımı

#### 3.2 Memory Kullanımı
- **Ne ölçülür**: RAM kullanımı
- **Neden önemli**: Memory leak'leri ve verimliliği gösterir
- **Metrikler**:
  - Başlangıç memory
  - Peak memory
  - Memory artış hızı

#### 3.3 Process/Thread Sayıları
- **Ne ölçülür**: Aktif process ve thread sayıları
- **Neden önemli**: Sistem kaynak kullanımını gösterir
- **Metrikler**:
  - Toplam process sayısı
  - Toplam thread sayısı
  - Aktif thread sayısı

### 4. Load Balancing Benchmark'ları

#### 4.1 Görev Dağılımı
- **Ne ölçülür**: Görevlerin worker'lara dağılımı
- **Neden önemli**: Load balancing'in adil olup olmadığını gösterir
- **Metrikler**:
  - Worker başına görev sayısı
  - Dağılım standart sapması
  - En yüklü/en az yüklü worker farkı

#### 4.2 Worker Yükü Dengesi
- **Ne ölçülür**: Worker'ların yük dağılımı
- **Neden önemli**: Sistem verimliliğini gösterir
- **Metrikler**:
  - Worker başına aktif thread sayısı
  - Yük dengesi katsayısı

### 5. Hata Toleransı Benchmark'ları

#### 5.1 Hata Durumları
- **Ne ölçülür**: Hata durumlarında sistem davranışı
- **Neden önemli**: Sistemin güvenilirliğini gösterir
- **Test Senaryoları**:
  - Geçersiz script path
  - Script içinde hata
  - Worker crash durumu

#### 5.2 Retry Mekanizması
- **Ne ölçülür**: Retry mekanizmasının çalışması
- **Neden önemli**: Geçici hataların yönetimini gösterir
- **Metrikler**:
  - Retry sayısı
  - Başarılı retry oranı

## Benchmark Senaryoları

### Senaryo 1: Basit Throughput Testi
- **Amaç**: Sistemin temel işlem hızını ölçmek
- **Test**: 1000 basit görev gönder, süre ölç
- **Metrikler**: Görevler/saniye, ortalama latency

### Senaryo 2: Ölçeklenebilirlik Testi
- **Amaç**: Worker sayısı artışının etkisini ölçmek
- **Test**: 1, 2, 4, 8 worker ile aynı test
- **Metrikler**: Throughput, latency, CPU kullanımı

### Senaryo 3: Batch İşlem Testi
- **Amaç**: Batch işlemlerin performansını ölçmek
- **Test**: 100, 500, 1000 görev batch
- **Metrikler**: Toplam süre, görev başına süre, queue bekleme süresi

### Senaryo 4: Karışık Yük Testi
- **Amaç**: Gerçek kullanım senaryosunu simüle etmek
- **Test**: CPU-bound ve IO-bound görevler karışık
- **Metrikler**: Her tip için throughput, latency, kaynak kullanımı

### Senaryo 5: Uzun Süreli Test
- **Amaç**: Sistemin uzun süreli kullanımda stabilitesini ölçmek
- **Test**: 1 saat boyunca sürekli görev gönder
- **Metrikler**: Memory leak, CPU kullanımı, hata oranı

## Benchmark Metrikleri

### Temel Metrikler
- **Throughput**: Görevler/saniye
- **Latency**: Ortalama, P50, P95, P99
- **Success Rate**: Başarılı görev yüzdesi
- **Error Rate**: Hata yüzdesi

### Kaynak Metrikleri
- **CPU Usage**: Ortalama, peak
- **Memory Usage**: Başlangıç, peak, artış
- **Process Count**: Toplam process sayısı
- **Thread Count**: Toplam, aktif thread sayısı

### Queue Metrikleri
- **Queue Size**: Ortalama, peak queue boyutu
- **Queue Wait Time**: Queue'da bekleme süresi
- **Queue Drop Rate**: Düşen görev yüzdesi

### Load Balancing Metrikleri
- **Task Distribution**: Worker başına görev sayısı
- **Load Balance**: Yük dengesi katsayısı
- **Worker Utilization**: Worker kullanım yüzdesi

## Benchmark Raporu Formatı

```json
{
  "test_name": "Throughput Test",
  "config": {
    "cpu_bound_count": 1,
    "io_bound_count": 4,
    "input_queue_size": 1000
  },
  "results": {
    "throughput": 150.5,
    "latency": {
      "avg": 0.025,
      "p50": 0.020,
      "p95": 0.050,
      "p99": 0.100
    },
    "success_rate": 0.99,
    "resource_usage": {
      "cpu_avg": 45.2,
      "memory_peak": 128.5
    }
  }
}
```

## Benchmark Çalıştırma

```bash
# Basit throughput testi
python benchmarks/throughput_test.py

# Ölçeklenebilirlik testi
python benchmarks/scalability_test.py

# Batch işlem testi
python benchmarks/batch_test.py

# Tüm testler
python benchmarks/run_all_benchmarks.py
```


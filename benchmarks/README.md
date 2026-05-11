# Axion - Benchmark Testleri

Bu klasör, Axion için benchmark testlerini içerir.

## Benchmark Testleri

### 1. Throughput Testi (`throughput_test.py`)

Sistemin saniyede kaç görev işleyebildiğini ölçer.

**Çalıştırma:**
```bash
python benchmarks/throughput_test.py
```

**Ölçülen Metrikler:**
- Throughput (görevler/saniye)
- Latency (ortalama, P50, P95, P99)
- Başarı oranı
- Toplam süre

### 2. Ölçeklenebilirlik Testi (`scalability_test.py`)

Farklı worker sayıları ile sistem performansını ölçer.

**Çalıştırma:**
```bash
python benchmarks/scalability_test.py
```

**Ölçülen Metrikler:**
- Farklı worker konfigürasyonları ile throughput
- Worker sayısı artışının etkisi
- Hızlanma oranı

### 3. Batch İşlem Testi (`batch_test.py`)

Batch işlemlerin performansını ölçer.

**Çalıştırma:**
```bash
python benchmarks/batch_test.py
```

**Ölçülen Metrikler:**
- Farklı batch boyutları ile performans
- İlk sonuç süresi
- Son sonuç süresi
- Batch süresi

## Tüm Testleri Çalıştırma

```bash
# Tüm testleri sırayla çalıştır
python benchmarks/throughput_test.py
python benchmarks/scalability_test.py
python benchmarks/batch_test.py
```

## Benchmark Sonuçları

Test sonuçları konsola yazdırılır. Gelecekte JSON formatında dosyaya kaydedilebilir.

## Benchmark Sonuçlarını Yorumlama

Benchmark sonuçlarını nasıl yorumlayacağınızı öğrenmek için:

📖 **[Benchmark Sonuçlarını Yorumlama Kılavuzu](./benchmark_results_interpretation.md)**

Bu kılavuz şunları içerir:
- Throughput sonuçlarını yorumlama
- Latency sonuçlarını yorumlama
- Başarı oranı analizi
- Ölçeklenebilirlik değerlendirmesi
- Batch işlem analizi
- Kırmızı bayraklar (red flags)
- Optimizasyon önerileri

## Yeni Benchmark Ekleme

Yeni benchmark eklemek için:

1. `benchmarks/` klasörüne yeni bir Python dosyası ekleyin
2. Benchmark fonksiyonunu yazın
3. `main()` fonksiyonu ile testi çalıştırılabilir hale getirin
4. README'ye ekleyin

## Notlar

- Benchmark'lar gerçek script'ler kullanır (`examples/simple_task.py`)
- Test süreleri sistem yüküne göre değişebilir
- Sonuçları karşılaştırmak için aynı sistemde çalıştırın
- Sonuçları yorumlamak için [yorumlama kılavuzunu](./benchmark_results_interpretation.md) okuyun


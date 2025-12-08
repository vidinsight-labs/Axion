# CPU Load Balancer - Dokümantasyon

Bu klasör, CPU Load Balancer projesinin tüm dokümantasyonunu içerir.

## İçindekiler

### Hızlı Başlangıç

1. **[Module Overview](./module_overview.md)** - Modül özeti (BAŞLANGIÇ İÇİN)
   - Modül parçaları
   - Girdi nasıl oluyor
   - Çıktı nasıl oluyor
   - Nasıl takip ediliyor

### Mimari ve Akış

2. **[Architecture](./architecture.md)** - Modül mimarisi ve bileşenler
   - Modül yapısı
   - Ana bileşenler
   - Girdi/çıktı akışı
   - Takip mekanizmaları

3. **[Data Flow](./data_flow.md)** - Veri akışı ve dönüşümleri
   - Veri dönüşümleri
   - Process iletişimi
   - Takip mekanizmaları
   - Örnek akışlar

### Kullanım Kılavuzları

3. **[Examples Guide](./examples_guide.md)** - Örneklerin nasıl çalıştığını açıklar
   - Basit örnek kullanımı
   - Gelişmiş örnek kullanımı
   - Kod akışı
   - Yaygın senaryolar

4. **[Output Interpretation](./output_interpretation.md)** - Çıktıların nasıl yorumlanacağını açıklar
   - Durum mesajları
   - Hata mesajları
   - İstatistikler
   - Zamanlama bilgileri

5. **[Demo Guide](./demo_guide.md)** - Demo script'i kılavuzu
   - Senaryolar
   - Performans metrikleri
   - Sorun giderme

### Örnek Çıktılar

- `simple_example_output.txt` - Basit örneğin çıktısı
- `advanced_example_output.txt` - Gelişmiş örneğin çıktısı

## Hızlı Başlangıç

### 1. Basit Örnek

```bash
cd examples
python3 simple_example.py
```

**Beklenen çıktı:**
- Engine başlatıldı
- Görev gönderildi
- Sonuç alındı
- Engine kapatıldı

Detaylı açıklama: [Examples Guide](./examples_guide.md#basit-örnek)

### 2. Gelişmiş Örnek

```bash
cd examples
python3 advanced_example.py
```

**Beklenen çıktı:**
- Özel config ile engine
- Birden fazla görev (CPU/IO-bound)
- Batch işlemler
- İstatistikler

Detaylı açıklama: [Examples Guide](./examples_guide.md#gelişmiş-örnek)

## Çıktı Yorumlama

### Başarılı Görev

```
✅ Görev başarılı!
   Sonuç: {'result': 84, ...}
```

→ Görev başarıyla tamamlandı, sonuç alındı.

### Başarısız Görev

```
❌ Görev başarısız
   Hata: Script'te 'main' fonksiyonu bulunamadı
```

→ Hata mesajını okuyun ve düzeltin.

### Timeout

```
❌ Timeout - sonuç alınamadı
```

→ Timeout süresini artırın veya worker sayısını artırın.

Detaylı açıklama: [Output Interpretation](./output_interpretation.md)

## Sorun Giderme

### Görev Timeout Alıyor

**Çözüm:**
```python
# Timeout süresini artır
result = engine.get_result(task_id, timeout=60.0)

# Worker sayısını artır
config = EngineConfig(io_bound_count=10)
```

### Script Bulunamadı

**Çözüm:**
```python
# Absolute path kullan
script_path = "/absolute/path/to/script.py"

# Veya Path objesi kullan
from pathlib import Path
script_path = str(Path(__file__).parent / "script.py")
```

### Queue Dolu

**Çözüm:**
```python
# Queue boyutunu artır
config = EngineConfig(input_queue_size=10000)
```

## Daha Fazla Bilgi

- **Config**: `cpu_load_balancer/config/README.md`
- **Examples**: `examples/README.md`
- **API**: Kod içi docstring'ler

## Katkıda Bulunma

Dokümantasyonu geliştirmek için:
1. Eksik bilgileri ekleyin
2. Örnek çıktıları güncelleyin
3. Yeni senaryolar ekleyin


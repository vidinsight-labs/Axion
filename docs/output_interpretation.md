# Axion - Çıktı Yorumlama Kılavuzu

**Axion v3.0** - Log Mesajları, Metrikler ve Hata Yorumlama

Bu dokümantasyon, Axion'un ürettiği çıktıların, log mesajlarının ve metriklerin nasıl yorumlanacağını açıklar.

## 📑 İçindekiler

1. [Log Mesajları](#log-mesajları)
2. [Auto-Scaling Logları](#auto-scaling-logları)
3. [Hata Mesajları](#hata-mesajları)
4. [Sistem Metrikleri](#sistem-metrikleri)
5. [Performans Göstergeleri](#performans-göstergeleri)

---

## 📝 Log Mesajları

### Log Seviyeleri

Axion, Python'un standart logging sistemini kullanır:

- **DEBUG**: Detaylı debug bilgileri
- **INFO**: Genel bilgilendirme mesajları
- **WARNING**: Uyarılar (kritik değil)
- **ERROR**: Hatalar (kritik)
- **CRITICAL**: Kritik hatalar

### Engine Başlatma

```
INFO:engine:Engine başlatıldı
```

**Yorumlama:**
- ✅ Engine başarıyla başlatıldı
- Worker process'leri ve thread'ler hazır
- Queue'lar oluşturuldu

### Görev Gönderme

```
INFO:engine:Görev gönderildi: abc123...
```

**Yorumlama:**
- ✅ Görev başarıyla queue'ya eklendi
- Task ID gösterilir (ilk 8 karakter)
- Görev işlenmeye başlayacak

### Sonuç Alma

```
INFO:engine:Sonuç alındı: abc123...
```

**Yorumlama:**
- ✅ Sonuç başarıyla alındı
- Result cache'den veya queue'dan geldi

---

## ⚡ Auto-Scaling Logları

### Scale-Out (Worker Ekleme)

#### Queue Pressure

```
WARNING:engine:[CPU] Scale OUT +2 → 6 workers | QUEUE PRESSURE: 2500 tasks/worker (queue=10000)
```

**Yorumlama:**
- ⚠️ **WARNING seviyesi**: Kritik değil, bilgilendirme
- **+2 worker**: 2 worker eklendi
- **6 workers**: Toplam worker sayısı
- **QUEUE PRESSURE**: Input queue'da çok fazla görev var
- **2500 tasks/worker**: Her worker'a ortalama 2500 görev düşüyor
- **queue=10000**: Input queue'da 10,000 görev bekliyor

**Ne Yapmalı?**
- ✅ Normal: Auto-scaling çalışıyor
- ✅ Beklenen: Yüksek yük durumunda normal
- ⚠️ Dikkat: Sürekli scale-out oluyorsa max limit'e yaklaşıyor olabilir

#### Emergency Load

```
WARNING:engine:[CPU] Scale OUT +2 → 8 workers | EMERGENCY: max_load=12.5, cpu=0.95
```

**Yorumlama:**
- **EMERGENCY**: Kritik durum
- **max_load=12.5**: En yüklü worker'ın load'u 12.5
- **cpu=0.95**: CPU kullanımı %95
- **+2 worker**: Acil olarak 2 worker eklendi

**Ne Yapmalı?**
- ⚠️ **Dikkat**: Sistem aşırı yüklü
- ✅ Auto-scaling tepki verdi
- 🔍 **Kontrol**: Worker'lar yeterli mi? Config optimize edilmeli mi?

#### High Velocity

```
INFO:engine:[CPU] Scale OUT +1 → 5 workers | HIGH VELOCITY: velocity=5.2/s, load=4.8
```

**Yorumlama:**
- **HIGH VELOCITY**: Yük hızla artıyor (predictive scaling)
- **velocity=5.2/s**: Her saniye 5.2 load artışı
- **load=4.8**: Mevcut ortalama load
- **+1 worker**: Proaktif olarak 1 worker eklendi

**Ne Yapmalı?**
- ✅ **İyi**: Predictive scaling çalışıyor
- ✅ Sistem yükü artmadan önce worker eklendi

#### High Load

```
INFO:engine:[CPU] Scale OUT +1 → 4 workers | HIGH LOAD: p75=6.5, cpu=0.78
```

**Yorumlama:**
- **HIGH LOAD**: Yüksek yük durumu
- **p75=6.5**: %75'lik worker'ın load'u 6.5
- **cpu=0.78**: CPU kullanımı %78
- **+1 worker**: 1 worker eklendi

### Scale-In (Worker Çıkarma)

```
INFO:engine:[CPU] Scale IN -1 → 3 workers | SCALE IN: avg=0.8, cpu=0.15
```

**Yorumlama:**
- **SCALE IN**: Worker sayısı azaltıldı
- **-1 worker**: 1 worker çıkarıldı
- **3 workers**: Kalan worker sayısı
- **avg=0.8**: Ortalama load düşük
- **cpu=0.15**: CPU kullanımı %15 (düşük)

**Ne Yapmalı?**
- ✅ **Normal**: Yük azaldı, gereksiz worker'lar kaldırıldı
- ✅ Kaynak tasarrufu sağlanıyor

### Fast Check Mode

```
WARNING:engine:[CPU] Scale OUT +2 → 10 workers | EMERGENCY: max_load=11.2, cpu=0.92
```

**Ardından:**
- Resource Manager loop **1 saniyede bir** çalışır (normal: 2 saniye)
- Kritik durum bitene kadar hızlı kontrol devam eder

**Yorumlama:**
- ⚡ **Hızlı tepki**: Sistem kritik durumda
- ✅ Auto-scaling daha sık kontrol ediyor

---

## ❌ Hata Mesajları

### Engine Hataları

#### Engine Zaten Başlatılmış

```
ERROR:engine:Engine zaten başlatılmış [ENG001]
```

**Neden:**
- `engine.start()` iki kez çağrıldı

**Çözüm:**
```python
# Yanlış
engine.start()
engine.start()  # ❌ Hata!

# Doğru
engine.start()
# veya
with Engine() as engine:  # ✅ Context manager kullan
```

#### Engine Başlatılmamış

```
ERROR:engine:Engine başlatılmamış [ENG002]
```

**Neden:**
- `engine.start()` çağrılmadan görev gönderildi

**Çözüm:**
```python
engine.start()  # Önce başlat
engine.submit_task(task)  # Sonra görev gönder
```

### Task Hataları

#### Queue Dolu

```
ERROR:engine:Queue dolu, görev eklenemedi [TASK001]
```

**Neden:**
- Input queue maksimum kapasiteye ulaştı
- Çok fazla görev gönderildi

**Çözüm:**
```python
# 1. Queue boyutunu artır
config = EngineConfig(input_queue_size=10000)

# 2. Auto-scaling çalışıyor mu kontrol et
# Auto-scaling otomatik worker ekler, ama queue dolmadan önce

# 3. Görev göndermeyi yavaşlat
for task in tasks:
    engine.submit_task(task)
    time.sleep(0.01)  # Biraz bekle
```

#### Backpressure Active

```
ERROR:engine:Sistem aşırı yüklü (Backpressure Active) [TASK002]
```

**Neden:**
- CPU kullanımı > %100 veya Memory > %100
- BackpressureController görev kabul etmiyor

**Çözüm:**
```python
# 1. Sistem kaynaklarını kontrol et
import psutil
print(f"CPU: {psutil.cpu_percent()}%")
print(f"Memory: {psutil.virtual_memory().percent}%")

# 2. Biraz bekle ve tekrar dene
time.sleep(5)
result = engine.submit_task(task)

# 3. Worker sayısını azalt (paradoks ama bazen gerekli)
config = EngineConfig(cpu_bound_count=2)  # Daha az worker
```

### Script Hataları

#### Main Fonksiyonu Bulunamadı

```
ERROR:executor:Script'te 'main' fonksiyonu bulunamadı: script.py
```

**Neden:**
- Script'te `main(params, context)` fonksiyonu yok

**Çözüm:**
```python
# script.py
def main(params, context):
    # İşlemler
    return {"result": "success"}
```

#### Script Yüklenemedi

```
ERROR:executor:Script yüklenemedi: /path/to/script.py
```

**Neden:**
- Script dosyası yok
- Path yanlış
- Dosya okuma izni yok

**Çözüm:**
```python
# Absolute path kullan
script_path = "/absolute/path/to/script.py"

# Veya Path objesi
from pathlib import Path
script_path = str(Path(__file__).parent / "script.py")
```

### Worker Hataları

#### Worker Process Crash

```
ERROR:worker:Worker process crashed: io-2
```

**Neden:**
- Worker process beklenmedik şekilde sonlandı
- Script'te fatal error
- Memory overflow

**Çözüm:**
- ✅ Auto-scaling otomatik yeni worker ekler
- 🔍 Script'i kontrol et (fatal error var mı?)
- 🔍 Memory kullanımını kontrol et

---

## 📊 Sistem Metrikleri

### Engine Status

```python
status = engine.get_status()

{
    "engine": {
        "is_running": true
    },
    "components": {
        "input_queue": {
            "name": "input_queue",
            "health": "healthy",
            "metrics": {
                "size": 150,
                "maxsize": 1000,
                "fullness": 0.15,
                "total_put": 10000,
                "total_dropped": 5
            }
        },
        "output_queue": {
            "name": "output_queue",
            "health": "healthy",
            "metrics": {
                "size": 2,
                "maxsize": 10000,
                "total_put": 9995,
                "total_get": 9993
            }
        },
        "process_pool": {
            "name": "process_pool",
            "health": "healthy",
            "metrics": {
                "cpu_bound_workers": 6,
                "io_bound_workers": 12,
                "total_workers": 18,
                "cpu_active_threads": 6,
                "io_active_threads": 45,
                "total_active_threads": 51,
                "cpu_worker_tasks": {
                    "cpu-0": {
                        "active_tasks": 1,
                        "queue_size": 5,
                        "thread_pool_queue_size": 0,
                        "total_load": 6,
                        "cpu_usage": 85.3
                    },
                    ...
                },
                "io_worker_tasks": {...}
            }
        }
    }
}
```

### Metrik Yorumlama

#### Input Queue

| Metrik | Açıklama | İdeal Değer |
|--------|----------|-------------|
| `size` | Queue'daki görev sayısı | 0-100 (düşük) |
| `fullness` | Doluluk oranı | < 0.5 (50%) |
| `total_put` | Toplam gönderilen | Artıyor |
| `total_dropped` | Düşen görev | 0 (ideal) |

**Yorumlama:**
- ✅ `size < 100`: Queue boş, sistem rahat
- ⚠️ `size > 500`: Queue dolu, auto-scaling çalışmalı
- ❌ `total_dropped > 0`: Queue taştı, boyut artırılmalı

#### Output Queue

| Metrik | Açıklama | İdeal Değer |
|--------|----------|-------------|
| `size` | Queue'daki sonuç sayısı | 0-10 (düşük) |
| `total_put` | Toplam eklenen | Artıyor |
| `total_get` | Toplam alınan | ≈ total_put |

**Yorumlama:**
- ✅ `size < 10`: Sonuçlar hızlıca alınıyor
- ⚠️ `size > 100`: Sonuçlar birikiyor, `get_result()` çağrıları yavaş

#### Process Pool

| Metrik | Açıklama | İdeal Değer |
|--------|----------|-------------|
| `cpu_bound_workers` | CPU worker sayısı | 1-16 |
| `io_bound_workers` | IO worker sayısı | 4-24 |
| `total_active_threads` | Aktif thread sayısı | Worker sayısına göre |

**Yorumlama:**
- ✅ Worker sayıları auto-scaling ile optimize edilmiş
- ⚠️ Sürekli max limit'teyse: Config optimize edilmeli

#### Worker Metrics

```python
"cpu-0": {
    "active_tasks": 1,              # Şu an çalışan thread sayısı
    "queue_size": 5,                # Worker'ın kendi queue'sunda bekleyen
    "thread_pool_queue_size": 0,    # ThreadPool queue'sunda bekleyen
    "total_load": 6,                # active + queue + thread_pool_queue
    "cpu_usage": 85.3               # Worker process'in CPU kullanımı (%)
}
```

**Yorumlama:**
- ✅ `total_load < 5`: Worker rahat
- ⚠️ `total_load > 10`: Worker aşırı yüklü, scale-out gerekli
- ✅ `cpu_usage < 80%`: CPU kullanımı normal
- ⚠️ `cpu_usage > 90%`: CPU bottleneck, worker eklenmeli

---

## 📈 Performans Göstergeleri

### Throughput

```
📊 Throughput: 350 görev/saniye
```

**Yorumlama:**
- ✅ **300-500 görev/s**: İyi performans (IO-bound)
- ✅ **100-200 görev/s**: İyi performans (CPU-bound)
- ⚠️ **< 50 görev/s**: Düşük performans, optimize edilmeli

### Latency

```
📊 Ortalama Latency: 45ms
📊 P95 Latency: 120ms
📊 P99 Latency: 250ms
```

**Yorumlama:**
- ✅ **< 100ms**: Çok iyi (düşük yük)
- ✅ **100-500ms**: İyi (orta yük)
- ⚠️ **> 1000ms**: Yavaş, optimize edilmeli

### Auto-Scaling Etkinliği

```
📊 Scale Events: 15
📊 Scale-Out: 12
📊 Scale-In: 3
📊 Final Workers: 14 (CPU: 6, IO: 8)
```

**Yorumlama:**
- ✅ **Scale-Out > Scale-In**: Yük artışı var, sistem adapt oldu
- ✅ **Final Workers**: Sistem yüküne göre optimize edilmiş
- ⚠️ **Sürekli Scale**: Config optimize edilmeli

---

## 🎯 Örnek Senaryolar

### Senaryo 1: Normal Çalışma

```
INFO:engine:Engine başlatıldı
INFO:engine:Görev gönderildi: abc123...
INFO:engine:Sonuç alındı: abc123...
✅ Görev başarılı!
```

**Yorumlama:**
- ✅ Tüm işlemler başarılı
- ✅ Sistem normal çalışıyor
- ✅ Herhangi bir sorun yok

### Senaryo 2: Yüksek Yük

```
WARNING:engine:[CPU] Scale OUT +2 → 6 workers | QUEUE PRESSURE: 2500 tasks/worker
WARNING:engine:[CPU] Scale OUT +2 → 8 workers | QUEUE PRESSURE: 1250 tasks/worker
INFO:engine:[CPU] Scale OUT +1 → 9 workers | HIGH LOAD: p75=6.2
...
INFO:engine:[CPU] Scale IN -1 → 8 workers | SCALE IN: avg=0.9
```

**Yorumlama:**
- ✅ Auto-scaling çalışıyor
- ✅ Yük artışına tepki verdi
- ✅ Yük azalınca scale-in yaptı
- ✅ Sistem dengeli

### Senaryo 3: Sistem Aşırı Yüklü

```
ERROR:engine:Sistem aşırı yüklü (Backpressure Active) [TASK002]
WARNING:engine:[CPU] Scale OUT +2 → 10 workers | EMERGENCY: max_load=12.5
ERROR:engine:Sistem aşırı yüklü (Backpressure Active) [TASK002]
```

**Yorumlama:**
- ❌ Sistem kritik durumda
- ⚠️ Backpressure aktif (yeni görev kabul etmiyor)
- ✅ Auto-scaling çalışıyor ama yeterli değil
- 🔍 **Aksiyon**: Worker sayısını manuel artır veya görev göndermeyi durdur

---

## 💡 İpuçları

### 1. Log Seviyesini Ayarlayın

```python
config = EngineConfig(log_level="DEBUG")  # Daha detaylı log
```

### 2. Metrikleri Düzenli Kontrol Edin

```python
status = engine.get_status()
print(f"Queue size: {status['components']['input_queue']['metrics']['size']}")
print(f"Workers: {status['components']['process_pool']['metrics']['total_workers']}")
```

### 3. Auto-Scaling Loglarını İzleyin

```bash
# Sadece auto-scaling loglarını göster
python script.py 2>&1 | grep "Scale"
```

### 4. Hata Mesajlarını Dikkatlice Okuyun

Hata mesajları genellikle sorunun ne olduğunu açıkça belirtir:
- `[ENG001]`: Engine hatası
- `[TASK001]`: Task hatası
- `[TASK002]`: Backpressure aktif

---

## 📚 Özet

### Log Seviyeleri

- **INFO**: Normal işlemler
- **WARNING**: Auto-scaling, uyarılar
- **ERROR**: Hatalar, kritik durumlar

### Auto-Scaling Mesajları

- **QUEUE PRESSURE**: Queue'da çok görev var
- **EMERGENCY**: Kritik yük durumu
- **HIGH VELOCITY**: Yük hızla artıyor
- **HIGH LOAD**: Yüksek yük
- **SCALE IN**: Yük azaldı, worker çıkarıldı

### Metrik Yorumlama

- ✅ **Healthy**: Sistem normal
- ⚠️ **Warning**: Dikkat edilmeli
- ❌ **Critical**: Aksiyon gerekli

---

## 🔗 İlgili Dokümantasyon

- [Examples Guide](./examples_guide.md) - Kullanım örnekleri
- [Architecture](./architecture.md) - Mimari detayları
- [Module Overview](./module_overview.md) - Genel bakış

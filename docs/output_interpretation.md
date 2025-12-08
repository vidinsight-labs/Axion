# Çıktı Yorumlama Kılavuzu

Bu dokümantasyon, CPU Load Balancer örneklerinin çıktılarının nasıl yorumlanacağını detaylı olarak açıklar.

## İçindekiler

1. [Çıktı Formatı](#çıktı-formatı)
2. [Durum Mesajları](#durum-mesajları)
3. [Hata Mesajları](#hata-mesajları)
4. [İstatistikler](#istatistikler)
5. [Zamanlama Bilgileri](#zamanlama-bilgileri)

---

## Çıktı Formatı

### Genel Yapı

CPU Load Balancer çıktıları şu bölümlerden oluşur:

1. **Başlık**: Örnek adı ve ayırıcı çizgiler
2. **Config Bilgisi**: Engine yapılandırması
3. **Görev Gönderimi**: Görevlerin gönderilme durumu
4. **Sonuçlar**: Görev sonuçları
5. **İstatistikler**: Özet bilgiler
6. **Final Durum**: Sistem durumu

---

## Durum Mesajları

### ✅ Başarılı İşlemler

```
✅ Engine başlatıldı
✅ Görev gönderildi: fcccdf0b...
✅ Görev başarılı!
```

**Yorumlama:**
- İşlem başarıyla tamamlandı
- Sistem normal çalışıyor
- Devam edebilirsiniz

### ⏳ Bekleme Durumları

```
⏳ Sonuç bekleniyor...
```

**Yorumlama:**
- Görev işleniyor
- Sonuç henüz gelmedi
- Normal bir durum (bekleyin)

### ❌ Başarısız İşlemler

```
❌ Görev başarısız
❌ Timeout - sonuç alınamadı
```

**Yorumlama:**
- İşlem başarısız oldu
- Hata mesajını kontrol edin
- Sorun giderme gerekebilir

### ⚠️ Uyarılar

```
⚠️ Config yükleme hatası: ...
```

**Yorumlama:**
- Kritik olmayan bir sorun var
- Sistem çalışmaya devam edebilir
- Dikkat edilmesi gereken bir durum

---

## Hata Mesajları

### Görev Hataları

#### 1. Script Bulunamadı

```
❌ Script bulunamadı: /path/to/script.py
```

**Neden:**
- Script dosyası belirtilen yolda yok
- Dosya adı yanlış yazılmış
- Path yanlış

**Çözüm:**
```python
# Doğru path kullan
script_path = Path(__file__).parent / "script.py"
# veya
script_path = "/absolute/path/to/script.py"
```

#### 2. Main Fonksiyonu Bulunamadı

```
❌ Hata: Script'te 'main' fonksiyonu bulunamadı
```

**Neden:**
- Script'te `main(params, context)` fonksiyonu yok
- Fonksiyon adı yanlış

**Çözüm:**
```python
# Script'te main fonksiyonu olmalı
def main(params: dict, context) -> dict:
    # İşlemler
    return {"result": "success"}
```

#### 3. Timeout

```
❌ Timeout - sonuç alınamadı
```

**Neden:**
- Görev belirtilen sürede tamamlanamadı
- Worker'lar meşgul
- Görev çok uzun sürüyor

**Çözüm:**
```python
# Timeout süresini artır
result = engine.get_result(task_id, timeout=60.0)

# Veya worker sayısını artır
config = EngineConfig(io_bound_count=10)
```

#### 4. Queue Dolu

```
❌ Queue dolu, görev eklenemedi
```

**Neden:**
- Input queue maksimum kapasiteye ulaştı
- Çok fazla görev gönderildi

**Çözüm:**
```python
# Queue boyutunu artır
config = EngineConfig(input_queue_size=10000)

# Veya görev göndermeyi yavaşlat
time.sleep(0.1)  # Her görev arasında bekle
```

---

## İstatistikler

### Görev İstatistikleri

```
📈 Özet:
   Toplam görev: 8
   Başarılı: 8
   Başarısız: 0
```

**Yorumlama:**
- **Toplam görev**: Gönderilen görev sayısı
- **Başarılı**: Başarıyla tamamlanan görev sayısı
- **Başarısız**: Hata alan görev sayısı

**İdeal durum:**
- Başarılı = Toplam görev
- Başarısız = 0

### Queue İstatistikleri

```
📊 Final Durum:
   input_queue: 8 görev işlendi
   output_queue: 0 görev işlendi
```

**Yorumlama:**
- **input_queue**: Queue'ya eklenen görev sayısı
- **output_queue**: Queue'dan alınan sonuç sayısı
  - Not: Cache kullanıldığı için 0 görünebilir (normal)

### Worker İstatistikleri

```
📊 Sistem Durumu:
   Engine: 🟢 Çalışıyor
   input_queue: healthy
   output_queue: healthy
   process_pool: healthy
```

**Yorumlama:**
- **🟢 Çalışıyor**: Engine aktif
- **🔴 Durdu**: Engine durmuş
- **healthy**: Component sağlıklı
- **unhealthy**: Component'te sorun var

---

## Zamanlama Bilgileri

### Görev Gönderim Zamanı

```
[0.001s] Görev 0 gönderildi
[0.001s] Görev 1 gönderildi
[0.002s] Görev 2 gönderildi
```

**Yorumlama:**
- Görevler çok hızlı gönderildi (batch gönderim)
- Tüm görevler neredeyse aynı anda queue'ya eklendi
- Bu normal ve beklenen bir durum

### Görev Tamamlanma Zamanı

```
[0.577s] Görev 0 tamamlandı
[0.577s] Görev 1 tamamlandı
[0.578s] Görev 2 tamamlandı
```

**Yorumlama:**
- Görevler paralel çalıştı (neredeyse aynı anda tamamlandı)
- Fark çok küçük (0.001s) = Paralel işleme kanıtı
- Eğer sırayla çalışsaydı: ~5-10 saniye sürerdi

### Toplam Süre

```
Toplam süre: 0.579 saniye
Eğer sırayla çalışsaydı: ~10 saniye
Paralel çalışma oranı: 17.28x hızlanma
```

**Yorumlama:**
- **Toplam süre**: İlk görev gönderiminden son sonuç alınana kadar
- **Sırayla süre**: Eğer görevler sırayla çalışsaydı (tahmini)
- **Hızlanma**: Paralel çalışmanın sağladığı hız artışı

---

## Sonuç Verileri

### Başarılı Sonuç

```python
{
    'result': 84,
    'original_value': 42,
    'test_mode': True,
    'task_id': 'fcccdf0b-562d-4985-a019-568dacd04ae7',
    'worker_id': 'io-0',
    'status': 'success'
}
```

**Alanlar:**
- **result**: İşlem sonucu (script'in döndürdüğü ana değer)
- **original_value**: Gönderilen parametre
- **test_mode**: Test modu aktif mi?
- **task_id**: Görevin benzersiz ID'si
- **worker_id**: Görevi işleyen worker (`io-0` = IO-bound worker 0)
- **status**: Görev durumu (`success`)

### Başarısız Sonuç

```python
{
    'status': 'failed',
    'error': "Script'te 'main' fonksiyonu bulunamadı",
    'error_details': {...}
}
```

**Alanlar:**
- **status**: `failed`
- **error**: Hata mesajı
- **error_details**: Detaylı hata bilgisi (varsa)

---

## Örnek Senaryolar

### Senaryo 1: Tüm Görevler Başarılı

```
✅ 5/5 görev başarıyla tamamlandı
```

**Yorumlama:**
- Mükemmel! Tüm görevler başarılı
- Sistem normal çalışıyor
- Herhangi bir sorun yok

### Senaryo 2: Bazı Görevler Başarısız

```
✅ 3/5 görev başarıyla tamamlandı
❌ 2 görev başarısız
```

**Yorumlama:**
- Bazı görevler başarısız oldu
- Hata mesajlarını kontrol edin
- Script'leri ve parametreleri kontrol edin

### Senaryo 3: Timeout'lar

```
✅ 1/5 görev başarıyla tamamlandı
⏱️  4 görev timeout
```

**Yorumlama:**
- Çoğu görev timeout aldı
- Timeout süresini artırın
- Worker sayısını artırın
- Görevlerin çok uzun sürmediğinden emin olun

---

## İpuçları

### 1. Log Seviyesini Ayarlayın

```python
config = EngineConfig(log_level="DEBUG")
```

Daha detaylı log mesajları için.

### 2. Zamanlama Bilgilerini Takip Edin

Görevlerin ne kadar sürdüğünü görmek için zamanlama bilgilerini kullanın.

### 3. Sistem Durumunu Kontrol Edin

```python
status = engine.get_status()
print(status)
```

Sistem sağlığını kontrol edin.

### 4. Hata Mesajlarını Okuyun

Hata mesajları genellikle sorunun ne olduğunu açıkça belirtir.

---

## Özet

- ✅ **Başarılı**: İşlem tamamlandı
- ❌ **Başarısız**: Hata var, mesajı okuyun
- ⏳ **Bekleme**: Normal, bekleyin
- ⚠️ **Uyarı**: Dikkat edilmesi gereken durum
- 📊 **İstatistikler**: Sistem performansı
- 🟢 **Sağlıklı**: Sistem normal çalışıyor
- 🔴 **Sorunlu**: Sistem durmuş veya hata var

Daha fazla bilgi için `examples_guide.md` dosyasına bakın.


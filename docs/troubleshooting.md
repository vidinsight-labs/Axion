# Sorun Giderme Kılavuzu

Bu kılavuz, Axion ile karşılaşabileceğiniz yaygın sorunları tanılamanıza ve çözmenize yardımcı olur.

## İçindekiler

- [Kurulum Sorunları](#kurulum-sorunları)
- [Çalışma Zamanı Hataları](#çalışma-zamanı-hataları)
- [Performans Sorunları](#performans-sorunları)
- [Yapılandırma Problemleri](#yapılandırma-problemleri)
- [Debug İpuçları](#debug-ipuçları)

---

## Kurulum Sorunları

### Sorun: `ModuleNotFoundError: No module named 'psutil'`

**Sebep:** Gerekli bağımlılık `psutil` yüklü değil.

**Çözüm:**
```bash
pip install psutil
```

Veya tüm bağımlılıklarla birlikte kurun:
```bash
pip install -e .
```

### Sorun: `ImportError: cannot import name 'Engine'`

**Sebep:** Axion düzgün yüklenmemiş veya yanlış dizindesiniz.

**Çözüm:**
1. Kurulumu doğrulayın:
   ```bash
   pip list | grep axion
   ```

2. Development modunda yükleyin:
   ```bash
   cd /path/to/Axion
   pip install -e .
   ```

3. Import'u test edin:
   ```python
   from axion import Engine, Task, TaskType
   print("Import başarılı!")
   ```

### Sorun: Python versiyon uyumsuzluğu

**Sebep:** Axion Python 3.8 veya üzeri gerektirir.

**Çözüm:**
```bash
python --version  # Versiyonunuzu kontrol edin
# Gerekirse Python'u güncelleyin ve Axion'u tekrar kurun
```

---

## Çalışma Zamanı Hataları

### Sorun: Worker process'leri hemen kapanıyor

**Belirtiler:**
- Engine başlıyor ama görevler hiç tamamlanmıyor
- Log'larda worker process'lerinin beklenmedik şekilde kapandığı görülüyor
- `BrokenPipeError` veya `EOFError` hataları

**Olası Sebepler ve Çözümler:**

**1. Task script'inde import hatası var:**
```python
# Task script'inizin import edilebilir olduğunu kontrol edin
python -c "import your_task_module"
```

**2. Task script'inde `main()` fonksiyonu eksik:**
```python
# Task script'iniz şu formatta olmalı:
def main(params: dict, context) -> dict:
    # Kodunuz burada
    return {"result": "success"}
```

**3. Bellek sorunları:**
- EngineConfig'de worker sayısını azaltın
- `input_queue_size` ve `output_queue_size` değerlerini düşürün

### Sorun: `TaskError: Task execution failed`

**Belirtiler:**
- Görevler genel TaskError ile başarısız oluyor
- Result status "failed" döndürüyor

**Debug Adımları:**

1. **Task script'ini doğrudan test edin:**
   ```python
   # Task script'inizi manuel çalıştırın
   from your_task_module import main
   result = main({"param": "value"}, None)
   print(result)
   ```

2. **DEBUG logging'i aktifleştirin:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   
   config = EngineConfig(log_level="DEBUG")
   engine = Engine(config)
   ```

3. **Result'taki hatayı kontrol edin:**
   ```python
   result = engine.get_result(task_id)
   if result.status == TaskStatus.FAILED:
       print(f"Hata: {result.error}")
       print(f"Traceback: {result.data.get('traceback')}")
   ```

### Sorun: Görevler PENDING durumunda takılı kalıyor

**Belirtiler:**
- Görevler gönderiliyor ama hiç çalışmıyor
- Worker sayısı 0 veya worker'lar başlamıyor

**Çözümler:**

1. **Engine'in başlatıldığından emin olun:**
   ```python
   engine = Engine(config)
   engine.start()  # Bunu unutmayın!
   ```

2. **Worker sayısını kontrol edin:**
   ```python
   status = engine.get_status()
   print(f"CPU workers: {status.cpu_workers}")
   print(f"IO workers: {status.io_workers}")
   ```

3. **Görev tipinin mevcut worker'larla eşleştiğinden emin olun:**
   ```python
   # Sadece CPU worker'larınız varsa IO görev göndermeyin
   task = Task.create(
       script_path="task.py",
       params={},
       task_type=TaskType.CPU_BOUND  # Worker'larınıza uygun seçin
   )
   ```

---

## Performans Sorunları

### Sorun: Görev çalıştırma çok yavaş

**Olası Sebepler:**

**1. Yanlış görev tipi sınıflandırması:**
```python
# CPU-bound görevler (hesaplama)
task = Task.create(..., task_type=TaskType.CPU_BOUND)

# IO-bound görevler (network, dosya I/O, sleep)
task = Task.create(..., task_type=TaskType.IO_BOUND)
```

**2. Yetersiz worker sayısı:**
```python
# CPU-bound için: CPU çekirdek sayısı kadar
config = EngineConfig(
    cpu_bound_count=multiprocessing.cpu_count()
)

# IO-bound için: Worker sayısını artırın
config = EngineConfig(
    io_bound_count=20,  # CPU sayısından fazla olabilir
    io_bound_task_limit=50  # Worker başına thread sayısı
)
```

**3. Queue darboğazı:**
```python
# Yüksek throughput için queue boyutunu artırın
config = EngineConfig(
    input_queue_size=5000,  # Varsayılan 1000'den
    output_queue_size=20000  # Varsayılan 10000'den
)
```

### Sorun: Yüksek bellek kullanımı

**Sebepler ve Çözümler:**

**1. Result cache dolması:**
```python
# Sonuçlar cache'leniyor (varsayılan 5000 limit)
# Sonuçları düzenli alın ve silin:
result = engine.get_result(task_id, remove=True)  # Cache'den kaldır
```

**2. Çok fazla worker:**
```python
# Worker sayısını azaltın
config = EngineConfig(
    cpu_bound_count=4,  # Tüm çekirdekleri otomatik tespit yerine
    io_bound_count=10   # 20+ yerine
)
```

**3. Büyük görev parametreleri veya sonuçları:**
```python
# Büyük veriyi params'ta veya result'ta geçirmeyin
# Bunun yerine dosya yolu veya harici depolama kullanın:

# Kötü:
params = {"data": huge_numpy_array}

# İyi:
np.save("/tmp/data.npy", huge_numpy_array)
params = {"data_path": "/tmp/data.npy"}
```

### Sorun: CPU kullanımı sürekli %100'de

**Sebep:** Worker process'leri agresif polling yapıyor.

**Çözüm:** Bu genellikle başlangıçta geçici olur. Kalıcıysa:
```python
# Görevlerin takılı olup olmadığını kontrol edin
status = engine.get_status()
print(f"Bekleyen: {status.pending_tasks}")
print(f"Çalışan: {status.running_tasks}")

# Gerekirse shutdown ve restart
engine.shutdown()
```

---

## Yapılandırma Problemleri

### Sorun: `ConfigError: Invalid configuration parameter`

**Sebep:** EngineConfig'de geçersiz değer.

**Yaygın Hatalar:**

```python
# Worker sayıları pozitif olmalı
config = EngineConfig(cpu_bound_count=0)  # ❌ Geçersiz

# Queue boyutları pozitif olmalı
config = EngineConfig(input_queue_size=-1)  # ❌ Geçersiz

# Task limitleri >= 1 olmalı
config = EngineConfig(cpu_bound_task_limit=0)  # ❌ Geçersiz
```

**Geçerli Yapılandırma:**
```python
config = EngineConfig(
    cpu_bound_count=4,  # >= 1
    io_bound_count=10,  # >= 1 veya None (otomatik)
    input_queue_size=1000,  # > 0
    output_queue_size=10000,  # > 0
    cpu_bound_task_limit=1,  # >= 1
    io_bound_task_limit=20,  # >= 1
    log_level="INFO"  # Geçerli: DEBUG, INFO, WARNING, ERROR, CRITICAL
)
```

### Sorun: Config dosyası yüklenmiyor

**Belirtiler:**
- `config.json` dosyasındaki değişiklikler etkili olmuyor
- Varsayılan değerler kullanılıyor

**Çözüm:**

```python
# Config dosyası yerine EngineConfig'i doğrudan kullanın:
from axion import Engine, EngineConfig

config = EngineConfig(
    cpu_bound_count=8,
    io_bound_count=16
)

engine = Engine(config)
```

---

## Debug İpuçları

### Detaylı Logging Aktifleştirme

```python
import logging

# Root logger'ı yapılandırın
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Veya sadece Axion logger'ını yapılandırın
axion_logger = logging.getLogger('axion')
axion_logger.setLevel(logging.DEBUG)

config = EngineConfig(log_level="DEBUG")
engine = Engine(config)
```

### Worker Sağlığını İzleme

```python
status = engine.get_status()

print(f"CPU Workers: {status.cpu_workers} (aktif: {status.cpu_active_threads})")
print(f"IO Workers: {status.io_workers} (aktif: {status.io_active_threads})")
print(f"Görevler - Bekleyen: {status.pending_tasks}, Çalışan: {status.running_tasks}")
print(f"Tamamlanan: {status.completed_tasks}, Başarısız: {status.failed_tasks}")
print(f"Backpressure Durumu: {status.backpressure_state}")
```

### Task Script'ini İzole Test Etme

```python
# Axion ile kullanmadan önce, task script'inizi doğrudan test edin:
from my_tasks import my_task_function

# Mock context
class MockContext:
    task_id = "test-001"
    worker_id = "test-worker"

params = {"test_param": 123}
context = MockContext()

try:
    result = my_task_function.main(params, context)
    print(f"Başarılı: {result}")
except Exception as e:
    print(f"Hata: {e}")
    import traceback
    traceback.print_exc()
```

### Process Durumunu Kontrol Etme

```python
import psutil
import os

# Worker process bilgilerini al
status = engine.get_status()

for worker in engine._pool._cpu_workers + engine._pool._io_workers:
    if worker._process and worker._process.is_alive():
        proc = psutil.Process(worker._process.pid)
        print(f"Worker {worker.worker_id}:")
        print(f"  PID: {proc.pid}")
        print(f"  CPU%: {proc.cpu_percent()}")
        print(f"  Bellek: {proc.memory_info().rss / 1024 / 1024:.1f} MB")
```

### Yaygın Log Mesajları ve Anlamları

| Log Mesajı | Anlam | Aksiyon |
|------------|-------|---------|
| `Could not detect CPU count` | CPU tespiti başarısız (nadir) | Tek CPU kullanır, manuel azalt |
| `Failed to send command to worker` | Worker process öldü veya pipe bozuk | Worker loglarını kontrol et |
| `Failed to set nice level` | Öncelik ayarlama izin hatası | Uygun izinlerle çalıştır veya yoksay |
| `Backpressure activated` | Sistem yüksek yük altında | Normal, engine görev kabulünü yavaşlatır |
| `Worker process terminated unexpectedly` | Worker çöktü | Task script'indeki hataları kontrol et |

---

## CPU İzolasyon Sorunları

### Sorun: "NoBackendAvailableError: No suitable isolation backend available"

**Sebep:** Linux'ta root erişimi yok veya systemd/cgroup v2 eksik.

**Çözüm:**

**Seçenek 1: Root ile çalıştır**
```bash
sudo python -m axion.main --enable-isolation
```

**Seçenek 2: Affinity fallback kullan (root gereksiz)**
```yaml
# config.yaml
cpu_isolation:
  enabled: false
  affinity_mode: auto
```

**Seçenek 3: Sistem kontrolü**
```bash
# Systemd var mı?
systemctl --version

# Cgroup v2 aktif mi?
mount | grep cgroup2

# Root musunuz?
id -u  # 0 = root
```

---

### Sorun: "systemd-run command failed" Hatası

**Sebep:** Systemd veya cgroup v2 eksik/kapalı.

**Belirti:** İzolasyon başlatılamıyor, "Command 'systemd-run' returned non-zero exit status" hatası

**Çözüm:**

**Adım 1: Systemd versiyonu kontrol**
```bash
systemctl --version
# Minimum: systemd 226+
```

**Adım 2: Cgroup v2 kontrolü**
```bash
# Cgroup v2 mount edilmiş mi?
mount | grep cgroup2
# Beklenen: cgroup2 on /sys/fs/cgroup type cgroup2
```

**Adım 3: Cgroup v2 etkinleştir (gerekirse)**
```bash
# Grub ile cgroup v2'yi etkinleştir
sudo nano /etc/default/grub
# Ekle: GRUB_CMDLINE_LINUX="systemd.unified_cgroup_hierarchy=1"
sudo update-grub
sudo reboot
```

**Adım 4: Affinity fallback'e geç**
```yaml
# config.yaml
cpu_isolation:
  backend: noop          # Systemd'yi atlat
  affinity_mode: auto    # Affinity kullan
```

---

### Sorun: İzolasyon Etkin Ama Performans Düşük

**Sebep:** Çok az CPU Axion'a ayrılmış.

**Belirti:** 
- Worker'lar yavaş
- CPU kullanımı sürekli %100
- Gecikme beklenenden yüksek

**Çözüm:**

**Adım 1: CPU dağılımını kontrol et**
```bash
# Axion loglarında ara (log_level: DEBUG)
# Örnek log: "System CPUs: 0-5, Axion CPUs: 6-7"
#  -> Sadece 2 CPU Axion'a (çok az!)
python -m axion.main --log-level DEBUG --enable-isolation | grep "CPUs"
```

**Adım 2: Profili değiştir**
```yaml
# config.yaml
cpu_isolation:
  profile: performance  # balanced yerine
```

**Adım 3: Custom dağılım (daha fazla CPU)**
```yaml
# config.yaml
cpu_isolation:
  profile: custom
  system_cpus: "0-1"     # Sadece 2 CPU sistem için
  axion_cpus: "2-15"     # 14 CPU Axion için
```

**Adım 4: Worker sayısını ayarla**
```yaml
# Axion CPU sayısına uygun worker sayısı
# axion_cpus = 2-9 (8 CPU) ise:
cpu_bound_count: 8     # ✅ 8 worker = 8 CPU
# cpu_bound_count: 16  # ❌ Fazla worker -> context switch
```

---

### Sorun: Sistem Yanıt Vermiyor / SSH Bağlantısı Kopuyor

**Sebep:** Sistem için çok az CPU kaldı (genellikle performance profil ile).

**Belirti:**
- SSH bağlantısı yavaş/kopar
- Sistem komutları donuyor
- top/htop yanıt vermiyor

**Çözüm:**

**Acil Durum - İzolasyonu Durdur:**
```bash
# Axion'u durdur (Ctrl+C)
# restore_on_shutdown=true ise otomatik cleanup olur

# Manuel cleanup (acil durumda):
sudo systemctl reset-failed
```

**Kalıcı Çözüm - Profili Safe'e Çevir:**
```yaml
# config.yaml
cpu_isolation:
  profile: safe  # Sistem için daha fazla CPU
```

**Alternatif - System Slice Kısıtlamasını Kaldır:**
```yaml
# config.yaml
cpu_isolation:
  restrict_system_slices: false  # Sistem process'lerini serbest bırak
```

**CPU Dağılımını Kontrol Et:**
```bash
# 8 CPU sistemde performance profil:
# system: 1 CPU, axion: 7 CPU -> Sistem için çok az!

# Önerilen: balanced veya safe
# balanced: system: 2 CPU, axion: 6 CPU
# safe: system: 2 CPU, axion: 6 CPU
```

---

### Sorun: "min_cpus_required" Uyarısı

**Log Mesajı:** `"CPU isolation disabled: only X CPUs available, minimum 4 required"`

**Sebep:** Sistemde 4'ten az mantıksal CPU var.

**Çözüm:**

**Seçenek 1: CPU sayısını kontrol et**
```python
import os
print(f"CPU sayısı: {os.cpu_count()}")
```

**Seçenek 2: Minimum gereksinimi düşür (DİKKATLE!)**
```yaml
# config.yaml
cpu_isolation:
  min_cpus_required: 2  # Varsayılan: 4
```
⚠️ **Uyarı**: 4'ten az CPU'da izolasyon sistem stabilitesini etkileyebilir. Safe profil kullanın.

**Seçenek 3: İzolasyonu kapat**
```yaml
# config.yaml
cpu_isolation:
  enabled: false
```

---

### Sorun: Affinity Windows'ta Çalışmıyor

**Sebep:** Windows API sınırlamaları veya yetki eksikliği.

**Belirti:**
- `PermissionError: [WinError 5] Access is denied`
- Affinity ayarlanamıyor

**Çözüm:**

**Adım 1: Administrator olarak çalıştır**
```powershell
# PowerShell'i "Run as Administrator" ile aç
python -m axion.main --affinity-mode auto
```

**Adım 2: Affinity CPU'larını kontrol et**
```yaml
# config.yaml
cpu_isolation:
  affinity_mode: custom
  affinity_cpus: "0-3"  # Geçerli CPU aralığı (0 - cpu_count-1)
```

**Adım 3: Process hata mesajlarını kontrol et**
```bash
# DEBUG log ile detaylı hata mesajları
python -m axion.main --log-level DEBUG --affinity-mode auto
```

**Adım 4: psutil versiyonunu kontrol et**
```bash
# psutil 5.9.0+ gerekli
python -c "import psutil; print(psutil.__version__)"

# Eski versiyonsa güncelle
pip install --upgrade psutil
```

---

### Sorun: "Custom profile requires manual system_cpus and axion_cpus"

**Sebep:** Custom profil seçildi ama CPU aralıkları belirtilmedi.

**Çözüm:**

**Yanlış:**
```yaml
cpu_isolation:
  profile: custom
  system_cpus: auto    # ❌ Custom'da auto kullanılamaz
  axion_cpus: auto     # ❌
```

**Doğru:**
```yaml
cpu_isolation:
  profile: custom
  system_cpus: "0-1"   # ✅ Manuel aralık
  axion_cpus: "2-7"    # ✅ Manuel aralık
```

---

### Debug Checklist (CPU İzolasyon)

İzolasyon sorunlarını debug etmek için:

```bash
# 1. Platform kontrolü
python -c "import platform; print(f'Platform: {platform.system()}')"

# 2. CPU sayısı
python -c "import os; print(f'CPUs: {os.cpu_count()}')"

# 3. Root/Admin kontrolü
# Linux:
id -u  # 0 = root
# Windows:
net session 2>&1 | findstr /C:"Access is denied" >nul && echo Not Admin || echo Admin

# 4. Systemd kontrolü (Linux)
systemctl --version
systemctl status

# 5. Cgroup v2 kontrolü (Linux)
mount | grep cgroup2
ls /sys/fs/cgroup/

# 6. Cgroup controllers (Linux)
cat /sys/fs/cgroup/cgroup.controllers
# Beklenen: cpuset cpu io memory ...

# 7. psutil kurulu mu?
python -c "import psutil; print(f'psutil: {psutil.__version__}')"

# 8. Axion DEBUG log
python -m axion.main --log-level DEBUG --enable-isolation

# 9. Backend seçimini kontrol et
# Logda ara: "Selected backend: LinuxCgroupBackend" veya "AffinityBackend"

# 10. CPU dağılımını kontrol et
# Logda ara: "System CPUs: ..., Axion CPUs: ..."
```

### CPU İzolasyon Log Mesajları

| Log Mesajı | Anlam | Aksiyon |
|------------|-------|---------|
| `CPU isolation enabled with profile: balanced` | İzolasyon başarıyla başlatıldı | Normal |
| `Selected backend: LinuxCgroupBackend` | Linux kernel izolasyonu aktif | En iyi performans |
| `Selected backend: AffinityBackend` | Affinity fallback kullanılıyor | Normal (root yok/Windows/macOS) |
| `Selected backend: NoopBackend` | İzolasyon devre dışı | İzolasyonu etkinleştir veya affinity kullan |
| `System CPUs: 0-1, Axion CPUs: 2-7` | CPU dağılımı | Dağılımı kontrol et |
| `Failed to create cgroup` | Cgroup oluşturulamadı | Root yetkisi/cgroup v2 kontrol et |
| `Failed to set CPU affinity` | Affinity ayarlanamadı | Administrator yetkisi/psutil kontrol et |
| `CPU isolation disabled: only X CPUs` | Minimum CPU yok | min_cpus_required düşür/izolasyonu kapat |
| `Restored original systemd settings` | Cleanup başarılı | Normal shutdown |

---

## Daha Fazla Yardım

### Debug Bilgisi Toplama

```python
# Kapsamlı durum bilgisi
status = engine.get_status()
print(status.to_dict())  # Tüm durum dictionary olarak

# JSON'a aktar
import json
with open("debug_status.json", "w") as f:
    json.dump(status.to_dict(), f, indent=2)
```

### Sorun Bildirme

Sorun bildirirken şunları ekleyin:
1. Axion versiyonu: `pip show axion`
2. Python versiyonu: `python --version`
3. İşletim sistemi
4. Minimal reproduction kodu
5. Tam hata traceback'i
6. Engine status çıktısı

GitHub Issues: https://github.com/vidinsight-labs/axion/issues

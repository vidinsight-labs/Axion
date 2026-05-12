# CPU İzolasyon Rehberi

**Axion v3.0+** - Kapsamlı CPU İzolasyon Dokümantasyonu

Bu rehber, Axion'un CPU izolasyon özelliğini detaylı olarak açıklar ve kullanıcıların kritik iş yükleri için öngörülebilir performans elde etmesine yardımcı olur.

---

## 📑 İçindekiler

1. [CPU İzolasyonu Nedir?](#-cpu-izolasyonu-nedir)
2. [Ne Zaman Kullanılmalı?](#-ne-zaman-kullanılmalı)
3. [Backend Türleri](#️-backend-türleri)
4. [İzolasyon Profilleri](#-izolasyon-profilleri)
5. [Platform Desteği](#-platform-desteği)
6. [Yapılandırma](#️-yapılandırma)
7. [Kullanım Örnekleri](#-kullanım-örnekleri)
8. [Sorun Giderme](#-sorun-giderme)
9. [Performans Önerileri](#-performans-önerileri)
10. [İlgili Dokümantasyon](#-i̇lgili-dokümantasyon)

---

## 🎯 CPU İzolasyonu Nedir?

**CPU izolasyonu**, Axion worker process'lerini sistem process'lerinden ayırarak belirli CPU çekirdeklerinde çalışmasını sağlayan bir özelliktir. Bu sayede:

- **Öngörülebilir Performans**: Sistem yükü Axion performansını etkilemez
- **Düşük Gecikme**: Context switch ve cache miss azalır
- **Kaynak Garantisi**: Axion'a ayrılan CPU'lar daima kullanılabilir
- **Sistem Stabilitesi**: Axion yükü sistem servislerini engellemez

### Nasıl Çalışır?

Axion, CPU izolasyonu için iki yaklaşım sunar:

1. **Linux Kernel İzolasyonu (Full Isolation)**
   - Systemd + cgroup v2 kullanarak çekirdek seviyesinde izolasyon
   - En güçlü yöntem, root erişimi gerektirir
   - Sistem slice'larını (system.slice, user.slice) da kısıtlayabilir

2. **CPU Affinity (Fallback)**
   - psutil kütüphanesi ile process-level CPU pinning
   - Windows/macOS ve root olmayan ortamlar için
   - Daha zayıf izolasyon ama kolay kurulum

### Avantajlar

- ✅ **Cache Locality**: Worker'lar aynı CPU'da çalışarak L1/L2 cache hit rate artar
- ✅ **Context Switch Azaltma**: Kernel, process'leri izole CPU'larda tutar
- ✅ **Gecikme Garantisi**: Sistem interrupt'ları Axion worker'larını etkilemez
- ✅ **Yük İzolasyonu**: Sistem servisleri (SSH, cron, systemd) Axion performansını düşürmez

### Sınırlamalar

- ⚠️ **Root Gereksinimi**: Linux kernel izolasyonu için sudo gereklidir
- ⚠️ **Platform Bağımlılığı**: Full isolation sadece Linux + systemd + cgroup v2'de çalışır
- ⚠️ **Minimum CPU**: En az 4 mantıksal CPU önerilir (varsayılan)
- ⚠️ **Sistem Stabilitesi**: Yanlış yapılandırma sistemi yavaşlatabilir

---

## 🔍 Ne Zaman Kullanılmalı?

CPU izolasyonu aşağıdaki senaryolarda faydalıdır:

### 1. Düşük Gecikmeli İşlemler (Real-Time)

**Senaryo**: Video frame işleme, gerçek zamanlı veri analizi, canlı stream processing

**Neden İzolasyon?**: Sistem yükü (log rotation, cron jobs, SSH) gecikmeyi artırmamalı

**Örnek**:
```yaml
cpu_isolation:
  enabled: true
  profile: performance  # Maksimum CPU Axion'a
  fail_on_error: true   # Gecikme kritikse hata fırlat
```

### 2. Yüksek Öncelikli Batch İşler

**Senaryo**: ETL pipeline, büyük veri dönüşümü, makine öğrenmesi eğitimi

**Neden İzolasyon?**: İşin belirli sürede bitmesi gerekir, sistem yükü tahmin edilemez

**Örnek**:
```yaml
cpu_isolation:
  enabled: true
  profile: balanced  # Dengeli dağılım
```

### 3. Kritik Üretim İş Yükleri

**Senaryo**: Production API backend job processor, financial transaction processing

**Neden İzolasyon?**: SLA garantisi, öngörülebilir yanıt süresi

**Örnek**:
```yaml
cpu_isolation:
  enabled: true
  profile: balanced
  restrict_system_slices: true  # Sistem servisleri de kısıtla
```

### 4. Performans Benchmark'ları

**Senaryo**: Performans testi, optimizasyon çalışmaları, A/B testing

**Neden İzolasyon?**: Tekrarlanabilir sonuçlar için tutarlı ortam

**Örnek**:
```bash
python benchmarks/cpu_bound_performance_test_isolated.py --full-isolation --profile performance
```

### 5. Hibrit İş Yükleri (Paylaşımlı Sunucu)

**Senaryo**: Aynı sunucuda Axion + web server + database

**Neden İzolasyon?**: Her servis kendi CPU'larında çalışmalı

**Örnek**:
```yaml
cpu_isolation:
  enabled: true
  profile: custom
  system_cpus: "0-1"    # Sistem + web server
  axion_cpus: "2-7"     # Axion worker'ları
```

### İzolasyon GEREKLİ DEĞİL:

- ❌ Development ortamı (local geliştirme)
- ❌ Küçük batch işler (birkaç saniye süren)
- ❌ Düşük yük (CPU kullanımı %50'nin altında)
- ❌ 4'ten az CPU çekirdeği olan sistemler

---

## 🏗️ Backend Türleri

Axion üç farklı izolasyon backend'i destekler:

### 1. Linux Systemd + Cgroup v2 Backend

**En Güçlü İzolasyon - Kernel Seviyesi**

#### Nasıl Çalışır?

1. `/sys/fs/cgroup/axion-runtime` cgroup oluşturulur
2. `cpuset.cpus` controller ile CPU aralıkları ayarlanır
3. Axion worker process'leri bu cgroup'a taşınır
4. İsteğe bağlı: `system.slice`, `user.slice`, `init.scope` kısıtlanır

#### Gereksinimler

- **İşletim Sistemi**: Linux (kernel 4.5+)
- **Init System**: systemd 226+
- **Cgroup**: cgroup v2 aktif (`/sys/fs/cgroup` unified hierarchy)
- **Controller**: cpuset controller etkin
- **Yetki**: Root erişimi (sudo)

#### Kontrol

```bash
# Systemd versiyonu
systemctl --version

# Cgroup v2 mount kontrolü
mount | grep cgroup2
# Beklenen: cgroup2 on /sys/fs/cgroup type cgroup2

# cpuset controller kontrolü
cat /sys/fs/cgroup/cgroup.controllers
# Beklenen: cpuset cpu io memory ...

# Root kontrolü
id -u  # 0 = root
```

#### Avantajlar

- ✅ **Kernel Seviyesi İzolasyon**: En güçlü yöntem
- ✅ **Sistem Slice Kısıtlama**: system.slice, user.slice de kısıtlanabilir
- ✅ **Context Switch Azaltma**: Kernel, process'leri izole CPU'larda tutar
- ✅ **Cache Locality**: L1/L2/L3 cache hit rate artar
- ✅ **Interrupt İzolasyonu**: Sistem interrupt'ları izole edilebilir (IRQ affinity ile)

#### Sınırlamalar

- ❌ **Sadece Linux**: Diğer platformlarda çalışmaz
- ❌ **Root Gerekli**: sudo olmadan kullanılamaz
- ❌ **Cgroup v2 Gerekli**: Eski sistemlerde (cgroup v1) çalışmaz
- ❌ **Karmaşık**: Yanlış yapılandırma sistem stabilitesini etkileyebilir

---

### 2. CPU Affinity Backend (Fallback)

**Çapraz Platform - Process Seviyesi**

#### Nasıl Çalışır?

1. `psutil` kütüphanesi ile worker process ID'leri alınır
2. `psutil.Process().cpu_affinity()` API ile CPU maskeleme yapılır
3. Her worker belirtilen CPU aralığında çalışır

#### Gereksinimler

- **Kütüphane**: psutil 5.9.0+
- **İşletim Sistemi**: Linux, Windows 10/11, macOS
- **Yetki**: Linux'ta root gereksiz, Windows'ta Administrator önerilir

#### Kontrol

```bash
# psutil kurulu mu?
python -c "import psutil; print(psutil.__version__)"

# CPU affinity test
python -c "import psutil; p = psutil.Process(); print(p.cpu_affinity())"
```

#### Avantajlar

- ✅ **Çapraz Platform**: Linux, Windows, macOS
- ✅ **Root Gereksiz** (Linux'ta)
- ✅ **Basit Kurulum**: Sadece psutil gerekli
- ✅ **Hızlı Başlatma**: Cgroup oluşturma overhead'i yok

#### Sınırlamalar

- ⚠️ **Process Seviyesi İzolasyon**: Kernel seviyesi kadar güçlü değil
- ⚠️ **Sistem Process'leri Etkilenmez**: system.slice kısıtlanamaz
- ⚠️ **macOS Kısıtlamaları**: macOS API'si CPU affinity'yi tam desteklemez
- ⚠️ **Windows Admin**: Windows'ta Administrator ayrıcalıkları gereklidir

---

### 3. Noop Backend

**İzolasyon Devre Dışı - Fallback**

#### Nasıl Çalışır?

- Hiçbir izolasyon uygulamaz
- Engine normal modda çalışır
- Hata durumlarında otomatik fallback olarak kullanılır

#### Ne Zaman Aktif Olur?

- `enabled: false` ise
- `backend: noop` olarak belirtilmişse
- İzolasyon başarısız oldu ve `fail_on_error: false` ise
- Sistem izolasyonu desteklemiyorsa (cgroup v2 yok, psutil yok)

---

### Backend Karşılaştırma Tablosu

| Özellik | Linux Cgroup v2 | CPU Affinity | Noop |
|---------|----------------|--------------|------|
| **İzolasyon Seviyesi** | Çekirdek | Process | Yok |
| **Platform** | Linux | Linux, Windows, macOS | Tümü |
| **Root Gerekli?** | Evet | Hayır (Linux), Evet (Windows) | Hayır |
| **Sistem Slice Kısıtlama** | Evet | Hayır | Hayır |
| **Context Switch Azaltma** | Yüksek | Orta | Yok |
| **Cache Locality** | Yüksek | Orta | Yok |
| **Interrupt İzolasyonu** | Evet (manuel IRQ affinity ile) | Hayır | Hayır |
| **Kurulum Karmaşıklığı** | Yüksek | Düşük | Yok |
| **Performans İyileştirme** | %20-40 gecikme azaltma | %5-15 gecikme azaltma | Yok |

---

## 📊 İzolasyon Profilleri

Axion, CPU dağılımı için 4 hazır profil sunar:

### 1. Safe Profile

**En Güvenli Yaklaşım - Sistem Stabilitesi Öncelikli**

- **Hedef**: Sistem servislerinin (SSH, systemd, logging) her zaman responsive olması
- **Dağılım**: Sisteme daha fazla CPU rezerve eder
- **Kullanım**: Paylaşımlı sunucular, kritik sistem servisleri olan ortamlar

**CPU Dağılımı**:

| Toplam CPU | Sistem CPU | Axion CPU | Örnek Aralık |
|------------|------------|-----------|--------------|
| 4 | 1 | 3 | system: 0, axion: 1-3 |
| 8 | 2 | 6 | system: 0-1, axion: 2-7 |
| 16 | 4 | 12 | system: 0-3, axion: 4-15 |
| 32 | 8 | 24 | system: 0-7, axion: 8-31 |
| 64 | 16 | 48 | system: 0-15, axion: 16-63 |

**Örnek**:
```yaml
cpu_isolation:
  enabled: true
  profile: safe
```

---

### 2. Balanced Profile (Varsayılan)

**Dengeli Dağılım - Genel Amaçlı**

- **Hedef**: Sistem ve Axion arasında dengeli performans
- **Dağılım**: Sisteme makul sayıda CPU, Axion'a yeterli kaynak
- **Kullanım**: Çoğu production ortamı, genel batch işler

**CPU Dağılımı**:

| Toplam CPU | Sistem CPU | Axion CPU | Örnek Aralık |
|------------|------------|-----------|--------------|
| 4 | 1 | 3 | system: 0, axion: 1-3 |
| 8 | 2 | 6 | system: 0-1, axion: 2-7 |
| 16 | 3 | 13 | system: 0-2, axion: 3-15 |
| 32 | 6 | 26 | system: 0-5, axion: 6-31 |
| 64 | 11 | 53 | system: 0-10, axion: 11-63 |

**Örnek**:
```yaml
cpu_isolation:
  enabled: true
  profile: balanced  # Varsayılan, belirtilmese de bu
```

---

### 3. Performance Profile

**Maksimum Performans - Axion Öncelikli**

- **Hedef**: Axion'a maksimum CPU, en düşük gecikme
- **Dağılım**: Sisteme minimum CPU (1-3), Axion'a kalan tümü
- **Kullanım**: Dedicated Axion sunucuları, real-time processing, benchmark'lar

**CPU Dağılımı**:

| Toplam CPU | Sistem CPU | Axion CPU | Örnek Aralık |
|------------|------------|-----------|--------------|
| 4 | 1 | 3 | system: 0, axion: 1-3 |
| 8 | 1 | 7 | system: 0, axion: 1-7 |
| 16 | 2 | 14 | system: 0-1, axion: 2-15 |
| 32 | 4 | 28 | system: 0-3, axion: 4-31 |
| 64 | 8 | 56 | system: 0-7, axion: 8-63 |

**⚠️ Dikkat**: Sistem için çok az CPU kalabilir. SSH bağlantısı yavaşlayabilir.

**Örnek**:
```yaml
cpu_isolation:
  enabled: true
  profile: performance
```

---

### 4. Custom Profile

**Manuel Kontrol - Özel Gereksinimler**

- **Hedef**: Tam kontrol, özel dağılım senaryoları
- **Dağılım**: Kullanıcı manuel `system_cpus` ve `axion_cpus` belirtir
- **Kullanım**: Hibrit iş yükleri, NUMA awareness, özel topolojiler

**Örnek 1: Basit Custom**
```yaml
cpu_isolation:
  enabled: true
  profile: custom
  system_cpus: "0-1"     # CPU 0 ve 1 sistem için
  axion_cpus: "2-7"      # CPU 2-7 Axion için
```

**Örnek 2: NUMA-Aware (2 soket)**
```yaml
# NUMA node 0: CPU 0-15, NUMA node 1: CPU 16-31
cpu_isolation:
  enabled: true
  profile: custom
  system_cpus: "0-3"     # NUMA node 0'dan 4 CPU
  axion_cpus: "16-31"    # NUMA node 1 tamamen Axion'a
```

**Örnek 3: Hibrit (Web + Axion + Database)**
```yaml
# CPU 0-1: Web server
# CPU 2-7: Axion
# CPU 8-9: Database
cpu_isolation:
  enabled: true
  profile: custom
  system_cpus: "0-1,8-9"  # Sistem + database
  axion_cpus: "2-7"       # Axion worker'ları
```

**Kurallar**:
- `system_cpus` ve `axion_cpus` kesişmemelidir
- Her iki alan da en az 1 CPU içermelidir
- CPU index'leri geçerli aralıkta olmalıdır (0 - cpu_count-1)

---

### Profil Seçim Rehberi

| Senaryo | Önerilen Profil | Sebep |
|---------|----------------|-------|
| Development | İzolasyon kapalı | Debug kolaylığı |
| Shared server | Safe | Sistem stabilitesi |
| Production (genel) | Balanced | Dengeli performans |
| Real-time processing | Performance | Düşük gecikme |
| Dedicated Axion server | Performance | Maksimum throughput |
| Hibrit iş yükü | Custom | Özel dağılım |
| Benchmark test | Performance | Tutarlı sonuçlar |

---

## 💻 Platform Desteği

### Linux (Tam Destek) ✅

**Backend 1: Systemd + Cgroup v2 (Full Isolation)**

- **Desteklenen Dağıtımlar**: Ubuntu 20.04+, Fedora 31+, Arch Linux, Debian 11+
- **Gereksinimler**: kernel 4.5+, systemd 226+, cgroup v2, root
- **Performans**: En iyi izolasyon, %20-40 gecikme azaltma

**Backend 2: CPU Affinity (Fallback)**

- **Desteklenen Dağıtımlar**: Tüm Linux dağıtımları
- **Gereksinimler**: psutil, root gereksiz
- **Performans**: İyi izolasyon, %5-15 gecikme azaltma

**Önerilen Kurulum**:
```bash
# Cgroup v2 kontrolü
mount | grep cgroup2

# Yoksa etkinleştir (Ubuntu/Debian)
sudo nano /etc/default/grub
# Ekle: GRUB_CMDLINE_LINUX="systemd.unified_cgroup_hierarchy=1"
sudo update-grub
sudo reboot
```

---

### Windows 10/11 (Sınırlı Destek) ⚠️

**Backend: CPU Affinity**

- **Desteklenen Versiyonlar**: Windows 10, Windows 11, Windows Server 2019+
- **Gereksinimler**: psutil, Administrator ayrıcalıkları
- **Performans**: Orta izolasyon, %5-10 gecikme azaltma
- **Sınırlama**: Sistem process'leri kısıtlanamaz

**Kurulum**:
```powershell
# psutil yükle
pip install psutil

# Administrator olarak çalıştır
# PowerShell'i "Run as Administrator" ile aç
python -m axion.main --affinity-mode auto
```

---

### macOS (Sınırlı Destek) ⚠️

**Backend: CPU Affinity (Kısıtlı)**

- **Desteklenen Versiyonlar**: macOS 10.15+
- **Gereksinimler**: psutil
- **Performans**: Zayıf izolasyon, %0-5 gecikme azaltma
- **Sınırlama**: macOS API CPU affinity'yi tam desteklemez

**Not**: macOS'ta `thread_policy_set` API kısıtlıdır. Affinity "öneri" olarak çalışır, garanti değildir.

**Kurulum**:
```bash
pip install psutil
python -m axion.main --affinity-mode auto
```

---

## ⚙️ Yapılandırma

CPU izolasyonu `config.yaml` dosyası veya CLI argümanları ile yapılandırılır.

### Minimum Örnek

```yaml
# config.yaml
cpu_isolation:
  enabled: true
  profile: balanced
```

### Tam Özellikli Örnek

```yaml
# config.yaml
cpu_isolation:
  # Temel Ayarlar
  enabled: true                                # İzolasyonu etkinleştir
  backend: auto                                 # auto | linux_systemd_cgroup | noop
  profile: balanced                             # safe | balanced | performance | custom
  
  # CPU Dağılımı (custom profil için)
  system_cpus: auto                             # "0-1" veya auto
  axion_cpus: auto                              # "2-7" veya auto
  
  # Cgroup Yönetimi (Linux)
  restrict_system_slices: true                  # system.slice'ı da kısıtla
  restore_on_shutdown: true                     # Kapanışta geri yükle
  cgroup_root: /sys/fs/cgroup/axion-runtime     # Cgroup yolu
  min_cpus_required: 4                          # Minimum CPU sayısı
  fail_on_error: false                          # Hata durumunda fail
  
  # Affinity Fallback (enabled=false iken)
  affinity_mode: disabled                       # disabled | auto | custom
  affinity_cpus: auto                           # "2-3" veya auto
```

### Parametreler

**Detaylı parametre referansı için**: [Config README](../axion/config/README.md)

| Parametre | Tip | Varsayılan | Açıklama |
|-----------|-----|------------|----------|
| `enabled` | bool | false | CPU izolasyonunu etkinleştir (Linux cgroup) |
| `backend` | str | auto | Backend seçimi: auto, linux_systemd_cgroup, noop |
| `profile` | str | balanced | CPU dağılım profili: safe, balanced, performance, custom |
| `system_cpus` | str | auto | Sistem CPU aralığı (örn: "0-1") |
| `axion_cpus` | str | auto | Axion CPU aralığı (örn: "2-7") |
| `restrict_system_slices` | bool | true | system.slice/user.slice'ı kısıtla |
| `restore_on_shutdown` | bool | true | Kapanışta ayarları geri yükle |
| `cgroup_root` | str | /sys/fs/cgroup/axion-runtime | Axion cgroup yolu |
| `min_cpus_required` | int | 4 | İzolasyon için minimum CPU sayısı |
| `fail_on_error` | bool | false | Hata durumunda engine'i durdur |
| `affinity_mode` | str | disabled | Affinity modu: disabled, auto, custom |
| `affinity_cpus` | str | auto | Affinity CPU aralığı |

### CLI Argümanları

```bash
# İzolasyonu etkinleştir
python -m axion.main --enable-isolation

# Profil belirt
python -m axion.main --enable-isolation --isolation-profile balanced

# Backend belirt
python -m axion.main --enable-isolation --isolation-backend linux_systemd_cgroup

# Custom CPU aralıkları
python -m axion.main --enable-isolation --system-cpus "0-1" --axion-cpus "2-7"

# Affinity fallback
python -m axion.main --affinity-mode auto --affinity-cpus "2-3"
```

---

## 🚀 Kullanım Örnekleri

### Örnek 1: Basit Balanced İzolasyon

**Senaryo**: Production batch job, varsayılan izolasyon

```yaml
# config.yaml
cpu_isolation:
  enabled: true
  profile: balanced
```

```python
# main.py
from axion import Engine, EngineConfig

config = EngineConfig.load("config.yaml")
with Engine(config=config) as engine:
    # İzolasyonlu engine çalışıyor
    task_id = engine.submit_task(task)
    result = engine.get_result(task_id)
```

**Sonuç**: 8 CPU'lu sistemde → system: 0-1, axion: 2-7

---

### Örnek 2: Custom CPU Aralıkları

**Senaryo**: Hibrit iş yükü, manuel CPU dağılımı

```yaml
# config.yaml
cpu_isolation:
  enabled: true
  profile: custom
  system_cpus: "0-1"      # CPU 0-1 sistem için
  axion_cpus: "2-7"       # CPU 2-7 Axion için
```

```bash
# Web server'ı sistem CPU'larında çalıştır (Linux)
taskset -c 0-1 uvicorn api:app

# Axion'u izolasyon ile başlat
python -m axion.main --config config.yaml
```

---

### Örnek 3: Affinity Fallback (Root Olmadan)

**Senaryo**: Root erişimi yok, affinity ile izolasyon

```yaml
# config.yaml
cpu_isolation:
  enabled: false          # Cgroup izolasyonu kapalı
  affinity_mode: auto     # Affinity etkin
  affinity_cpus: auto     # Otomatik hesaplama
```

```python
# main.py
from axion import Engine, EngineConfig

config = EngineConfig.load("config.yaml")
with Engine(config=config) as engine:
    # Affinity ile izolasyon
    pass
```

**Sonuç**: Worker'lar psutil ile CPU'lara pinlenecek (root gereksiz)

---

### Örnek 4: Benchmark için Performance Profile

**Senaryo**: Performans testi, maksimum CPU Axion'a

```bash
# Komut satırından
python benchmarks/cpu_bound_performance_test_isolated.py --full-isolation --profile performance
```

```yaml
# Veya config ile
cpu_isolation:
  enabled: true
  profile: performance
  fail_on_error: true     # Benchmark için hata toleransı yok
```

---

### Örnek 5: Windows'ta Affinity

**Senaryo**: Windows ortamı, Administrator ile affinity

```yaml
# config.yaml (Windows)
cpu_isolation:
  enabled: false          # Linux cgroup çalışmaz
  affinity_mode: custom
  affinity_cpus: "2-7"    # CPU 2-7'ye pinle
```

```powershell
# PowerShell (Administrator olarak)
python -m axion.main --config config.yaml
```

---

## 🔧 Sorun Giderme

### Sık Karşılaşılan Problemler

#### 1. "NoBackendAvailableError: No suitable isolation backend available"

**Sebep**: Linux'ta root erişimi yok veya systemd/cgroup v2 eksik

**Çözüm**:

**Seçenek A: Root ile çalıştır**
```bash
sudo python -m axion.main --enable-isolation
```

**Seçenek B: Affinity fallback kullan**
```yaml
cpu_isolation:
  enabled: false
  affinity_mode: auto
```

**Seçenek C: Sistem kontrolü**
```bash
# Systemd var mı?
systemctl --version

# Cgroup v2 aktif mi?
mount | grep cgroup2

# Root musunuz?
id -u  # 0 = root
```

---

#### 2. "systemd-run command failed" Hatası

**Sebep**: Systemd veya cgroup v2 eksik/kapalı

**Çözüm**:

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
cpu_isolation:
  backend: noop          # Systemd'yi atlat
  affinity_mode: auto
```

---

#### 3. İzolasyon Etkin Ama Performans Düşük

**Sebep**: Çok az CPU Axion'a ayrılmış

**Belirti**: Worker'lar yavaş, CPU kullanımı %100

**Çözüm**:

**Adım 1: CPU dağılımını kontrol et**
```python
# Axion loglarında ara:
# "System CPUs: 0-5, Axion CPUs: 6-7" -> Çok az Axion CPU'su!
```

**Adım 2: Profili değiştir**
```yaml
cpu_isolation:
  profile: performance  # balanced yerine
```

**Adım 3: VEYA Custom dağılım**
```yaml
cpu_isolation:
  profile: custom
  system_cpus: "0-1"
  axion_cpus: "2-15"    # Daha fazla CPU
```

**Adım 4: Worker sayısını ayarla**
```yaml
# Axion CPU sayısından fazla worker açma
cpu_bound_count: 8  # axion_cpus = 2-9 ise (8 CPU)
```

---

#### 4. Sistem Yanıt Vermiyor / SSH Bağlantısı Kopuyor

**Sebep**: Sistem için çok az CPU kaldı (performance profil)

**Çözüm**:

**Acil Müdahale**:
```bash
# Axion'u durdur (Ctrl+C)
# restore_on_shutdown=true ise otomatik cleanup olur

# Manuel cleanup (gerekirse):
sudo systemctl reset-failed
```

**Profili safe'e çevir**:
```yaml
cpu_isolation:
  profile: safe  # Sistem için daha fazla CPU
```

**System slice kısıtlamasını kaldır**:
```yaml
cpu_isolation:
  restrict_system_slices: false  # Sistem process'lerini serbest bırak
```

---

#### 5. "min_cpus_required" Uyarısı

**Log Mesajı**: `"CPU isolation disabled: only X CPUs available, minimum 4 required"`

**Sebep**: Sistemde 4'ten az mantıksal CPU var

**Çözüm**:

**Seçenek A: CPU sayısını kontrol et**
```python
import os
print(os.cpu_count())
```

**Seçenek B: Minimum gereksinimi düşür (DİKKATLE!)**
```yaml
cpu_isolation:
  min_cpus_required: 2  # Varsayılan: 4
```
⚠️ **Uyarı**: 4'ten az CPU'da izolasyon sistem stabilitesini etkileyebilir

**Seçenek C: İzolasyonu kapat**
```yaml
cpu_isolation:
  enabled: false
```

---

#### 6. Affinity Windows'ta Çalışmıyor

**Sebep**: Windows API sınırlamaları veya yetki eksikliği

**Çözüm**:

**Adım 1: Administrator olarak çalıştır**
```powershell
# PowerShell'i "Run as Administrator" ile aç
python -m axion.main --affinity-mode auto
```

**Adım 2: Affinity CPU'larını kontrol et**
```yaml
cpu_isolation:
  affinity_mode: custom
  affinity_cpus: "0-3"  # Geçerli aralık belirt
```

**Adım 3: Process hata mesajlarını kontrol et**
```bash
python -m axion.main --log-level DEBUG --affinity-mode auto
```

---

### Debug Checklist

İzolasyon sorunlarını debug etmek için:

```bash
# 1. Platform
python -c "import platform; print(platform.system())"

# 2. CPU sayısı
python -c "import os; print(f'CPUs: {os.cpu_count()}')"

# 3. Root/Admin kontrolü
# Linux:
id -u  # 0 = root
# Windows:
net session  # "Access is denied" -> admin değil

# 4. Systemd kontrolü (Linux)
systemctl --version
systemctl status

# 5. Cgroup v2 kontrolü (Linux)
mount | grep cgroup2
ls /sys/fs/cgroup/

# 6. psutil kurulu mu?
python -c "import psutil; print(psutil.__version__)"

# 7. Axion DEBUG log
python -m axion.main --log-level DEBUG --enable-isolation

# 8. Backend seçimini kontrol et
# Logda ara: "Selected backend: LinuxCgroupBackend" veya "AffinityBackend"
```

---

## 💡 Performans Önerileri

### 1. Profil Seçimi

| Ortam | Profil | Sebep |
|-------|--------|-------|
| Development | İzolasyon kapalı | Debug kolaylığı, esneklik |
| Staging | Balanced | Production benzeri test |
| Production (paylaşımlı) | Safe | Sistem stabilitesi |
| Production (dedicated) | Performance | Maksimum performans |
| Benchmark | Performance | Tutarlı sonuçlar |

### 2. Worker Sayısı Ayarı

```yaml
# Kötü: Axion CPU sayısından fazla worker
cpu_isolation:
  axion_cpus: "2-7"  # 6 CPU
cpu_bound_count: 12  # ❌ 12 worker -> Context switch

# İyi: Worker sayısı = CPU sayısı
cpu_isolation:
  axion_cpus: "2-7"  # 6 CPU
cpu_bound_count: 6   # ✅ 6 worker
```

### 3. Benchmark Önemi

```bash
# İzolasyonsuz baseline
python benchmarks/cpu_bound_performance_test_isolated.py --no-isolation

# Affinity ile test
python benchmarks/cpu_bound_performance_test_isolated.py --affinity

# Full isolation ile test
python benchmarks/cpu_bound_performance_test_isolated.py --full-isolation --profile balanced

# Sonuçları karşılaştır
# Gecikme %20+ azaldıysa izolasyon faydalı
```

### 4. Sistem İzleme

```bash
# CPU kullanımını izle
htop  # Veya top

# Worker process'leri bul
ps aux | grep axion

# CPU affinity kontrolü
taskset -cp <PID>

# Cgroup kontrolü (Linux)
cat /sys/fs/cgroup/axion-runtime/cpuset.cpus
```

### 5. Production Ayarları

```yaml
# Önerilen production config
cpu_isolation:
  enabled: true
  profile: balanced               # Veya safe (shared server)
  backend: auto                    # Platform otomatik seçimi
  restrict_system_slices: true     # Sistem servisleri de kısıtla
  restore_on_shutdown: true        # Cleanup otomatik
  fail_on_error: true              # Production'da hata toleransı yok
  min_cpus_required: 8             # Küçük sistemlerde devre dışı
```

### 6. İzolasyon + NUMA Awareness

```yaml
# 2 NUMA node olan sistemlerde (örn: dual socket server)
# NUMA node 0: CPU 0-15
# NUMA node 1: CPU 16-31

cpu_isolation:
  enabled: true
  profile: custom
  system_cpus: "0-3"      # NUMA 0'dan 4 CPU
  axion_cpus: "16-31"     # NUMA 1 tamamen Axion'a
```

**Avantaj**: Memory access latency azalır (local memory access)

---

## 🔗 İlgili Dokümantasyon

- [Yapılandırma Rehberi](../axion/config/README.md) - Tüm config parametreleri
- [Mimari Dokümantasyon](architecture.md) - İzolasyon mimarisi, backend'ler, algoritmalar
- [Sorun Giderme Rehberi](troubleshooting.md) - Yaygın problemler ve çözümleri
- [Benchmark Rehberi](../benchmarks/benchmark_guide.md) - Performans testleri
- [Integration Guide](integration_guide.md) - Production deployment senaryoları

---

## 📝 Özet

- **CPU İzolasyonu**: Axion worker'larını sistem process'lerinden ayırır
- **İki Backend**: Linux kernel (güçlü) + CPU affinity (çapraz platform)
- **Dört Profil**: safe, balanced, performance, custom
- **Platform**: Linux (tam), Windows (sınırlı), macOS (sınırlı)
- **Performans**: %5-40 gecikme azaltma (backend ve profile göre)
- **Kullanım**: Real-time, batch, benchmark, production kritik iş yükleri

**Başlangıç için**:
```yaml
cpu_isolation:
  enabled: true
  profile: balanced
```

```bash
sudo python -m axion.main --config config.yaml
```
# Config Klasörü

Bu klasör, Axion'un yapılandırma dosyalarını ve konfigürasyon sınıflarını içerir.

## Dosyalar

- `config.yaml` - Varsayılan YAML yapılandırma şablonu
- `engine_config.py` - EngineConfig dataclass tanımı
- `cpu_isolation_config.py` - CpuIsolationConfig dataclass tanımı
- `__init__.py` - Modül exports

## Config Dosyası Formatı

**Axion v3.0+** YAML formatını kullanır (eski JSON formatı desteklenmez).

```yaml
# config.yaml

# Queue Ayarları
input_queue_size: 1000
output_queue_size: 10000

# Worker Ayarları
cpu_bound_count: 3
io_bound_count: null  # null = otomatik (CPU sayısı - 1)
cpu_bound_task_limit: 1
io_bound_task_limit: 20

# Genel Ayarlar
log_level: INFO
queue_poll_timeout: 1.0

# CPU İzolasyon Ayarları
cpu_isolation:
  enabled: false
  backend: auto
  profile: balanced
  system_cpus: auto
  axion_cpus: auto
  restrict_system_slices: true
  restore_on_shutdown: true
  cgroup_root: /sys/fs/cgroup/axion-runtime
  min_cpus_required: 4
  fail_on_error: false
  affinity_mode: disabled
  affinity_cpus: auto
```

## Parametreler

### Queue Ayarları
- `input_queue_size`: Input queue maksimum boyutu (varsayılan: 1000)
- `output_queue_size`: Output queue maksimum boyutu (varsayılan: 10000)

### Worker Ayarları
- `cpu_bound_count`: CPU-bound worker sayısı (varsayılan: 1)
- `io_bound_count`: IO-bound worker sayısı (varsayılan: null = otomatik, CPU sayısı - 1)
- `cpu_bound_task_limit`: CPU-bound worker başına thread sayısı (varsayılan: 1)
- `io_bound_task_limit`: IO-bound worker başına thread sayısı (varsayılan: 20)

### Genel Ayarlar
- `log_level`: Log seviyesi (DEBUG, INFO, WARNING, ERROR, CRITICAL) (varsayılan: INFO)
- `queue_poll_timeout`: Queue polling timeout süresi (saniye) (varsayılan: 1.0)

### CPU İzolasyon Ayarları

**Not**: CPU izolasyonu hakkında detaylı bilgi için [CPU İzolasyon Rehberi](../docs/cpu_isolation.md)'ne bakın.

#### Temel Ayarlar
- `cpu_isolation.enabled`: CPU izolasyonunu etkinleştir (Linux cgroup v2 izolasyonu) (varsayılan: false)
- `cpu_isolation.backend`: Backend seçimi - "auto", "linux_systemd_cgroup", "noop" (varsayılan: auto)
  - `auto`: Platform ve sistem yeteneklerine göre otomatik backend seçimi
  - `linux_systemd_cgroup`: Linux systemd + cgroup v2 backend (root gerekli)
  - `noop`: İzolasyon yok, normal mod
- `cpu_isolation.profile`: CPU dağılım profili - "safe", "balanced", "performance", "custom" (varsayılan: balanced)
  - `safe`: Sistem için daha fazla CPU rezerve eder (paylaşımlı sunucular)
  - `balanced`: Dengeli dağılım (genel amaçlı, varsayılan)
  - `performance`: Axion'a maksimum CPU (dedicated sunucular, real-time)
  - `custom`: Manuel CPU aralıkları (system_cpus ve axion_cpus gerekli)

#### CPU Dağılımı
- `cpu_isolation.system_cpus`: Sistem için rezerve edilen CPU'lar (örn: "0-1", "0,2,4") (varsayılan: auto)
  - Profile'a göre otomatik hesaplanır (auto ise)
  - Custom profil için manuel belirtilmelidir
  - Format: "0-3", "0,2,4", "0-1,4-7"
- `cpu_isolation.axion_cpus`: Axion worker'ları için CPU'lar (örn: "2-7") (varsayılan: auto)
  - Profile'a göre otomatik hesaplanır (auto ise)
  - Custom profil için manuel belirtilmelidir
  - Format: system_cpus ile aynı

#### Cgroup Yönetimi (Linux)
- `cpu_isolation.restrict_system_slices`: system.slice/user.slice/init.scope'u system CPU'lara kısıtla (varsayılan: true)
  - true: Sistem servisleri de izole edilir (SSH, systemd, logging)
  - false: Sadece Axion worker'ları izole edilir
- `cpu_isolation.restore_on_shutdown`: Engine kapanırken systemd CPU ayarlarını geri yükle (varsayılan: true)
  - Graceful cleanup için önerilir
- `cpu_isolation.cgroup_root`: Axion worker process'lerinin taşınacağı cgroup yolu (varsayılan: /sys/fs/cgroup/axion-runtime)
- `cpu_isolation.min_cpus_required`: İzolasyon için minimum mantıksal CPU sayısı (varsayılan: 4)
  - Sistemde bu sayıdan az CPU varsa izolasyon devre dışı kalır
- `cpu_isolation.fail_on_error`: İzolasyon hatası durumunda engine'i durdur (varsayılan: false)
  - true: Hata durumunda exception fırlatılır, engine başlamaz
  - false: Warning verip noop backend'e geçilir (graceful fallback)

#### Affinity Fallback (Root Olmadan)
- `cpu_isolation.affinity_mode`: CPU affinity modu - "disabled", "auto", "custom" (varsayılan: disabled)
  - `disabled`: Affinity kapalı
  - `auto`: Profile'a göre otomatik CPU aralığı
  - `custom`: affinity_cpus manuel verilmelidir
  - **Not**: Sadece enabled=false iken uygulanır (cgroup ve affinity beraber çalışmaz)
- `cpu_isolation.affinity_cpus`: Affinity için CPU aralığı (custom mode için gerekli) (varsayılan: auto)
  - Format: "2-7", "0,2,4"
  - affinity_mode=custom ise zorunlu

## Kullanım

### Varsayılan Config ile
```bash
python -m axion.main
# Sırasıyla aranır: ./config.yaml → ./axion/config/config.yaml → paket varsayılanı
```

### Özel Config ile
```bash
python -m axion.main --config my_config.yaml
python -m axion.main --config configs/production.yaml
```

### Varsayılan Config Oluştur
```bash
python -m axion.main --create-config
# config.yaml dosyası oluşturulur (mevcut dizinde)
```

### CLI ile Config Override
```bash
# Worker sayıları
python -m axion.main --cpu-workers 4 --io-workers 8

# Log seviyesi
python -m axion.main --log-level DEBUG

# CPU izolasyonu
python -m axion.main --enable-isolation --isolation-profile balanced

# Custom CPU aralıkları
python -m axion.main --enable-isolation --isolation-profile custom --system-cpus "0-1" --axion-cpus "2-7"

# Affinity fallback
python -m axion.main --affinity-mode auto --affinity-cpus "2-3"

# Birden fazla parametre
python -m axion.main --config my_config.yaml --cpu-workers 8 --enable-isolation --isolation-profile performance
```

**Not**: CLI argümanları config dosyasındaki değerlerin üzerine yazar.

---

## Örnek Config Dosyaları

Farklı senaryolar için özel config dosyaları oluşturabilirsiniz:

### Production (İzolasyon Etkin)

```yaml
# config.production.yaml
input_queue_size: 2000
output_queue_size: 20000

cpu_bound_count: 8
io_bound_count: 15
cpu_bound_task_limit: 1
io_bound_task_limit: 20

log_level: WARNING
queue_poll_timeout: 1.0

cpu_isolation:
  enabled: true
  backend: auto
  profile: performance           # Maksimum performans
  restrict_system_slices: true
  restore_on_shutdown: true
  fail_on_error: true            # Production'da hata toleransı yok
  min_cpus_required: 8           # Küçük sistemlerde devre dışı
```

### Development (İzolasyon Devre Dışı)

```yaml
# config.development.yaml
input_queue_size: 100
output_queue_size: 1000

cpu_bound_count: 2
io_bound_count: 4
cpu_bound_task_limit: 1
io_bound_task_limit: 10

log_level: DEBUG
queue_poll_timeout: 1.0

cpu_isolation:
  enabled: false  # Development'ta izolasyon gereksiz
```

### Test (Minimal)

```yaml
# config.test.yaml
input_queue_size: 50
output_queue_size: 100

cpu_bound_count: 1
io_bound_count: 1
cpu_bound_task_limit: 1
io_bound_task_limit: 5

log_level: INFO
queue_poll_timeout: 0.5

cpu_isolation:
  enabled: false
```

### Hibrit İş Yükü (Custom CPU Dağılımı)

```yaml
# config.hybrid.yaml
# Senaryo: Aynı sunucuda web server + Axion + database

cpu_bound_count: 6
io_bound_count: 8

log_level: INFO

cpu_isolation:
  enabled: true
  backend: auto
  profile: custom
  system_cpus: "0-1,8-9"      # CPU 0-1: Web, CPU 8-9: Database
  axion_cpus: "2-7"           # CPU 2-7: Axion worker'ları
  restrict_system_slices: false  # Sistem servisleri serbest
```

### Affinity Fallback (Root Olmadan)

```yaml
# config.affinity.yaml
# Senaryo: Root erişimi yok, Linux/Windows affinity kullan

cpu_bound_count: 4
io_bound_count: 6

log_level: INFO

cpu_isolation:
  enabled: false              # Cgroup izolasyonu kapalı
  affinity_mode: auto         # Affinity etkin
  affinity_cpus: auto         # Otomatik hesaplama (profile'a göre)
```

---

## JSON'dan YAML'a Geçiş Rehberi

**Axion v3.0+** YAML yapılandırma formatını kullanır. Eğer eski `config.json` dosyanız varsa:

### Manuel Geçiş

**Adım 1**: `config.json` dosyanızı açın

**Adım 2**: Yeni bir `config.yaml` dosyası oluşturun

**Adım 3**: Değerleri aşağıdaki formata çevirin

**JSON (Eski):**
```json
{
  "input_queue_size": 1000,
  "output_queue_size": 10000,
  "cpu_bound_count": 3,
  "io_bound_count": null,
  "log_level": "INFO"
}
```

**YAML (Yeni):**
```yaml
input_queue_size: 1000
output_queue_size: 10000
cpu_bound_count: 3
io_bound_count: null
log_level: INFO
```

### Otomatik Şablon Oluşturma

```bash
python -m axion.main --create-config
# config.yaml varsayılan değerlerle oluşturulur
```

Bu komut varsayılan değerlerle `config.yaml` oluşturur. Eski ayarlarınızı elle ekleyin.

### Syntax Farklılıkları

| Özellik | JSON | YAML |
|---------|------|------|
| **Tırnak işareti** | Zorunlu: `"INFO"` | İsteğe bağlı: `INFO` veya `"INFO"` |
| **Boolean** | `true`, `false` | `true`, `false` (küçük harf) |
| **Null** | `null` | `null` |
| **Sayı** | `1000` | `1000` |
| **Liste** | `[1, 2, 3]` | `[1, 2, 3]` veya satır satır |
| **Yorum** | Yok | `# Yorum satırı` |
| **İç içe** | `{"key": {"nested": "value"}}` | `key:\n  nested: value` |

### Dikkat Edilmesi Gerekenler

- ✅ `null` değerleri JSON'daki gibi kalır (örn: `io_bound_count: null`)
- ✅ String değerler tırnak işareti olmadan yazılabilir (örn: `log_level: INFO`)
- ✅ Boolean değerler küçük harfle yazılır (örn: `enabled: true`)
- ✅ YAML indentation (girinti) önemlidir, tab yerine space kullanın
- ✅ Yorum satırları ekleyebilirsiniz (`# Yorum`)
- ❌ JSON formatı artık desteklenmez, YAML kullanın

### Yeni Eklenen Parametreler (v3.0+)

Eski JSON config'inizde bu parametreler yoktu, YAML'a ekleyin:

```yaml
cpu_isolation:
  enabled: false
  backend: auto
  profile: balanced
  # ... (11 parametre daha, yukarıda detaylı açıklandı)
```

Varsayılan değerler kullanılacak, özelleştirme isteğe bağlıdır.

---

## Python API Kullanımı

### Config Yükleme

```python
from axion import EngineConfig

# Varsayılan config (./config.yaml veya paket varsayılanı)
config = EngineConfig.load()

# Özel config dosyası
config = EngineConfig.load("configs/production.yaml")

# Dict'ten yükleme
config_dict = {
    "cpu_bound_count": 4,
    "io_bound_count": 8,
    "log_level": "DEBUG"
}
config = EngineConfig.from_dict(config_dict)
```

### CPU İzolasyon ile Config

```python
from axion import Engine, EngineConfig
from axion.config import CpuIsolationConfig

# Yöntem 1: YAML'dan yükle
config = EngineConfig.load("config.yaml")

# Yöntem 2: Programatik oluştur
isolation_config = CpuIsolationConfig(
    enabled=True,
    profile="balanced",
    backend="auto"
)

config = EngineConfig(
    cpu_bound_count=4,
    io_bound_count=8,
    cpu_isolation=isolation_config
)

# Engine ile kullan
with Engine(config=config) as engine:
    # İzolasyonlu engine çalışıyor
    pass
```

### Config Validasyonu

```python
from axion import EngineConfig

try:
    config = EngineConfig.load("invalid_config.yaml")
except ValueError as e:
    print(f"Config hatası: {e}")
    # Örnek: "cpu_bound_count 1'den küçük olamaz"
```

---

## İlgili Dokümantasyon

- [CPU İzolasyon Rehberi](../docs/cpu_isolation.md) - CPU izolasyonu detayları, profiller, backend'ler
- [Mimari Dokümantasyon](../docs/architecture.md) - Sistem mimarisi, izolasyon entegrasyonu
- [Module Overview](../docs/module_overview.md) - Config modülü yapısı
- [Main README](../README.md) - Genel kullanım ve örnekler


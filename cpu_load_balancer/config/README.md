# Config Klasörü

Bu klasör, CPU Load Balancer'ın yapılandırma dosyalarını içerir.

## Dosyalar

- `config.json` - Varsayılan yapılandırma dosyası
- `__init__.py` - EngineConfig sınıfı tanımı

## Config Dosyası Formatı

```json
{
  "input_queue_size": 1000,
  "output_queue_size": 10000,
  "cpu_bound_count": 1,
  "io_bound_count": null,
  "cpu_bound_task_limit": 1,
  "io_bound_task_limit": 20,
  "log_level": "INFO",
  "queue_poll_timeout": 1.0
}
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

## Kullanım

### Varsayılan Config ile
```bash
python -m cpu_load_balancer.main
```

### Özel Config ile
```bash
python -m cpu_load_balancer.main --config cpu_load_balancer/config/my_config.json
```

### Varsayılan Config Oluştur
```bash
python -m cpu_load_balancer.main --create-config
```

## Örnek Config Dosyaları

Farklı senaryolar için özel config dosyaları oluşturabilirsiniz:

- `config.production.json` - Production ortamı için
- `config.development.json` - Development ortamı için
- `config.test.json` - Test ortamı için


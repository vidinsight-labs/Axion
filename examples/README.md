# Examples - Kullanım Örnekleri

Bu klasör, CPU Load Balancer'ın farklı kullanım senaryolarını gösteren örnekleri içerir.

## Dosyalar

### Basit Örnekler
- **`simple_example.py`** - Temel kullanım örneği
  - Engine oluşturma ve başlatma
  - Tek bir görev gönderme
  - Sonuç alma

- **`simple_task.py`** - Basit görev script'i
  - CPU Load Balancer'ın çalıştırabileceği örnek script
  - `main(params, context)` fonksiyonu içerir

### Gelişmiş Örnekler
- **`advanced_example.py`** - Gelişmiş kullanım örneği
  - Özel config ile engine oluşturma
  - Birden fazla görev gönderme (CPU-bound ve IO-bound)
  - Batch işlemler
  - Durum takibi ve istatistikler

## Kullanım

### Basit Örnek
```bash
cd examples
python3 simple_example.py
```

### Gelişmiş Örnek
```bash
cd examples
python3 advanced_example.py
```

## Script Formatı

CPU Load Balancer'ın çalıştırabileceği script'ler şu formatta olmalıdır:

```python
def main(params: dict, context) -> dict:
    """
    Ana fonksiyon
    
    Args:
        params: Görev parametreleri (dict)
        context: Execution context (task_id, worker_id içerir)
    
    Returns:
        dict: Sonuç verisi
    """
    # İşlemleriniz burada
    return {"result": "success", "data": ...}
```

## Örnek Senaryolar

### 1. Basit Hesaplama
```python
def main(params, context):
    value = params.get("value", 0)
    result = value * 2
    return {"result": result}
```

### 2. CPU-Bound İşlem
```python
def main(params, context):
    n = params.get("n", 1000)
    result = sum(i * i for i in range(n))
    return {"result": result}
```

### 3. IO-Bound İşlem
```python
def main(params, context):
    import time
    delay = params.get("delay", 0.1)
    time.sleep(delay)  # Network/IO simülasyonu
    return {"status": "completed"}
```

## Notlar

- Tüm script'ler `main(params, context)` fonksiyonu içermelidir
- Script'ler Python 3.8+ ile uyumludur
- Context objesi `task_id` ve `worker_id` içerir
- Script'ler hata fırlatırsa, görev başarısız olarak işaretlenir


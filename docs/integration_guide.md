# Axion - Entegrasyon ve Gerçek Hayat Kullanım Rehberi

**Axion v3.0** - Pratik Kullanım Senaryoları ve Entegrasyon Örnekleri

Bu dokümantasyon, Axion'u kendi projelerinize nasıl entegre edeceğinizi ve gerçek hayat senaryolarında nasıl kullanacağınızı gösterir.

## 📑 İçindekiler

1. [Hızlı Entegrasyon](#hızlı-entegrasyon)
2. [Gerçek Hayat Senaryoları](#gerçek-hayat-senaryoları)
3. [Best Practices](#best-practices)
4. [Yaygın Kullanım Desenleri](#yaygın-kullanım-desenleri)
5. [Performans Optimizasyonu](#performans-optimizasyonu)
6. [Sorun Giderme](#sorun-giderme)

---

## 🚀 Hızlı Entegrasyon

### Adım 1: Axion'u Projenize Ekleyin

**Seçenek 1: Direkt Kopyalama (En Basit)**

```bash
# Axion klasörünü projenize kopyalayın
cp -r /path/to/Axion/axion /your/project/

# Veya git submodule olarak ekleyin
git submodule add https://github.com/your-repo/axion.git axion
```

**Seçenek 2: Python Path'e Ekleme**

```python
import sys
from pathlib import Path

# Axion'u path'e ekle
axion_path = Path("/path/to/Axion")
sys.path.insert(0, str(axion_path))

from axion import Engine, Task, TaskType
```

**Seçenek 3: Package Olarak Kurulum (Gelecekte)**

```bash
pip install axion
```

### Adım 2: İlk Kullanım

```python
# my_project/main.py
from axion import Engine, Task, TaskType

# Engine başlat
with Engine() as engine:
    # Görev oluştur
    task = Task.create(
        script_path="tasks/my_task.py",
        params={"input": "data"},
        task_type=TaskType.IO_BOUND
    )
    
    # Görevi gönder
    task_id = engine.submit_task(task)
    
    # Sonucu al
    result = engine.get_result(task_id, timeout=30)
    
    if result and result.is_success:
        print(f"Sonuç: {result.data}")
```

### Adım 3: Task Script'inizi Oluşturun

```python
# tasks/my_task.py
def main(params, context):
    """
    Gerçek iş mantığınız burada
    
    Args:
        params: Görev parametreleri
        context: Execution context (task_id, worker_id)
    
    Returns:
        dict: İşlem sonucu
    """
    input_data = params.get("input")
    
    # İş mantığınız
    processed = process_data(input_data)
    
    return {
        "result": processed,
        "status": "success",
        "task_id": context.task_id
    }
```

---

## 💼 Gerçek Hayat Senaryoları

### Senaryo 1: Web Scraping Pipeline

**Problem:** 1000 URL'den veri çekmek gerekiyor

**Çözüm:**

```python
# web_scraper.py
from axion import Engine, Task, TaskType
from pathlib import Path

def scrape_urls(urls: list[str]) -> list[dict]:
    """
    1000 URL'den veri çeker
    
    Args:
        urls: URL listesi
    
    Returns:
        list: Scrape edilmiş veriler
    """
    script_path = str(Path(__file__).parent / "tasks" / "scrape_task.py")
    
    with Engine() as engine:
        # Tüm URL'ler için görev oluştur
        task_ids = []
        for url in urls:
            task = Task.create(
                script_path=script_path,
                params={"url": url},
                task_type=TaskType.IO_BOUND  # Network I/O
            )
            task_id = engine.submit_task(task)
            task_ids.append((url, task_id))
        
        # Sonuçları topla
        results = []
        for url, task_id in task_ids:
            result = engine.get_result(task_id, timeout=60)
            if result and result.is_success:
                results.append({
                    "url": url,
                    "data": result.data
                })
        
        return results

# tasks/scrape_task.py
def main(params, context):
    import requests
    
    url = params["url"]
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        return {
            "url": url,
            "status_code": response.status_code,
            "content": response.text[:1000],  # İlk 1000 karakter
            "success": True
        }
    except Exception as e:
        return {
            "url": url,
            "error": str(e),
            "success": False
        }
```

**Kullanım:**

```python
urls = [
    "https://example.com/page1",
    "https://example.com/page2",
    # ... 1000 URL
]

scraped_data = scrape_urls(urls)
print(f"✅ {len(scraped_data)} URL başarıyla scrape edildi")
```

### Senaryo 2: Image Processing Pipeline

**Problem:** 500 görüntüyü resize, crop ve filter uygulamak gerekiyor

**Çözüm:**

```python
# image_processor.py
from axion import Engine, Task, TaskType
from pathlib import Path

def process_images(image_paths: list[str], operations: dict) -> list[dict]:
    """
    Görüntüleri paralel işler
    
    Args:
        image_paths: Görüntü dosya yolları
        operations: İşlem parametreleri (resize, crop, filter)
    
    Returns:
        list: İşlenmiş görüntü bilgileri
    """
    script_path = str(Path(__file__).parent / "tasks" / "image_task.py")
    
    config = EngineConfig(
        cpu_bound_count=4,  # Görüntü işleme CPU-intensive
        cpu_bound_task_limit=1
    )
    
    with Engine(config) as engine:
        task_ids = []
        for img_path in image_paths:
            task = Task.create(
                script_path=script_path,
                params={
                    "image_path": img_path,
                    "operations": operations
                },
                task_type=TaskType.CPU_BOUND
            )
            task_id = engine.submit_task(task)
            task_ids.append((img_path, task_id))
        
        results = []
        for img_path, task_id in task_ids:
            result = engine.get_result(task_id, timeout=120)
            if result and result.is_success:
                results.append(result.data)
        
        return results

# tasks/image_task.py
def main(params, context):
    from PIL import Image
    
    image_path = params["image_path"]
    operations = params["operations"]
    
    try:
        # Görüntüyü yükle
        img = Image.open(image_path)
        
        # İşlemleri uygula
        if operations.get("resize"):
            width, height = operations["resize"]
            img = img.resize((width, height))
        
        if operations.get("crop"):
            box = operations["crop"]
            img = img.crop(box)
        
        if operations.get("filter"):
            filter_type = operations["filter"]
            img = img.filter(filter_type)
        
        # Kaydet
        output_path = f"processed_{Path(image_path).name}"
        img.save(output_path)
        
        return {
            "original": image_path,
            "processed": output_path,
            "size": img.size,
            "success": True
        }
    except Exception as e:
        return {
            "original": image_path,
            "error": str(e),
            "success": False
        }
```

**Kullanım:**

```python
image_paths = ["img1.jpg", "img2.jpg", ...]  # 500 görüntü

operations = {
    "resize": (800, 600),
    "crop": (100, 100, 700, 500),
    "filter": "BLUR"
}

processed = process_images(image_paths, operations)
print(f"✅ {len(processed)} görüntü işlendi")
```

### Senaryo 3: Data Pipeline (ETL)

**Problem:** Veritabanından veri çek → İşle → API'ye gönder

**Çözüm:**

```python
# data_pipeline.py
from axion import Engine, Task, TaskType
from pathlib import Path

def run_etl_pipeline(config: dict):
    """
    ETL Pipeline: Extract → Transform → Load
    
    Args:
        config: Pipeline konfigürasyonu
    """
    extract_script = str(Path(__file__).parent / "tasks" / "extract_task.py")
    transform_script = str(Path(__file__).parent / "tasks" / "transform_task.py")
    load_script = str(Path(__file__).parent / "tasks" / "load_task.py")
    
    with Engine() as engine:
        # Extract: Veritabanından veri çek
        extract_task = Task.create(
            script_path=extract_script,
            params={
                "db_config": config["database"],
                "query": config["query"]
            },
            task_type=TaskType.IO_BOUND
        )
        
        # Transform: Veriyi işle (Extract'a bağımlı)
        transform_task = Task.create(
            script_path=transform_script,
            params={
                "transform_rules": config["transform_rules"]
            },
            task_type=TaskType.CPU_BOUND,
            dependencies=[extract_task.id]
        )
        
        # Load: API'ye gönder (Transform'a bağımlı)
        load_task = Task.create(
            script_path=load_script,
            params={
                "api_config": config["api"]
            },
            task_type=TaskType.IO_BOUND,
            dependencies=[transform_task.id]
        )
        
        # Workflow gönder
        task_ids = engine.submit_workflow([extract_task, transform_task, load_task])
        
        # Son sonucu bekle (Load)
        result = engine.get_result(load_task.id, timeout=300)
        
        if result and result.is_success:
            print("✅ ETL Pipeline başarıyla tamamlandı")
            return result.data
        else:
            print("❌ ETL Pipeline başarısız")
            return None

# tasks/extract_task.py
def main(params, context):
    import sqlite3
    
    db_config = params["db_config"]
    query = params["query"]
    
    conn = sqlite3.connect(db_config["path"])
    cursor = conn.cursor()
    cursor.execute(query)
    data = cursor.fetchall()
    conn.close()
    
    return {
        "data": data,
        "count": len(data)
    }

# tasks/transform_task.py
def main(params, context):
    # Upstream result'u al (Extract'tan)
    upstream = params.get("upstream_results", {})
    extract_task_id = list(upstream.keys())[0]
    raw_data = upstream[extract_task_id]["data"]
    
    # Transform kurallarını uygula
    transform_rules = params["transform_rules"]
    transformed = []
    
    for row in raw_data:
        # Transform işlemleri
        processed_row = apply_rules(row, transform_rules)
        transformed.append(processed_row)
    
    return {
        "data": transformed,
        "count": len(transformed)
    }

# tasks/load_task.py
def main(params, context):
    import requests
    
    # Upstream result'u al (Transform'tan)
    upstream = params.get("upstream_results", {})
    transform_task_id = list(upstream.keys())[0]
    transformed_data = upstream[transform_task_id]["data"]
    
    # API'ye gönder
    api_config = params["api_config"]
    response = requests.post(
        api_config["url"],
        json={"data": transformed_data},
        headers=api_config.get("headers", {})
    )
    
    return {
        "status_code": response.status_code,
        "sent_count": len(transformed_data),
        "success": response.status_code == 200
    }
```

**Kullanım:**

```python
config = {
    "database": {
        "path": "data.db"
    },
    "query": "SELECT * FROM users",
    "transform_rules": {
        "clean": True,
        "normalize": True
    },
    "api": {
        "url": "https://api.example.com/upload",
        "headers": {"Authorization": "Bearer token"}
    }
}

result = run_etl_pipeline(config)
```

### Senaryo 4: Batch Data Processing

**Problem:** Büyük CSV dosyasını parçalara bölüp paralel işlemek

**Çözüm:**

```python
# batch_processor.py
from axion import Engine, Task, TaskType
from pathlib import Path
import pandas as pd

def process_large_csv(csv_path: str, chunk_size: int = 1000) -> list[dict]:
    """
    Büyük CSV'yi parçalara bölüp paralel işler
    
    Args:
        csv_path: CSV dosya yolu
        chunk_size: Her chunk'ta kaç satır
    
    Returns:
        list: İşlenmiş chunk sonuçları
    """
    script_path = str(Path(__file__).parent / "tasks" / "process_chunk.py")
    
    # CSV'yi oku ve chunk'lara böl
    df = pd.read_csv(csv_path)
    chunks = [df[i:i+chunk_size] for i in range(0, len(df), chunk_size)]
    
    print(f"📊 {len(df)} satır, {len(chunks)} chunk'a bölündü")
    
    with Engine() as engine:
        # Her chunk için görev oluştur
        task_ids = []
        for i, chunk in enumerate(chunks):
            task = Task.create(
                script_path=script_path,
                params={
                    "chunk_id": i,
                    "chunk_data": chunk.to_dict("records"),  # JSON serializable
                    "operations": ["clean", "validate", "aggregate"]
                },
                task_type=TaskType.CPU_BOUND
            )
            task_id = engine.submit_task(task)
            task_ids.append((i, task_id))
        
        # Sonuçları topla
        results = []
        for chunk_id, task_id in task_ids:
            result = engine.get_result(task_id, timeout=120)
            if result and result.is_success:
                results.append(result.data)
        
        return results

# tasks/process_chunk.py
def main(params, context):
    import pandas as pd
    
    chunk_id = params["chunk_id"]
    chunk_data = params["chunk_data"]
    operations = params["operations"]
    
    # DataFrame'e dönüştür
    df = pd.DataFrame(chunk_data)
    
    # İşlemleri uygula
    if "clean" in operations:
        df = df.dropna()
    
    if "validate" in operations:
        # Validasyon kuralları
        df = df[df["value"] > 0]  # Örnek
    
    if "aggregate" in operations:
        aggregated = df.groupby("category").sum()
        return {
            "chunk_id": chunk_id,
            "aggregated": aggregated.to_dict(),
            "row_count": len(df)
        }
    
    return {
        "chunk_id": chunk_id,
        "row_count": len(df)
    }
```

**Kullanım:**

```python
results = process_large_csv("large_data.csv", chunk_size=1000)
print(f"✅ {len(results)} chunk işlendi")
```

---

## 🎯 Best Practices

### 1. Engine Lifecycle Yönetimi

**✅ DOĞRU:**

```python
# Context manager kullan (otomatik cleanup)
with Engine() as engine:
    # İşlemler
    pass
# Engine otomatik kapanır
```

**❌ YANLIŞ:**

```python
# Manuel cleanup unutulabilir
engine = Engine()
engine.start()
# ... işlemler
# engine.shutdown() unutuldu! ❌
```

### 2. Task Type Seçimi

**CPU-Bound İşler:**
- ✅ Matrix operations
- ✅ Image processing
- ✅ Data transformations
- ✅ Mathematical calculations

```python
task = Task.create(
    script_path="matrix_multiply.py",
    params={"size": 1000},
    task_type=TaskType.CPU_BOUND  # ✅ Doğru
)
```

**IO-Bound İşler:**
- ✅ File I/O
- ✅ Network requests
- ✅ Database queries
- ✅ API calls

```python
task = Task.create(
    script_path="api_call.py",
    params={"url": "https://api.example.com"},
    task_type=TaskType.IO_BOUND  # ✅ Doğru
)
```

### 3. Error Handling

**✅ DOĞRU:**

```python
with Engine() as engine:
    task_id = engine.submit_task(task)
    
    result = engine.get_result(task_id, timeout=30)
    
    if result:
        if result.is_success:
            # Başarılı
            process_result(result.data)
        else:
            # Hata var
            handle_error(result.error)
            # Retry logic
            retry_task(task)
    else:
        # Timeout
        handle_timeout(task_id)
```

### 4. Batch İşlemler

**✅ DOĞRU:**

```python
# Tüm görevleri önce gönder
task_ids = []
for item in items:
    task = Task.create(...)
    task_id = engine.submit_task(task)
    task_ids.append(task_id)

# Sonra sonuçları topla
results = []
for task_id in task_ids:
    result = engine.get_result(task_id, timeout=60)
    if result and result.is_success:
        results.append(result.data)
```

**❌ YANLIŞ:**

```python
# Her görevi gönderip hemen sonucu bekle (yavaş!)
for item in items:
    task = Task.create(...)
    task_id = engine.submit_task(task)
    result = engine.get_result(task_id)  # ❌ Sıralı işleme
    process(result)
```

### 5. Config Optimizasyonu

**CPU-Intensive Workload:**

```python
config = EngineConfig(
    cpu_bound_count=multiprocessing.cpu_count(),
    cpu_bound_task_limit=1,  # GIL nedeniyle
    io_bound_count=2  # Az sayıda
)
```

**IO-Intensive Workload:**

```python
config = EngineConfig(
    cpu_bound_count=2,  # Az sayıda
    io_bound_count=multiprocessing.cpu_count() * 3,
    io_bound_task_limit=50  # Yüksek thread limiti
)
```

**Mixed Workload:**

```python
config = EngineConfig(
    cpu_bound_count=4,
    io_bound_count=12,
    cpu_bound_task_limit=1,
    io_bound_task_limit=20
)
# Auto-scaling bu dengeyi optimize eder
```

---

## 🔧 Yaygın Kullanım Desenleri

### Desen 1: Service Wrapper

```python
# services/task_service.py
from axion import Engine, Task, TaskType
from pathlib import Path
from typing import Optional

class TaskService:
    """Axion'u sarmalayan service sınıfı"""
    
    def __init__(self):
        self.engine = None
        self.script_base_path = Path(__file__).parent.parent / "tasks"
    
    def start(self):
        """Service'i başlat"""
        self.engine = Engine()
        self.engine.start()
    
    def stop(self):
        """Service'i durdur"""
        if self.engine:
            self.engine.shutdown()
            self.engine = None
    
    def process_item(self, item: dict) -> Optional[dict]:
        """Tek bir item işle"""
        task = Task.create(
            script_path=str(self.script_base_path / "process_item.py"),
            params={"item": item},
            task_type=TaskType.IO_BOUND
        )
        
        task_id = self.engine.submit_task(task)
        result = self.engine.get_result(task_id, timeout=30)
        
        if result and result.is_success:
            return result.data
        return None
    
    def process_batch(self, items: list[dict]) -> list[dict]:
        """Batch item işle"""
        task_ids = []
        for item in items:
            task = Task.create(
                script_path=str(self.script_base_path / "process_item.py"),
                params={"item": item},
                task_type=TaskType.IO_BOUND
            )
            task_id = self.engine.submit_task(task)
            task_ids.append(task_id)
        
        results = []
        for task_id in task_ids:
            result = self.engine.get_result(task_id, timeout=60)
            if result and result.is_success:
                results.append(result.data)
        
        return results

# Kullanım
service = TaskService()
service.start()

try:
    result = service.process_item({"id": 1, "data": "test"})
    print(f"Sonuç: {result}")
finally:
    service.stop()
```

### Desen 2: Async Wrapper

```python
# async_task_runner.py
import asyncio
from axion import Engine, Task, TaskType
from concurrent.futures import ThreadPoolExecutor

class AsyncTaskRunner:
    """Axion'u async/await ile kullanmak için wrapper"""
    
    def __init__(self):
        self.engine = Engine()
        self.engine.start()
        self.executor = ThreadPoolExecutor(max_workers=1)
    
    async def submit_task_async(self, task: Task) -> str:
        """Async olarak görev gönder"""
        loop = asyncio.get_event_loop()
        task_id = await loop.run_in_executor(
            self.executor,
            self.engine.submit_task,
            task
        )
        return task_id
    
    async def get_result_async(self, task_id: str, timeout: float = 30) -> dict:
        """Async olarak sonuç al"""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.executor,
            lambda: self.engine.get_result(task_id, timeout)
        )
        return result
    
    async def process_item_async(self, item: dict) -> dict:
        """Async item işleme"""
        task = Task.create(
            script_path="tasks/process.py",
            params={"item": item},
            task_type=TaskType.IO_BOUND
        )
        
        task_id = await self.submit_task_async(task)
        result = await self.get_result_async(task_id)
        
        return result.data if result and result.is_success else None
    
    def shutdown(self):
        """Kapat"""
        self.engine.shutdown()
        self.executor.shutdown()

# Kullanım
async def main():
    runner = AsyncTaskRunner()
    
    try:
        # Async olarak işle
        result = await runner.process_item_async({"id": 1})
        print(f"Sonuç: {result}")
        
        # Batch async işleme
        items = [{"id": i} for i in range(100)]
        tasks = [runner.process_item_async(item) for item in items]
        results = await asyncio.gather(*tasks)
        print(f"✅ {len(results)} item işlendi")
    finally:
        runner.shutdown()

asyncio.run(main())
```

### Desen 3: Flask/FastAPI Integration

```python
# app.py (Flask örneği)
from flask import Flask, request, jsonify
from axion import Engine, Task, TaskType
from pathlib import Path

app = Flask(__name__)

# Global engine instance
engine = None

@app.before_first_request
def init_engine():
    """Uygulama başlarken engine'i başlat"""
    global engine
    engine = Engine()
    engine.start()

@app.teardown_appcontext
def close_engine(error):
    """Uygulama kapanırken engine'i kapat"""
    global engine
    if engine:
        engine.shutdown()

@app.route("/api/process", methods=["POST"])
def process_data():
    """Veri işleme endpoint'i"""
    data = request.json
    
    task = Task.create(
        script_path=str(Path(__file__).parent / "tasks" / "process.py"),
        params={"data": data},
        task_type=TaskType.CPU_BOUND
    )
    
    task_id = engine.submit_task(task)
    
    return jsonify({
        "task_id": task_id,
        "status": "submitted"
    })

@app.route("/api/result/<task_id>", methods=["GET"])
def get_result(task_id):
    """Sonuç alma endpoint'i"""
    result = engine.get_result(task_id, timeout=30)
    
    if result:
        if result.is_success:
            return jsonify({
                "status": "completed",
                "data": result.data
            })
        else:
            return jsonify({
                "status": "failed",
                "error": result.error
            }), 500
    else:
        return jsonify({
            "status": "pending"
        }), 202

if __name__ == "__main__":
    app.run()
```

**FastAPI Örneği:**

```python
# app.py (FastAPI)
from fastapi import FastAPI, BackgroundTasks
from axion import Engine, Task, TaskType
from pydantic import BaseModel
from pathlib import Path

app = FastAPI()
engine = Engine()
engine.start()

class ProcessRequest(BaseModel):
    data: dict

@app.post("/api/process")
async def process_data(request: ProcessRequest, background: BackgroundTasks):
    """Veri işleme endpoint'i"""
    task = Task.create(
        script_path="tasks/process.py",
        params={"data": request.data},
        task_type=TaskType.CPU_BOUND
    )
    
    task_id = engine.submit_task(task)
    
    return {
        "task_id": task_id,
        "status": "submitted"
    }

@app.get("/api/result/{task_id}")
async def get_result(task_id: str):
    """Sonuç alma endpoint'i"""
    result = engine.get_result(task_id, timeout=30)
    
    if result:
        if result.is_success:
            return {
                "status": "completed",
                "data": result.data
            }
        else:
            return {
                "status": "failed",
                "error": result.error
            }
    else:
        return {
            "status": "pending"
        }

@app.on_event("shutdown")
async def shutdown():
    """Uygulama kapanırken"""
    engine.shutdown()
```

### Desen 4: Celery Alternative

**Axion ile Celery benzeri kullanım:**

```python
# task_queue.py
from axion import Engine, Task, TaskType
from pathlib import Path
from typing import Callable, Any
import functools

class AxionTaskQueue:
    """Celery benzeri task queue"""
    
    def __init__(self):
        self.engine = Engine()
        self.engine.start()
        self.task_registry = {}
    
    def task(self, script_path: str, task_type: TaskType = TaskType.IO_BOUND):
        """Task decorator"""
        def decorator(func):
            # Script'i oluştur
            self._create_task_script(func, script_path)
            
            # Registry'ye ekle
            self.task_registry[func.__name__] = {
                "script_path": script_path,
                "task_type": task_type
            }
            
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Task oluştur ve gönder
                task = Task.create(
                    script_path=script_path,
                    params={"args": args, "kwargs": kwargs},
                    task_type=task_type
                )
                return self.engine.submit_task(task)
            
            return wrapper
        return decorator
    
    def _create_task_script(self, func: Callable, script_path: str):
        """Function'dan task script oluştur"""
        # Script'i dinamik olarak oluştur
        script_content = f"""
def main(params, context):
    # Function'ı çağır
    import {func.__module__}
    func = {func.__module__}.{func.__name__}
    
    args = params.get("args", [])
    kwargs = params.get("kwargs", {{}})
    
    result = func(*args, **kwargs)
    return {{"result": result}}
"""
        Path(script_path).parent.mkdir(parents=True, exist_ok=True)
        Path(script_path).write_text(script_content)
    
    def get_result(self, task_id: str, timeout: float = 30):
        """Sonuç al"""
        result = self.engine.get_result(task_id, timeout)
        if result and result.is_success:
            return result.data.get("result")
        return None

# Kullanım
queue = AxionTaskQueue()

@queue.task("tasks/my_task.py", TaskType.CPU_BOUND)
def process_data(data: dict) -> dict:
    """İş mantığı"""
    # Process data
    return {"processed": True}

# Görev gönder
task_id = process_data({"input": "data"})

# Sonuç al
result = queue.get_result(task_id)
```

---

## ⚡ Performans Optimizasyonu

### 1. Script Caching

Axion otomatik olarak script'leri cache'ler, ama siz de optimize edebilirsiniz:

```python
# Script'i bir kez yükle ve cache'le
import importlib.util

def load_script_once(script_path: str):
    """Script'i bir kez yükle"""
    spec = importlib.util.spec_from_file_location("task_module", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Kullanım: Script'i önceden yükle
module = load_script_once("tasks/my_task.py")
# Axion aynı script'i tekrar yüklediğinde cache'den gelecek
```

### 2. Batch Size Optimizasyonu

```python
# Optimal batch size bulma
def find_optimal_batch_size(items: list, test_sizes: list[int] = [10, 50, 100, 500, 1000]):
    """Optimal batch size'ı bul"""
    best_size = 10
    best_time = float('inf')
    
    for batch_size in test_sizes:
        start = time.time()
        process_batch(items[:batch_size])
        elapsed = time.time() - start
        
        if elapsed < best_time:
            best_time = elapsed
            best_size = batch_size
    
    return best_size
```

### 3. Timeout Ayarlama

```python
# Görev tipine göre timeout
def get_timeout_for_task(task_type: TaskType, task_params: dict) -> float:
    """Görev tipine göre timeout hesapla"""
    if task_type == TaskType.CPU_BOUND:
        # CPU işleri genelde tahmin edilebilir
        complexity = task_params.get("complexity", 1)
        return 30.0 * complexity
    else:
        # IO işleri network'e bağlı
        return 60.0  # Daha uzun timeout
```

---

## 🛠️ Sorun Giderme

### Problem 1: Script Import Hatası

**Hata:**
```
ModuleNotFoundError: No module named 'tasks'
```

**Çözüm:**
```python
# Absolute path kullan
script_path = str(Path(__file__).parent / "tasks" / "my_task.py")

# Veya sys.path'e ekle
import sys
sys.path.insert(0, str(Path(__file__).parent))
```

### Problem 2: Pickle Hatası

**Hata:**
```
PicklingError: Can't pickle <function>
```

**Çözüm:**
```python
# Function'ları params'a gönderme, sadece data gönder
# ❌ YANLIŞ
task = Task.create(
    params={"func": my_function}  # ❌ Pickle edilemez
)

# ✅ DOĞRU
task = Task.create(
    params={"data": data, "operation": "process"}  # ✅ Sadece data
)
```

### Problem 3: Memory Kullanımı

**Problem:** Çok fazla memory kullanılıyor

**Çözüm:**
```python
# 1. Result cache'i temizle
# get_result() çağrıldıktan sonra sonuçlar otomatik temizlenir
# Ama büyük batch'lerde dikkatli olun

# 2. Worker sayısını sınırla
config = EngineConfig(
    cpu_bound_count=4,  # Max 4 worker
    io_bound_count=8    # Max 8 worker
)

# 3. Queue boyutlarını optimize et
config = EngineConfig(
    input_queue_size=1000,   # Daha küçük
    output_queue_size=5000    # Daha küçük
)
```

---

## 📚 Örnek Proje Yapısı

```
my_project/
├── main.py                 # Ana uygulama
├── config.py              # Config yönetimi
├── services/
│   ├── task_service.py    # Task service wrapper
│   └── data_service.py    # Data processing service
├── tasks/                  # Task script'leri
│   ├── process_data.py
│   ├── api_call.py
│   └── transform.py
├── utils/
│   └── helpers.py         # Yardımcı fonksiyonlar
└── requirements.txt
```

**main.py:**
```python
from services.task_service import TaskService
from config import get_config

def main():
    config = get_config()
    service = TaskService()
    service.start()
    
    try:
        # İş mantığınız
        results = service.process_batch(data_items)
        print(f"✅ {len(results)} item işlendi")
    finally:
        service.stop()

if __name__ == "__main__":
    main()
```

---

## 🎓 Özet

### Entegrasyon Adımları

1. ✅ **Axion'u projenize ekleyin** (kopyalama veya path)
2. ✅ **Task script'lerinizi oluşturun** (`main(params, context)` fonksiyonu)
3. ✅ **Engine'i başlatın** (context manager kullanın)
4. ✅ **Görevleri gönderin** (batch olarak)
5. ✅ **Sonuçları toplayın** (paralel olarak)

### Best Practices

- ✅ Context manager kullan (`with Engine()`)
- ✅ Doğru task type seç (CPU vs IO)
- ✅ Batch işlemler yap (gönder → topla)
- ✅ Error handling ekle
- ✅ Config'i optimize et

### Yaygın Desenler

- ✅ Service wrapper
- ✅ Async wrapper
- ✅ Web framework entegrasyonu
- ✅ Celery alternative

**Axion ile yüksek performanslı, scalable task execution sistemleri kurun!** 🚀

---

## 🔗 İlgili Dokümantasyon

- [Module Overview](./module_overview.md) - Genel bakış
- [Examples Guide](./examples_guide.md) - Kod örnekleri
- [Architecture](./architecture.md) - Mimari detayları


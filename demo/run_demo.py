#!/usr/bin/env python3
"""
Gerçek Hayat Demo - CPU Load Balancer

Bu script, gerçek dünya senaryolarını simüle eder:
1. Veri işleme görevleri (CPU-bound)
2. API çağrıları (IO-bound)
3. Görüntü işleme (CPU-bound)
4. Batch işlemler
"""

import sys
import os
import time
import multiprocessing
from pathlib import Path

# Multiprocessing için gerekli
if __name__ == '__main__':
    multiprocessing.set_start_method('spawn', force=True)

# Proje root'unu path'e ekle
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from cpu_load_balancer import Engine, EngineConfig, Task, TaskType


def main():
    """Ana demo fonksiyonu"""
    print("=" * 70)
    print("🚀 CPU LOAD BALANCER - GERÇEK HAYAT DEMO")
    print("=" * 70)
    
    # Script path'lerini hazırla
    demo_dir = Path(__file__).parent
    data_processor = str(demo_dir / "data_processor.py")
    api_client = str(demo_dir / "api_client.py")
    image_processor = str(demo_dir / "image_processor.py")
    
    # Script'lerin varlığını kontrol et
    if not all(os.path.exists(s) for s in [data_processor, api_client, image_processor]):
        print("❌ Demo script'leri bulunamadı!")
        return 1
    
    # Engine config - gerçekçi ayarlar
    config = EngineConfig(
        input_queue_size=5000,
        output_queue_size=10000,
        cpu_bound_count=2,  # CPU-bound görevler için 2 worker
        io_bound_count=6,   # IO-bound görevler için 6 worker
        cpu_bound_task_limit=1,
        io_bound_task_limit=15,
        log_level="INFO"
    )
    
    print(f"\n📊 Engine Yapılandırması:")
    print(f"   CPU-bound workers: {config.cpu_bound_count}")
    print(f"   IO-bound workers: {config.io_bound_count}")
    print(f"   Input queue: {config.input_queue_size}")
    print(f"   Output queue: {config.output_queue_size}")
    
    # Engine'i başlat
    print("\n🔧 Engine başlatılıyor...")
    engine = Engine(config)
    
    try:
        engine.start()
        print("✅ Engine başlatıldı!\n")
        
        # Durum göster
        status = engine.get_status()
        print("📊 Sistem Durumu:")
        print(f"   Engine: {'🟢 Çalışıyor' if status['engine']['is_running'] else '🔴 Durdu'}")
        for name, comp in status['components'].items():
            health = comp['health']
            metrics = comp['metrics']
            print(f"   {name}: {health} (size: {metrics.get('size', 0)})")
        
        # ============================================================
        # Senaryo 1: Veri İşleme (CPU-bound)
        # ============================================================
        print("\n" + "=" * 70)
        print("📊 SENARYO 1: Veri İşleme (CPU-bound)")
        print("=" * 70)
        
        tasks_cpu = []
        
        # Toplama işlemi
        task1 = Task.create(
            script_path=data_processor,
            params={"data": list(range(1, 101)), "operation": "sum"},
            task_type=TaskType.CPU_BOUND
        )
        tasks_cpu.append(("Toplama", task1))
        
        # Çarpma işlemi
        task2 = Task.create(
            script_path=data_processor,
            params={"data": list(range(1, 11)), "operation": "multiply"},
            task_type=TaskType.CPU_BOUND
        )
        tasks_cpu.append(("Çarpma", task2))
        
        # Filtreleme
        task3 = Task.create(
            script_path=data_processor,
            params={"data": list(range(1, 21)), "operation": "filter"},
            task_type=TaskType.CPU_BOUND
        )
        tasks_cpu.append(("Filtreleme", task3))
        
        # Görevleri gönder
        task_ids_cpu = {}
        for name, task in tasks_cpu:
            task_id = engine.submit_task(task)
            task_ids_cpu[task_id] = name
            print(f"   ✓ {name} görevi gönderildi: {task_id[:8]}...")
        
        # Sonuçları bekle
        print("\n   ⏳ Sonuçlar bekleniyor...")
        results_cpu = {}
        for task_id, name in task_ids_cpu.items():
            result = engine.get_result(task_id, timeout=30)
            if result and result.is_success:
                results_cpu[name] = result.data
                print(f"   ✅ {name}: {result.data.get('result', 'N/A')}")
            else:
                print(f"   ❌ {name}: Başarısız")
        
        # ============================================================
        # Senaryo 2: API Çağrıları (IO-bound)
        # ============================================================
        print("\n" + "=" * 70)
        print("🌐 SENARYO 2: API Çağrıları (IO-bound)")
        print("=" * 70)
        
        tasks_io = []
        
        # GET isteği
        task4 = Task.create(
            script_path=api_client,
            params={
                "endpoint": "https://api.example.com/users",
                "method": "GET",
                "timeout": 5.0
            },
            task_type=TaskType.IO_BOUND
        )
        tasks_io.append(("API GET", task4))
        
        # POST isteği
        task5 = Task.create(
            script_path=api_client,
            params={
                "endpoint": "https://api.example.com/users",
                "method": "POST",
                "payload": {"name": "John Doe", "email": "john@example.com"},
                "timeout": 5.0
            },
            task_type=TaskType.IO_BOUND
        )
        tasks_io.append(("API POST", task5))
        
        # Görevleri gönder
        task_ids_io = {}
        for name, task in tasks_io:
            task_id = engine.submit_task(task)
            task_ids_io[task_id] = name
            print(f"   ✓ {name} görevi gönderildi: {task_id[:8]}...")
        
        # Sonuçları bekle
        print("\n   ⏳ Sonuçlar bekleniyor...")
        results_io = {}
        for task_id, name in task_ids_io.items():
            result = engine.get_result(task_id, timeout=30)
            if result and result.is_success:
                results_io[name] = result.data
                response = result.data.get('response', {})
                if response.get('count') is not None:
                    print(f"   ✅ {name}: {response.get('status', 'N/A')} ({response.get('count')} items)")
                else:
                    print(f"   ✅ {name}: {response.get('status', 'N/A')}")
            elif result:
                print(f"   ❌ {name}: Başarısız - {result.error}")
            else:
                print(f"   ❌ {name}: Timeout - sonuç alınamadı")
        
        # ============================================================
        # Senaryo 3: Görüntü İşleme (CPU-bound)
        # ============================================================
        print("\n" + "=" * 70)
        print("🖼️  SENARYO 3: Görüntü İşleme (CPU-bound)")
        print("=" * 70)
        
        tasks_image = []
        
        # Görüntü işleme görevleri
        for i in range(3):
            task = Task.create(
                script_path=image_processor,
                params={
                    "image_path": f"photo_{i+1}.jpg",
                    "width": 1920,
                    "height": 1080,
                    "format": "jpg"
                },
                task_type=TaskType.CPU_BOUND
            )
            tasks_image.append((f"Görüntü {i+1}", task))
        
        # Görevleri gönder
        task_ids_image = {}
        for name, task in tasks_image:
            task_id = engine.submit_task(task)
            task_ids_image[task_id] = name
            print(f"   ✓ {name} görevi gönderildi: {task_id[:8]}...")
        
        # Sonuçları bekle
        print("\n   ⏳ Sonuçlar bekleniyor...")
        results_image = {}
        for task_id, name in task_ids_image.items():
            result = engine.get_result(task_id, timeout=30)
            if result and result.is_success:
                results_image[name] = result.data
                metadata = result.data.get('metadata', {})
                print(f"   ✅ {name}: {metadata.get('dimensions', {}).get('width')}x{metadata.get('dimensions', {}).get('height')}")
            else:
                print(f"   ❌ {name}: Başarısız")
        
        # ============================================================
        # Senaryo 4: Batch İşlemler (Karışık)
        # ============================================================
        print("\n" + "=" * 70)
        print("📦 SENARYO 4: Batch İşlemler (Karışık)")
        print("=" * 70)
        
        batch_tasks = []
        
        # Farklı tip görevler
        for i in range(5):
            if i % 2 == 0:
                # IO-bound: API çağrısı
                task = Task.create(
                    script_path=api_client,
                    params={"endpoint": f"https://api.example.com/data/{i}", "method": "GET"},
                    task_type=TaskType.IO_BOUND
                )
            else:
                # CPU-bound: Veri işleme
                task = Task.create(
                    script_path=data_processor,
                    params={"data": list(range(1, 20+i)), "operation": "sum"},
                    task_type=TaskType.CPU_BOUND
                )
            batch_tasks.append(task)
        
        # Tüm görevleri gönder
        batch_task_ids = []
        for task in batch_tasks:
            task_id = engine.submit_task(task)
            batch_task_ids.append(task_id)
        
        print(f"   ✓ {len(batch_tasks)} görev batch olarak gönderildi")
        
        # Sonuçları topla
        print("\n   ⏳ Sonuçlar bekleniyor...")
        batch_results = []
        batch_failed = []
        batch_timeout = []
        
        for task_id in batch_task_ids:
            result = engine.get_result(task_id, timeout=30)
            if result and result.is_success:
                batch_results.append(result)
            elif result:
                batch_failed.append((task_id[:8], result.error))
            else:
                batch_timeout.append(task_id[:8])
        
        print(f"   ✅ {len(batch_results)}/{len(batch_tasks)} görev başarıyla tamamlandı")
        if batch_failed:
            print(f"   ❌ {len(batch_failed)} görev başarısız")
        if batch_timeout:
            print(f"   ⏱️  {len(batch_timeout)} görev timeout")
        
        # ============================================================
        # Final Durum
        # ============================================================
        print("\n" + "=" * 70)
        print("📊 FİNAL DURUM")
        print("=" * 70)
        
        final_status = engine.get_status()
        
        print("\n📈 İstatistikler:")
        for name, comp in final_status['components'].items():
            metrics = comp['metrics']
            if name == "input_queue":
                print(f"   Input Queue: {metrics.get('total_put', 0)} görev gönderildi")
            elif name == "output_queue":
                print(f"   Output Queue: {metrics.get('total_put', 0)} sonuç alındı")
            elif name == "process_pool":
                print(f"   Process Pool: {metrics.get('total_workers', 0)} worker aktif")
        
        print("\n✅ Demo başarıyla tamamlandı!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Kullanıcı tarafından durduruldu")
    except Exception as e:
        print(f"\n❌ Hata: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        print("\n🛑 Engine kapatılıyor...")
        engine.shutdown()
        print("✅ Engine kapatıldı")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


#!/usr/bin/env python3
"""
Gelişmiş Kullanım Örneği - CPU Load Balancer

Bu örnek, CPU Load Balancer'ın gelişmiş özelliklerini gösterir:
- Özel config ile engine oluşturma
- Birden fazla görev gönderme (CPU-bound ve IO-bound)
- Batch işlemler
- Durum takibi
- Hata yönetimi
"""

import sys
import multiprocessing
import time
from pathlib import Path
from typing import List, Dict

# Multiprocessing için gerekli
if __name__ == '__main__':
    multiprocessing.set_start_method('spawn', force=True)

# Proje root'unu path'e ekle
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from cpu_load_balancer import Engine, EngineConfig, Task, TaskType, Result


def create_test_script(content: str, filename: str) -> Path:
    """Test script'i oluştur"""
    script_path = Path(__file__).parent / filename
    script_path.write_text(content)
    return script_path


def main():
    """Gelişmiş kullanım örneği"""
    print("=" * 70)
    print("GELİŞMİŞ KULLANIM ÖRNEĞİ")
    print("=" * 70)
    
    # 1. Özel Config oluştur
    config = EngineConfig(
        input_queue_size=5000,
        output_queue_size=10000,
        cpu_bound_count=2,
        io_bound_count=4,
        cpu_bound_task_limit=1,
        io_bound_task_limit=10,
        log_level="INFO"
    )
    
    print(f"\n📊 Özel Config:")
    print(f"   CPU-bound workers: {config.cpu_bound_count} (her biri {config.cpu_bound_task_limit} thread)")
    print(f"   IO-bound workers: {config.io_bound_count} (her biri {config.io_bound_task_limit} thread)")
    print(f"   Queue sizes: {config.input_queue_size}/{config.output_queue_size}")
    
    # 2. Test script'leri oluştur
    print("\n📝 Test script'leri oluşturuluyor...")
    
    cpu_task_script = create_test_script('''def main(params, context):
    """CPU-bound görev - hesaplama"""
    n = params.get("n", 1000)
    result = sum(i * i for i in range(n))
    return {"result": result, "n": n, "task_id": context.task_id}
''', "cpu_task.py")
    
    io_task_script = create_test_script('''def main(params, context):
    """IO-bound görev - simüle edilmiş network işlemi"""
    import time
    delay = params.get("delay", 0.1)
    time.sleep(delay)
    return {"status": "completed", "delay": delay, "task_id": context.task_id}
''', "io_task.py")
    
    print("✅ Script'ler oluşturuldu")
    
    # 3. Engine oluştur ve başlat
    print("\n🔧 Engine başlatılıyor...")
    engine = Engine(config)
    engine.start()
    print("✅ Engine başlatıldı")
    
    try:
        # 4. Durum göster
        status = engine.get_status()
        print(f"\n📊 Sistem Durumu:")
        print(f"   Engine: {'🟢 Çalışıyor' if status['engine']['is_running'] else '🔴 Durdu'}")
        for name, comp in status['components'].items():
            health = comp['health']
            print(f"   {name}: {health}")
        
        # 5. Birden fazla görev gönder (CPU-bound)
        print("\n" + "=" * 70)
        print("CPU-BOUND GÖREVLER")
        print("=" * 70)
        
        cpu_tasks: List[Task] = []
        for i in range(3):
            task = Task.create(
                script_path=str(cpu_task_script),
                params={"n": 1000 * (i + 1)},
                task_type=TaskType.CPU_BOUND
            )
            cpu_tasks.append(task)
            task_id = engine.submit_task(task)
            print(f"   ✓ Görev {i+1} gönderildi: {task_id[:8]}... (n={1000*(i+1)})")
        
        # 6. Birden fazla görev gönder (IO-bound)
        print("\n" + "=" * 70)
        print("IO-BOUND GÖREVLER")
        print("=" * 70)
        
        io_tasks: List[Task] = []
        for i in range(5):
            task = Task.create(
                script_path=str(io_task_script),
                params={"delay": 0.1 * (i + 1)},
                task_type=TaskType.IO_BOUND
            )
            io_tasks.append(task)
            task_id = engine.submit_task(task)
            print(f"   ✓ Görev {i+1} gönderildi: {task_id[:8]}... (delay={0.1*(i+1)}s)")
        
        # 7. Sonuçları topla
        print("\n" + "=" * 70)
        print("SONUÇLAR")
        print("=" * 70)
        
        all_results: Dict[str, Result] = {}
        
        # CPU-bound sonuçları
        print("\n📊 CPU-bound sonuçları:")
        for task in cpu_tasks:
            result = engine.get_result(task.id, timeout=30.0)
            if result:
                all_results[task.id] = result
                if result.is_success:
                    print(f"   ✅ {task.id[:8]}...: {result.data.get('result', 'N/A')}")
                else:
                    print(f"   ❌ {task.id[:8]}...: {result.error}")
        
        # IO-bound sonuçları
        print("\n🌐 IO-bound sonuçları:")
        for task in io_tasks:
            result = engine.get_result(task.id, timeout=30.0)
            if result:
                all_results[task.id] = result
                if result.is_success:
                    print(f"   ✅ {task.id[:8]}...: {result.data.get('status', 'N/A')}")
                else:
                    print(f"   ❌ {task.id[:8]}...: {result.error}")
        
        # 8. İstatistikler
        print("\n" + "=" * 70)
        print("İSTATİSTİKLER")
        print("=" * 70)
        
        successful = sum(1 for r in all_results.values() if r.is_success)
        failed = len(all_results) - successful
        
        print(f"\n📈 Özet:")
        print(f"   Toplam görev: {len(cpu_tasks) + len(io_tasks)}")
        print(f"   Başarılı: {successful}")
        print(f"   Başarısız: {failed}")
        
        # Final durum
        final_status = engine.get_status()
        print(f"\n📊 Final Durum:")
        for name, comp in final_status['components'].items():
            metrics = comp['metrics']
            if 'total_put' in metrics:
                print(f"   {name}: {metrics['total_put']} görev işlendi")
        
    except Exception as e:
        print(f"\n❌ Hata: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        # 9. Temizlik
        print("\n🧹 Temizlik yapılıyor...")
        try:
            cpu_task_script.unlink()
            io_task_script.unlink()
        except:
            pass
        
        # 10. Engine'i kapat
        print("🛑 Engine kapatılıyor...")
        engine.shutdown()
        print("✅ Engine kapatıldı")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


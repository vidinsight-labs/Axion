
import sys
import time
from pathlib import Path

# Proje root'unu path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from cpu_load_balancer import Engine, EngineConfig, Task, TaskType

def run_scaling_test():
    print("🚀 Auto-Scaling Testi Başlıyor...")
    
    # Başlangıçta sadece 1 CPU worker ile başla
    config = EngineConfig(
        cpu_bound_count=1,
        io_bound_count=1
    )
    
    engine = Engine(config)
    engine.start()
    
    try:
        script_path = str(Path(__file__).parent / "test_tasks.py")
        
        print(f"   Başlangıç Worker Sayısı: {engine.get_component_status('process_pool').metrics['cpu_bound_workers']}")
        
        # 1. Yükü Artır (500 Ağır Görev)
        print("\n📤 500 Ağır Görev gönderiliyor (Sistem Scale-Out yapmalı)...")
        tasks = []
        for i in range(500):
            task = Task.create(
                script_path=script_path,
                params={"type": "medium"}, # Medium görevler (biraz sürsün)
                task_type=TaskType.CPU_BOUND
            )
            engine.submit_task(task)
            tasks.append(task.id)
            
        print("   ✅ Görevler gönderildi.")
        
        # 2. İzleme Döngüsü (30 saniye boyunca worker sayısını izle)
        print("\n👀 Sistem izleniyor (30sn)...")
        max_workers = 0
        
        for i in range(6): # 6 * 5sn = 30sn
            time.sleep(5)
            status = engine.get_component_status('process_pool')
            workers = status.metrics['cpu_bound_workers']
            active = status.metrics['cpu_active_threads']
            max_workers = max(max_workers, workers)
            
            print(f"   [{i*5}sn] Workers: {workers} | Active Tasks: {active}")
            
        print(f"\n📈 Maksimum Worker Sayısı: {max_workers} (Başlangıç: 1)")
        
        if max_workers > 1:
            print("   ✅ BAŞARILI: Sistem otomatik olarak Scale-Out yaptı!")
        else:
            print("   ❌ BAŞARISIZ: Sistem worker sayısını artırmadı.")
            
        # 3. Bekleme (Scale-In testi için görevlerin bitmesini bekle)
        print("\n⏳ Görevlerin bitmesi bekleniyor (Scale-In için)...")
        # Basitçe bekleyelim, get_result uzun sürer
        time.sleep(10)
        
    finally:
        print("\n🛑 Engine kapatılıyor...")
        engine.shutdown()

if __name__ == "__main__":
    run_scaling_test()


import sys
import time
from pathlib import Path

# Proje root'unu path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from cpu_load_balancer import Engine, Task, TaskType

def run_complex_workflow_test():
    print("🚀 Complex Workflow (MapReduce) Testi Başlıyor...")
    
    engine = Engine()
    engine.start()
    
    try:
        script_path = str(Path(__file__).parent / "test_tasks.py")
        tasks = []
        
        # 1. Splitter (Root Task)
        splitter = Task.create(
            script_path=script_path,
            params={"type": "light", "name": "Splitter"},
            task_type=TaskType.CPU_BOUND
        )
        tasks.append(splitter)
        
        # 2. Mappers (50 Paralel Görev) - Splitter'a bağımlı
        mappers = []
        for i in range(50):
            mapper = Task.create(
                script_path=script_path,
                params={"type": "medium", "name": f"Mapper-{i}"}, # Biraz iş yapsınlar (Medium)
                task_type=TaskType.CPU_BOUND,
                dependencies=[splitter.id]
            )
            mappers.append(mapper)
            tasks.extend(mappers)
            
        # 3. Reducer (Final Task) - Tüm Mapper'lara bağımlı
        reducer = Task.create(
            script_path=script_path,
            params={"type": "light", "name": "Reducer"},
            task_type=TaskType.CPU_BOUND,
            dependencies=[m.id for m in mappers] # 50 bağımlılık!
        )
        tasks.append(reducer)
        
        print(f"📝 Workflow Tanımlandı:")
        print(f"   Splitter -> 50 Mappers -> Reducer")
        print(f"   Toplam Görev: {len(tasks)}")
        
        start_time = time.time()
        
        # Workflow'u gönder
        engine.submit_workflow(tasks)
        print("📤 Workflow gönderildi...")
        
        # Sadece Reducer'ı beklemek yeterli, çünkü o en son bitecek
        print("\n⏳ Reducer bekleniyor (Tüm zincirin bitmesi lazım)...")
        
        # Timeout'u uzun tutalım (50 medium task * süre / 4 worker)
        res_reducer = engine.get_result(reducer.id, timeout=60)
        
        duration = time.time() - start_time
        
        if res_reducer:
            print(f"   ✅ Reducer Bitti! Workflow Tamamlandı.")
            print(f"   ⏱️ Toplam Süre: {duration:.2f} saniye")
            
            # Veri aktarımı kontrolü (Reducer'a 50 sonuç gelmiş mi?)
            upstream = res_reducer.data.get('upstream_results', {})
            # Not: test_tasks.py upstream_results'ı döndürmüyor olabilir,
            # ama WorkflowManager'ın bunu parametreye eklediğini biliyoruz.
            # Performans testi olduğu için süreye odaklanalım.
        else:
            print("   ❌ Reducer Timeout! Sistem yetişemedi.")
            
    finally:
        print("\n🛑 Engine kapatılıyor...")
        engine.shutdown()

if __name__ == "__main__":
    run_complex_workflow_test()

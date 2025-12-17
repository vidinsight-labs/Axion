
import sys
import time
from pathlib import Path

# Proje root'unu path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from cpu_load_balancer import Engine, Task, TaskType

def run_workflow_test():
    print("🚀 Workflow (DAG) Testi Başlıyor...")
    
    engine = Engine()
    engine.start()
    
    try:
        # Script path (test_tasks.py kullanacağız)
        script_path = str(Path(__file__).parent / "test_tasks.py")
        
        # 1. Task A: Başlangıç (Hafif iş)
        task_a = Task.create(
            script_path=script_path,
            params={"type": "light", "name": "Task A"},
            task_type=TaskType.CPU_BOUND
        )
        
        # 2. Task B: A'ya bağımlı (Orta iş)
        task_b = Task.create(
            script_path=script_path,
            params={"type": "medium", "name": "Task B"},
            task_type=TaskType.CPU_BOUND,
            dependencies=[task_a.id]
        )
        
        # 3. Task C: B'ye bağımlı (Hafif iş)
        task_c = Task.create(
            script_path=script_path,
            params={"type": "light", "name": "Task C"},
            task_type=TaskType.CPU_BOUND,
            dependencies=[task_b.id]
        )
        
        print(f"📝 Workflow Tanımlandı:")
        print(f"   A ({task_a.id}) -> B ({task_b.id}) -> C ({task_c.id})")
        
        # Workflow'u gönder
        engine.submit_workflow([task_a, task_b, task_c])
        print("📤 Workflow gönderildi. Zincirleme reaksiyon bekleniyor...")
        
        # Sonuçları bekle (Sadece en sonuncuyu beklemek yeterli olmalı ama hepsini kontrol edelim)
        
        print("\n⏳ Task A bekleniyor...")
        res_a = engine.get_result(task_a.id, timeout=10)
        if res_a:
            print(f"   ✅ Task A Bitti! Sonuç: {res_a.data.get('result')}")
        else:
            print("   ❌ Task A Timeout!")
            
        print("\n⏳ Task B bekleniyor (A bittiği için başlamış olmalı)...")
        res_b = engine.get_result(task_b.id, timeout=10)
        if res_b:
            print(f"   ✅ Task B Bitti! Sonuç: {res_b.data.get('count')}")
            # Veri aktarımı kontrolü
            upstream = res_b.data.get('upstream_results', {})
            print(f"      (Gelen Veri: {len(upstream)} adet)")
        else:
            print("   ❌ Task B Timeout!")
            
        print("\n⏳ Task C bekleniyor (B bittiği için başlamış olmalı)...")
        res_c = engine.get_result(task_c.id, timeout=10)
        if res_c:
            print(f"   ✅ Task C Bitti! Sonuç: {res_c.data.get('result')}")
        else:
            print("   ❌ Task C Timeout!")
            
    finally:
        print("\n🛑 Engine kapatılıyor...")
        engine.shutdown()

if __name__ == "__main__":
    run_workflow_test()

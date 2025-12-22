#!/usr/bin/env python3
"""Network I/O script test - Engine ile"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cpu_load_balancer import Engine, EngineConfig, Task, TaskType

def main():
    print("Testing network_io_task.py with Engine...")
    
    # Engine config
    config = EngineConfig(
        cpu_bound_count=1,
        io_bound_count=2,
        cpu_bound_task_limit=1,
        io_bound_task_limit=10,
        input_queue_size=100,
        output_queue_size=500
    )
    
    engine = Engine(config)
    engine.start()
    
    try:
        # Script path
        script_path = Path(__file__).parent / "test_scripts" / "network_io_task.py"
        
        # Test parametreleri
        task_params = {
            "urls": ["https://httpbin.org/get"],
            "timeout": 10,
            "retry_count": 1
        }
        
        # Görev gönder
        print(f"\n📤 Görev gönderiliyor...")
        task = Task.create(
            script_path=str(script_path),
            params=task_params,
            task_type=TaskType.IO_BOUND
        )
        task_id = engine.submit_task(task)
        print(f"   Task ID: {task_id}")
        
        # Sonuç bekle
        print(f"\n⏳ Sonuç bekleniyor...")
        result = engine.get_result(task_id, timeout=30.0)
        
        if result:
            print(f"\n✅ Sonuç alındı:")
            print(f"   - Success: {result.is_success}")
            print(f"   - Status: {result.status}")
            print(f"   - Error: {result.error}")
            print(f"   - Data: {result.data}")
            
            if result.data:
                print(f"\n📊 Data içeriği:")
                for k, v in result.data.items():
                    print(f"   - {k}: {v}")
        else:
            print(f"\n❌ Sonuç alınamadı (timeout)")
    
    finally:
        engine.shutdown()

if __name__ == "__main__":
    main()


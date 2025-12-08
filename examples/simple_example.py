#!/usr/bin/env python3
"""
Basit Kullanım Örneği - CPU Load Balancer

Bu örnek, CPU Load Balancer'ın temel kullanımını gösterir:
- Engine oluşturma ve başlatma
- Basit bir görev gönderme
- Sonuç alma
"""

import sys
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
    """Basit kullanım örneği"""
    print("=" * 60)
    print("BASİT KULLANIM ÖRNEĞİ")
    print("=" * 60)
    
    # 1. Engine Config oluştur (varsayılan ayarlar)
    config = EngineConfig()
    print(f"\n📊 Config:")
    print(f"   CPU-bound workers: {config.cpu_bound_count}")
    print(f"   IO-bound workers: {config.io_bound_count}")
    
    # 2. Engine oluştur ve başlat
    print("\n🔧 Engine başlatılıyor...")
    engine = Engine(config)
    engine.start()
    print("✅ Engine başlatıldı")
    
    try:
        # 3. Basit bir görev script'i oluştur
        script_path = Path(__file__).parent / "simple_task.py"
        
        if not script_path.exists():
            print(f"❌ Script bulunamadı: {script_path}")
            return 1
        
        # 4. Görev oluştur
        task = Task.create(
            script_path=str(script_path),
            params={"value": 42, "test": True},
            task_type=TaskType.IO_BOUND
        )
        
        print(f"\n📤 Görev gönderiliyor: {task.id[:8]}...")
        
        # 5. Görevi gönder
        task_id = engine.submit_task(task)
        print(f"✅ Görev gönderildi: {task_id[:8]}...")
        
        # 6. Sonucu bekle
        print("\n⏳ Sonuç bekleniyor...")
        result = engine.get_result(task_id, timeout=30.0)
        
        if result and result.is_success:
            print(f"\n✅ Görev başarılı!")
            print(f"   Sonuç: {result.data}")
        else:
            print(f"\n❌ Görev başarısız")
            if result:
                print(f"   Hata: {result.error}")
            else:
                print("   Timeout - sonuç alınamadı")
            return 1
        
    except Exception as e:
        print(f"\n❌ Hata: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        # 7. Engine'i kapat
        print("\n🛑 Engine kapatılıyor...")
        engine.shutdown()
        print("✅ Engine kapatıldı")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


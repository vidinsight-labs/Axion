#!/usr/bin/env python3
"""
CPU Load Balancer - Ana Giriş Noktası

Kullanım:
    python -m cpu_load_balancer.main
    python -m cpu_load_balancer.main --config config/custom_config.json
    python -m cpu_load_balancer.main --interactive
"""

import argparse
import sys
import os
import signal
import time
import json
from pathlib import Path
from typing import Optional

from .engine import Engine
from .config import EngineConfig
from .task.task import Task
from .core.enums import TaskType
from .core.exceptions import EngineError, TaskError


class CPULoadBalancerApp:
    """Ana uygulama sınıfı"""
    
    def __init__(self, config: Optional[EngineConfig] = None):
        self.config = config or EngineConfig()
        self.engine: Optional[Engine] = None
        self.running = False
    
    def start(self):
        """Engine'i başlat"""
        print("🚀 CPU Load Balancer başlatılıyor...")
        print(f"   Config: cpu_bound={self.config.cpu_bound_count}, "
              f"io_bound={self.config.io_bound_count}")
        
        try:
            self.engine = Engine(self.config)
            self.engine.start()
            self.running = True
            
            # Signal handler'ları ayarla
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            print("✅ Engine başarıyla başlatıldı!")
            return True
        
        except Exception as e:
            print(f"❌ Engine başlatma hatası: {e}", file=sys.stderr)
            return False
    
    def shutdown(self):
        """Engine'i kapat"""
        if self.engine and self.running:
            print("\n🛑 Engine kapatılıyor...")
            self.engine.shutdown()
            self.running = False
            print("✅ Engine kapatıldı")
    
    def _signal_handler(self, signum, frame):
        """Signal handler - graceful shutdown"""
        print(f"\n⚠️  Signal alındı ({signum}), kapatılıyor...")
        self.shutdown()
        sys.exit(0)
    
    def show_status(self):
        """Engine durumunu göster"""
        if not self.engine:
            print("❌ Engine başlatılmamış")
            return
        
        status = self.engine.get_status()
        
        print("\n📊 Engine Durumu:")
        print(f"   Çalışıyor: {status['engine']['is_running']}")
        print("\n📦 Component'ler:")
        
        for name, comp_status in status['components'].items():
            health = comp_status['health']
            metrics = comp_status['metrics']
            
            print(f"\n   {name}:")
            print(f"      Sağlık: {health}")
            for key, value in metrics.items():
                print(f"      {key}: {value}")
    
    def run_interactive(self):
        """Interactive mode - kullanıcı komutları alır"""
        if not self.engine:
            print("❌ Engine başlatılmamış")
            return
        
        print("\n💡 Interactive Mode")
        print("   Komutlar: status, submit <script_path>, quit")
        print("   Örnek: submit /path/to/script.py")
        
        while self.running:
            try:
                command = input("\n> ").strip()
                
                if not command:
                    continue
                
                if command == "quit" or command == "exit":
                    break
                
                elif command == "status":
                    self.show_status()
                
                elif command.startswith("submit "):
                    script_path = command[7:].strip()
                    if not script_path:
                        print("❌ Script path belirtin: submit <script_path>")
                        continue
                    
                    self._submit_example_task(script_path)
                
                elif command == "help":
                    print("\n📖 Komutlar:")
                    print("   status              - Engine durumunu göster")
                    print("   submit <path>       - Örnek görev gönder")
                    print("   quit / exit         - Çıkış")
                    print("   help                - Bu yardım mesajı")
                
                else:
                    print(f"❌ Bilinmeyen komut: {command}")
                    print("   'help' yazarak komutları görebilirsiniz")
            
            except KeyboardInterrupt:
                break
            except EOFError:
                break
    
    def _submit_example_task(self, script_path: str):
        """Örnek görev gönder"""
        if not self.engine:
            return
        
        try:
            task = Task.create(
                script_path=script_path,
                params={"value": 42, "test": True},
                task_type=TaskType.IO_BOUND
            )
            
            task_id = self.engine.submit_task(task)
            print(f"✅ Görev gönderildi: {task_id[:8]}...")
            
            # Sonucu bekle
            print("   Sonuç bekleniyor...")
            result = self.engine.get_result(task_id, timeout=30)
            
            if result:
                if result.is_success:
                    print(f"✅ Görev başarılı!")
                    print(f"   Sonuç: {result.data}")
                else:
                    print(f"❌ Görev başarısız: {result.error}")
            else:
                print("⏱️  Timeout - sonuç alınamadı")
        
        except TaskError as e:
            print(f"❌ Görev hatası: {e}")
        except Exception as e:
            print(f"❌ Hata: {e}")
    
    def run_demo(self):
        """Demo mode - örnek görevler çalıştır"""
        if not self.engine:
            return
        
        print("\n🎬 Demo Mode - Örnek görevler çalıştırılıyor...")
        
        # Örnek script path'i (kullanıcı kendi script'ini belirtebilir)
        demo_script = input("   Script path (boş bırakırsanız demo atlanır): ").strip()
        
        if not demo_script:
            print("   Demo atlandı")
            return
        
        if not Path(demo_script).exists():
            print(f"❌ Script bulunamadı: {demo_script}")
            return
        
        try:
            task = Task.create(
                script_path=demo_script,
                params={"demo": True, "timestamp": time.time()},
                task_type=TaskType.IO_BOUND
            )
            
            print(f"📤 Görev gönderiliyor: {task.id[:8]}...")
            task_id = self.engine.submit_task(task)
            
            print("⏳ Sonuç bekleniyor...")
            result = self.engine.get_result(task_id, timeout=30)
            
            if result:
                if result.is_success:
                    print(f"✅ Başarılı! Sonuç: {result.data}")
                else:
                    print(f"❌ Başarısız: {result.error}")
            else:
                print("⏱️  Timeout")
        
        except Exception as e:
            print(f"❌ Demo hatası: {e}")


def load_config_from_file(config_path: str) -> Optional[EngineConfig]:
    """JSON dosyasından config yükle"""
    try:
        # Eğer relative path ise, config klasöründen başlat
        if not os.path.isabs(config_path):
            # Önce mevcut dizinde dene
            if not os.path.exists(config_path):
                # Config klasöründe dene
                config_dir = Path(__file__).parent / "config"
                config_path_in_dir = config_dir / config_path
                if config_path_in_dir.exists():
                    config_path = str(config_path_in_dir)
        
        with open(config_path, 'r') as f:
            data = json.load(f)
        
        return EngineConfig(
            input_queue_size=data.get("input_queue_size", 1000),
            output_queue_size=data.get("output_queue_size", 10000),
            cpu_bound_count=data.get("cpu_bound_count", 1),
            io_bound_count=data.get("io_bound_count", None),
            cpu_bound_task_limit=data.get("cpu_bound_task_limit", 1),
            io_bound_task_limit=data.get("io_bound_task_limit", 20),
            log_level=data.get("log_level", "INFO"),
            queue_poll_timeout=data.get("queue_poll_timeout", 1.0)
        )
    
    except Exception as e:
        print(f"⚠️  Config yükleme hatası: {e}", file=sys.stderr)
        return None


def create_default_config_file(path: Optional[str] = None):
    """Varsayılan config dosyası oluştur"""
    if path is None:
        # Varsayılan olarak config klasörüne kaydet
        config_dir = Path(__file__).parent / "config"
        config_dir.mkdir(exist_ok=True)
        path = str(config_dir / "config.json")
    
    default_config = {
        "input_queue_size": 1000,
        "output_queue_size": 10000,
        "cpu_bound_count": 1,
        "io_bound_count": None,
        "cpu_bound_task_limit": 1,
        "io_bound_task_limit": 20,
        "log_level": "INFO",
        "queue_poll_timeout": 1.0
    }
    
    with open(path, 'w') as f:
        json.dump(default_config, f, indent=2)
    
    print(f"✅ Varsayılan config dosyası oluşturuldu: {path}")


def main():
    """Ana fonksiyon"""
    parser = argparse.ArgumentParser(
        description="CPU Load Balancer - Task Execution Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  # Varsayılan ayarlarla başlat
  python -m cpu_load_balancer.main
  
  # Interactive mode
  python -m cpu_load_balancer.main --interactive
  
  # Config dosyası ile
  python -m cpu_load_balancer.main --config config/my_config.json
  
  # Demo mode
  python -m cpu_load_balancer.main --demo
  
  # Varsayılan config dosyası oluştur
  python -m cpu_load_balancer.main --create-config
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        help='Config dosyası yolu (JSON). Varsayılan: config/config.json'
    )
    
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Interactive mode - komut satırından komutlar al'
    )
    
    parser.add_argument(
        '--demo', '-d',
        action='store_true',
        help='Demo mode - örnek görev çalıştır'
    )
    
    parser.add_argument(
        '--create-config',
        action='store_true',
        help='Varsayılan config.json dosyası oluştur ve çık'
    )
    
    parser.add_argument(
        '--cpu-bound',
        type=int,
        help='CPU-bound worker sayısı (varsayılan: 1)'
    )
    
    parser.add_argument(
        '--io-bound',
        type=int,
        help='IO-bound worker sayısı (varsayılan: otomatik)'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Log seviyesi (varsayılan: INFO)'
    )
    
    args = parser.parse_args()
    
    # Config dosyası oluştur
    if args.create_config:
        create_default_config_file()
        return 0
    
    # Config yükle
    config = None
    
    if args.config:
        config = load_config_from_file(args.config)
        if not config:
            return 1
    else:
        # Varsayılan config dosyasını dene
        default_config_path = Path(__file__).parent / "config" / "config.json"
        if default_config_path.exists():
            config = load_config_from_file(str(default_config_path))
    
    # Komut satırı argümanları ile config'i güncelle
    if config is None:
        config = EngineConfig()
    
    if args.cpu_bound:
        config.cpu_bound_count = args.cpu_bound
    
    if args.io_bound:
        config.io_bound_count = args.io_bound
    
    if args.log_level:
        config.log_level = args.log_level
    
    # Uygulamayı başlat
    app = CPULoadBalancerApp(config)
    
    if not app.start():
        return 1
    
    try:
        # Mod seçimi
        if args.interactive:
            app.run_interactive()
        elif args.demo:
            app.run_demo()
            # Demo sonrası interactive mode'a geç
            print("\n💡 Interactive mode'a geçiliyor...")
            app.run_interactive()
        else:
            # Varsayılan: status göster ve interactive mode'a geç
            app.show_status()
            print("\n💡 Interactive mode'a geçiliyor...")
            app.run_interactive()
    
    finally:
        app.shutdown()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


#!/usr/bin/env python3
"""
Ölçeklenebilirlik Benchmark Testi

Bu test, farklı worker sayıları ile sistem performansını ölçer.
"""

import sys
import time
import statistics
from pathlib import Path
from typing import List, Dict, Any

# Proje root'unu path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from cpu_load_balancer import Engine, EngineConfig, Task, TaskType


def run_scalability_test(
    script_path: str,
    num_tasks: int = 500,
    worker_configs: List[Dict[str, int]] = None
) -> List[Dict[str, Any]]:
    """
    Ölçeklenebilirlik testi çalıştırır
    
    Args:
        script_path: Test script path
        num_tasks: Her test için görev sayısı
        worker_configs: Worker konfigürasyonları
    
    Returns:
        List[Dict]: Her config için test sonuçları
    """
    if worker_configs is None:
        worker_configs = [
            {"cpu": 1, "io": 1},
            {"cpu": 1, "io": 2},
            {"cpu": 1, "io": 4},
            {"cpu": 1, "io": 8},
            {"cpu": 2, "io": 4},
            {"cpu": 2, "io": 8},
        ]
    
    results = []
    
    for config_dict in worker_configs:
        cpu_count = config_dict["cpu"]
        io_count = config_dict["io"]
        
        print(f"\n{'='*60}")
        print(f"Test: CPU={cpu_count}, IO={io_count}")
        print(f"{'='*60}")
        
        # Config oluştur
        config = EngineConfig(
            cpu_bound_count=cpu_count,
            io_bound_count=io_count,
            cpu_bound_task_limit=1,
            io_bound_task_limit=10,
            input_queue_size=2000,
            output_queue_size=10000
        )
        
        # Engine oluştur ve başlat
        engine = Engine(config)
        engine.start()
        
        try:
            # Görevleri gönder
            task_ids = []
            start_time = time.time()
            
            print(f"\n📤 {num_tasks} görev gönderiliyor...")
            for i in range(num_tasks):
                task = Task.create(
                    script_path=script_path,
                    params={"value": i, "test": True},
                    task_type=TaskType.IO_BOUND
                )
                task_id = engine.submit_task(task)
                task_ids.append(task_id)
            
            submit_time = time.time() - start_time
            
            # Sonuçları al
            print(f"⏳ Sonuçlar bekleniyor...")
            results_list = []
            latencies = []
            
            for task_id in task_ids:
                result = engine.get_result(task_id, timeout=30.0)
                if result:
                    results_list.append(result)
                    if result.duration:
                        latencies.append(result.duration)
            
            total_time = time.time() - start_time
            
            # Metrikleri hesapla
            successful = len([r for r in results_list if r.is_success])
            success_rate = successful / len(results_list) if results_list else 0
            throughput = len(results_list) / total_time if total_time > 0 else 0
            
            # Status bilgileri
            status = engine.get_status()
            pool_metrics = status["components"]["process_pool"]["metrics"]
            
            result = {
                "config": {"cpu": cpu_count, "io": io_count},
                "total_workers": pool_metrics["total_workers"],
                "total_tasks": num_tasks,
                "successful_tasks": successful,
                "success_rate": success_rate,
                "total_duration": total_time,
                "throughput": throughput,
                "latency": {
                    "avg": statistics.mean(latencies) if latencies else 0,
                    "min": min(latencies) if latencies else 0,
                    "max": max(latencies) if latencies else 0,
                    "p95": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 0 else 0,
                } if latencies else {},
            }
            
            results.append(result)
            
            print(f"\n📊 Sonuçlar:")
            print(f"   - Throughput: {throughput:.2f} görev/saniye")
            print(f"   - Başarı oranı: {success_rate*100:.1f}%")
            print(f"   - Ortalama latency: {result['latency'].get('avg', 0)*1000:.2f} ms")
            
        finally:
            engine.shutdown()
    
    return results


def main():
    """Ana fonksiyon"""
    print("=" * 60)
    print("🚀 CPU Load Balancer - Ölçeklenebilirlik Benchmark")
    print("=" * 60)
    
    # Script path
    script_path = str(Path(__file__).parent.parent / "examples" / "simple_task.py")
    
    if not Path(script_path).exists():
        print(f"❌ Script bulunamadı: {script_path}")
        return 1
    
    # Test çalıştır
    results = run_scalability_test(script_path, num_tasks=500)
    
    # Özet tablo
    print("\n" + "=" * 60)
    print("📈 Ölçeklenebilirlik Özeti")
    print("=" * 60)
    print(f"{'Config':<15} {'Workers':<10} {'Throughput':<15} {'Success':<10} {'Avg Latency':<15}")
    print("-" * 60)
    
    for result in results:
        config = result["config"]
        config_str = f"CPU={config['cpu']}, IO={config['io']}"
        print(f"{config_str:<15} {result['total_workers']:<10} {result['throughput']:<15.2f} {result['success_rate']*100:<10.1f}% {result['latency'].get('avg', 0)*1000:<15.2f} ms")
    
    # Analiz
    print("\n" + "=" * 60)
    print("📊 Analiz")
    print("=" * 60)
    
    if len(results) > 1:
        first_throughput = results[0]["throughput"]
        last_throughput = results[-1]["throughput"]
        
        if first_throughput > 0:
            speedup = last_throughput / first_throughput
            print(f"   - İlk config throughput: {first_throughput:.2f} görev/saniye")
            print(f"   - Son config throughput: {last_throughput:.2f} görev/saniye")
            print(f"   - Hızlanma: {speedup:.2f}x")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


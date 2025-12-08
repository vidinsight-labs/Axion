#!/usr/bin/env python3
"""
Batch İşlem Benchmark Testi

Bu test, batch işlemlerin performansını ölçer.
"""

import sys
import time
import statistics
from pathlib import Path
from typing import List, Dict, Any

# Proje root'unu path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from cpu_load_balancer import Engine, EngineConfig, Task, TaskType


def run_batch_test(
    engine: Engine,
    script_path: str,
    batch_size: int
) -> Dict[str, Any]:
    """
    Batch test çalıştırır
    
    Args:
        engine: Engine instance
        script_path: Test script path
        batch_size: Batch boyutu
    
    Returns:
        Dict: Test sonuçları
    """
    print(f"\n📊 Batch Test: {batch_size} görev")
    
    # Görevleri oluştur
    tasks = []
    for i in range(batch_size):
        task = Task.create(
            script_path=script_path,
            params={"value": i, "test": True},
            task_type=TaskType.IO_BOUND
        )
        tasks.append(task)
    
    # Görevleri gönder
    start_time = time.time()
    task_ids = []
    
    for task in tasks:
        task_id = engine.submit_task(task)
        task_ids.append(task_id)
    
    submit_time = time.time() - start_time
    
    # İlk sonuç zamanı
    first_result_time = None
    last_result_time = None
    
    # Sonuçları al
    results = []
    latencies = []
    
    for task_id in task_ids:
        result = engine.get_result(task_id, timeout=30.0)
        if result:
            if first_result_time is None:
                first_result_time = time.time()
            last_result_time = time.time()
            
            results.append(result)
            if result.duration:
                latencies.append(result.duration)
    
    total_time = time.time() - start_time
    
    # Metrikleri hesapla
    successful = len([r for r in results if r.is_success])
    success_rate = successful / len(results) if results else 0
    
    batch_throughput = len(results) / total_time if total_time > 0 else 0
    
    time_to_first_result = (first_result_time - start_time) if first_result_time else 0
    time_to_last_result = (last_result_time - start_time) if last_result_time else 0
    batch_duration = time_to_last_result - time_to_first_result if (time_to_first_result and time_to_last_result) else 0
    
    return {
        "batch_size": batch_size,
        "total_tasks": len(tasks),
        "successful_tasks": successful,
        "success_rate": success_rate,
        "submit_time": submit_time,
        "total_time": total_time,
        "time_to_first_result": time_to_first_result,
        "time_to_last_result": time_to_last_result,
        "batch_duration": batch_duration,
        "throughput": batch_throughput,
        "latency": {
            "avg": statistics.mean(latencies) if latencies else 0,
            "min": min(latencies) if latencies else 0,
            "max": max(latencies) if latencies else 0,
        } if latencies else {},
    }


def main():
    """Ana fonksiyon"""
    print("=" * 60)
    print("🚀 CPU Load Balancer - Batch İşlem Benchmark")
    print("=" * 60)
    
    # Script path
    script_path = str(Path(__file__).parent.parent / "examples" / "simple_task.py")
    
    if not Path(script_path).exists():
        print(f"❌ Script bulunamadı: {script_path}")
        return 1
    
    # Config
    config = EngineConfig(
        cpu_bound_count=1,
        io_bound_count=4,
        cpu_bound_task_limit=1,
        io_bound_task_limit=10,
        input_queue_size=2000,
        output_queue_size=10000
    )
    
    print(f"\n⚙️  Config:")
    print(f"   - CPU workers: {config.cpu_bound_count}")
    print(f"   - IO workers: {config.io_bound_count}")
    
    # Engine oluştur ve başlat
    engine = Engine(config)
    engine.start()
    
    try:
        # Farklı batch boyutları ile test
        batch_sizes = [10, 50, 100, 500, 1000]
        results = []
        
        for batch_size in batch_sizes:
            result = run_batch_test(engine, script_path, batch_size)
            results.append(result)
            
            print(f"\n📊 Sonuçlar:")
            print(f"   - Toplam süre: {result['total_time']:.2f} saniye")
            print(f"   - İlk sonuç: {result['time_to_first_result']:.3f} saniye")
            print(f"   - Son sonuç: {result['time_to_last_result']:.3f} saniye")
            print(f"   - Batch süresi: {result['batch_duration']:.3f} saniye")
            print(f"   - Throughput: {result['throughput']:.2f} görev/saniye")
            print(f"   - Başarı oranı: {result['success_rate']*100:.1f}%")
        
        # Özet tablo
        print("\n" + "=" * 60)
        print("📈 Batch Test Özeti")
        print("=" * 60)
        print(f"{'Batch Size':<15} {'Total Time':<15} {'Throughput':<15} {'Success':<10} {'Batch Duration':<15}")
        print("-" * 60)
        
        for result in results:
            print(f"{result['batch_size']:<15} {result['total_time']:<15.2f} {result['throughput']:<15.2f} {result['success_rate']*100:<10.1f}% {result['batch_duration']:<15.3f}")
        
    finally:
        engine.shutdown()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


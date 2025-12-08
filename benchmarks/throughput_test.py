#!/usr/bin/env python3
"""
Throughput Benchmark Testi

Bu test, sistemin saniyede kaç görev işleyebildiğini ölçer.
"""

import sys
import time
import statistics
from pathlib import Path
from typing import List, Dict, Any

# Proje root'unu path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from cpu_load_balancer import Engine, EngineConfig, Task, TaskType


def create_simple_task(script_path: str, value: int) -> Task:
    """Basit görev oluştur"""
    return Task.create(
        script_path=script_path,
        params={"value": value, "test": True},
        task_type=TaskType.IO_BOUND
    )


def run_throughput_test(
    engine: Engine,
    script_path: str,
    num_tasks: int = 1000,
    batch_size: int = 100
) -> Dict[str, Any]:
    """
    Throughput testi çalıştırır
    
    Args:
        engine: Engine instance
        script_path: Test script path
        num_tasks: Toplam görev sayısı
        batch_size: Her batch'te kaç görev gönderilecek
    
    Returns:
        Dict: Test sonuçları
    """
    print(f"\n📊 Throughput Testi Başlıyor...")
    print(f"   - Toplam görev: {num_tasks}")
    print(f"   - Batch boyutu: {batch_size}")
    
    # Test başlangıcı
    start_time = time.time()
    
    # Görevleri gönder
    task_ids: List[str] = []
    submit_times: List[float] = []
    
    print(f"\n📤 Görevler gönderiliyor...")
    submit_start = time.time()
    
    for i in range(0, num_tasks, batch_size):
        batch_end = min(i + batch_size, num_tasks)
        batch_task_ids = []
        
        for j in range(i, batch_end):
            task = create_simple_task(script_path, j)
            task_id = engine.submit_task(task)
            batch_task_ids.append(task_id)
            submit_times.append(time.time() - submit_start)
        
        task_ids.extend(batch_task_ids)
        
        if (i // batch_size + 1) % 10 == 0:
            print(f"   ✅ {batch_end}/{num_tasks} görev gönderildi")
    
    submit_duration = time.time() - submit_start
    print(f"   ✅ Tüm görevler gönderildi ({submit_duration:.2f} saniye)")
    
    # Sonuçları al
    print(f"\n⏳ Sonuçlar bekleniyor...")
    results: List[Any] = []
    latencies: List[float] = []
    result_start = time.time()
    
    for i, task_id in enumerate(task_ids):
        result = engine.get_result(task_id, timeout=30.0)
        if result:
            results.append(result)
            if result.duration:
                latencies.append(result.duration)
        
        if (i + 1) % 100 == 0:
            print(f"   ✅ {i + 1}/{num_tasks} sonuç alındı")
    
    result_duration = time.time() - result_start
    total_duration = time.time() - start_time
    
    # Metrikleri hesapla
    successful = len([r for r in results if r.is_success])
    success_rate = successful / len(results) if results else 0
    
    throughput = len(results) / total_duration if total_duration > 0 else 0
    
    latency_stats = {}
    if latencies:
        latency_stats = {
            "avg": statistics.mean(latencies),
            "min": min(latencies),
            "max": max(latencies),
            "p50": statistics.median(latencies),
            "p95": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 0 else 0,
            "p99": sorted(latencies)[int(len(latencies) * 0.99)] if len(latencies) > 0 else 0,
        }
    
    return {
        "total_tasks": num_tasks,
        "successful_tasks": successful,
        "success_rate": success_rate,
        "total_duration": total_duration,
        "submit_duration": submit_duration,
        "result_duration": result_duration,
        "throughput": throughput,  # Görevler/saniye
        "latency": latency_stats,
        "submit_times": {
            "avg": statistics.mean(submit_times) if submit_times else 0,
            "max": max(submit_times) if submit_times else 0,
        }
    }


def main():
    """Ana fonksiyon"""
    print("=" * 60)
    print("🚀 CPU Load Balancer - Throughput Benchmark")
    print("=" * 60)
    
    # Script path
    script_path = str(Path(__file__).parent.parent / "examples" / "simple_task.py")
    
    if not Path(script_path).exists():
        print(f"❌ Script bulunamadı: {script_path}")
        return 1
    
    # Config - Büyük testler için daha büyük queue
    config = EngineConfig(
        cpu_bound_count=1,
        io_bound_count=4,
        cpu_bound_task_limit=1,
        io_bound_task_limit=10,
        input_queue_size=10000,  # Büyük testler için artırıldı
        output_queue_size=20000  # Büyük testler için artırıldı
    )
    
    print(f"\n⚙️  Config:")
    print(f"   - CPU workers: {config.cpu_bound_count}")
    print(f"   - IO workers: {config.io_bound_count}")
    print(f"   - Input queue: {config.input_queue_size}")
    print(f"   - Output queue: {config.output_queue_size}")
    
    # Engine oluştur ve başlat
    engine = Engine(config)
    engine.start()
    
    try:
        # Test 1: Küçük test (100 görev)
        print("\n" + "=" * 60)
        print("Test 1: Küçük Test (100 görev)")
        print("=" * 60)
        result1 = run_throughput_test(engine, script_path, num_tasks=100, batch_size=10)
        
        print(f"\n📊 Sonuçlar:")
        print(f"   - Throughput: {result1['throughput']:.2f} görev/saniye")
        print(f"   - Başarı oranı: {result1['success_rate']*100:.1f}%")
        print(f"   - Ortalama latency: {result1['latency'].get('avg', 0)*1000:.2f} ms")
        print(f"   - P95 latency: {result1['latency'].get('p95', 0)*1000:.2f} ms")
        
        # Test 2: Orta test (1000 görev)
        print("\n" + "=" * 60)
        print("Test 2: Orta Test (1000 görev)")
        print("=" * 60)
        result2 = run_throughput_test(engine, script_path, num_tasks=1000, batch_size=100)
        
        print(f"\n📊 Sonuçlar:")
        print(f"   - Throughput: {result2['throughput']:.2f} görev/saniye")
        print(f"   - Başarı oranı: {result2['success_rate']*100:.1f}%")
        print(f"   - Ortalama latency: {result2['latency'].get('avg', 0)*1000:.2f} ms")
        print(f"   - P95 latency: {result2['latency'].get('p95', 0)*1000:.2f} ms")
        
        # Test 3: Büyük test (5000 görev) - Daha küçük batch size ile
        print("\n" + "=" * 60)
        print("Test 3: Büyük Test (5000 görev)")
        print("=" * 60)
        result3 = run_throughput_test(engine, script_path, num_tasks=5000, batch_size=200)  # Batch size küçültüldü
        
        print(f"\n📊 Sonuçlar:")
        print(f"   - Throughput: {result3['throughput']:.2f} görev/saniye")
        print(f"   - Başarı oranı: {result3['success_rate']*100:.1f}%")
        print(f"   - Ortalama latency: {result3['latency'].get('avg', 0)*1000:.2f} ms")
        print(f"   - P95 latency: {result3['latency'].get('p95', 0)*1000:.2f} ms")
        
        # Özet
        print("\n" + "=" * 60)
        print("📈 Özet")
        print("=" * 60)
        print(f"{'Test':<20} {'Throughput':<15} {'Success Rate':<15} {'Avg Latency':<15}")
        print("-" * 60)
        print(f"{'Küçük (100)':<20} {result1['throughput']:<15.2f} {result1['success_rate']*100:<15.1f}% {result1['latency'].get('avg', 0)*1000:<15.2f} ms")
        print(f"{'Orta (1000)':<20} {result2['throughput']:<15.2f} {result2['success_rate']*100:<15.1f}% {result2['latency'].get('avg', 0)*1000:<15.2f} ms")
        print(f"{'Büyük (5000)':<20} {result3['throughput']:<15.2f} {result3['success_rate']*100:<15.1f}% {result3['latency'].get('avg', 0)*1000:<15.2f} ms")
        
    finally:
        engine.shutdown()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


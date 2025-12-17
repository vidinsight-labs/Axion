#!/usr/bin/env python3
"""
Heavy Load Benchmark Testi

Bu test, farklı zorluk seviyelerindeki (Hafif, Orta, Ağır) CPU-bound görevlerin
performansını ölçer ve worker dağılımını analiz eder.
"""

import sys
import time
import statistics
from pathlib import Path
from typing import List, Dict, Any
from collections import Counter

# Proje root'unu path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from cpu_load_balancer import Engine, EngineConfig, Task, TaskType


def run_load_test(
    engine: Engine,
    script_path: str,
    complexity: str,
    num_tasks: int,
    batch_size: int
) -> Dict[str, Any]:
    """
    Belirli bir zorluk seviyesi için test çalıştırır
    """
    print(f"\n📊 {complexity.upper()} Yük Testi Başlıyor...")
    print(f"   - Toplam görev: {num_tasks}")
    print(f"   - Batch boyutu: {batch_size}")
    
    start_time = time.time()
    
    # Görevleri gönder
    task_ids: List[str] = []
    
    print(f"\n📤 Görevler gönderiliyor...")
    submit_start = time.time()
    
    for i in range(0, num_tasks, batch_size):
        batch_end = min(i + batch_size, num_tasks)
        
        for j in range(i, batch_end):
            task = Task.create(
                script_path=script_path,
                params={"type": complexity},
                task_type=TaskType.CPU_BOUND
            )
            task_id = engine.submit_task(task)
            task_ids.append(task_id)
        
        if (i // batch_size + 1) % 5 == 0:
            print(f"   ✅ {batch_end}/{num_tasks} görev gönderildi")
    
    submit_duration = time.time() - submit_start
    print(f"   ✅ Tüm görevler gönderildi ({submit_duration:.2f} saniye)")
    
    # Sonuçları al
    print(f"\n⏳ Sonuçlar bekleniyor...")
    results: List[Any] = []
    task_durations: List[float] = []
    worker_ids: List[str] = []
    
    result_start = time.time()
    
    for i, task_id in enumerate(task_ids):
        result = engine.get_result(task_id, timeout=60.0)
        if result:
            results.append(result)
            if result.is_success and isinstance(result.data, dict):
                task_durations.append(result.data.get("duration", 0))
                worker_ids.append(result.data.get("worker_id", "unknown"))
        
        if (i + 1) % (num_tasks // 5 if num_tasks >= 5 else 1) == 0:
            print(f"   ✅ {i + 1}/{num_tasks} sonuç alındı")
    
    total_duration = time.time() - start_time
    
    # Metrikleri hesapla
    successful = len([r for r in results if r.is_success])
    success_rate = successful / len(results) if results else 0
    throughput = len(results) / total_duration if total_duration > 0 else 0
    
    # Task execution time istatistikleri
    exec_stats = {}
    if task_durations:
        exec_stats = {
            "avg": statistics.mean(task_durations),
            "min": min(task_durations),
            "max": max(task_durations),
            "p95": sorted(task_durations)[int(len(task_durations) * 0.95)] if len(task_durations) > 0 else 0
        }
        
    # Worker dağılımı
    worker_dist = dict(Counter(worker_ids))

    return {
        "complexity": complexity,
        "total_tasks": num_tasks,
        "throughput": throughput,
        "total_duration": total_duration,
        "exec_stats": exec_stats,
        "success_rate": success_rate,
        "worker_dist": worker_dist
    }


def main():
    print("=" * 60)
    print("🏋️  CPU Load Balancer - Heavy Load Benchmark & Analysis")
    print("=" * 60)
    
    script_path = str(Path(__file__).parent / "test_tasks.py")
    
    if not Path(script_path).exists():
        print(f"❌ Script bulunamadı: {script_path}")
        return 1
    
    # Config - 4 CPU worker
    config = EngineConfig(
        cpu_bound_count=4,
        io_bound_count=2,
        cpu_bound_task_limit=1,
        input_queue_size=5000,
        output_queue_size=5000
    )
    
    print(f"\n⚙️  Config:")
    print(f"   - CPU workers: {config.cpu_bound_count}")
    
    engine = Engine(config)
    engine.start()
    
    results = []
    
    try:
        # 1. Hafif Yük Testi
        results.append(run_load_test(
            engine, script_path, 
            complexity="light", 
            num_tasks=1000, 
            batch_size=100
        ))
        
        # 2. Orta Yük Testi
        results.append(run_load_test(
            engine, script_path, 
            complexity="medium", 
            num_tasks=1000, 
            batch_size=100
        ))
        
        # 3. Ağır Yük Testi
        results.append(run_load_test(
            engine, script_path, 
            complexity="heavy", 
            num_tasks=1000,  # Sayıyı artırdım
            batch_size=100
        ))
        
        # Özet Tablo
        print("\n" + "=" * 100)
        print("📈 Yük Testi Özeti")
        print("=" * 100)
        print(f"{'Complexity':<10} {'Tasks':<8} {'Throughput':<12} {'Avg Exec':<12} {'Total Time':<12} {'Worker Dist'}")
        print("-" * 100)
        
        for r in results:
            avg_exec = r['exec_stats'].get('avg', 0) * 1000
            worker_dist_str = ", ".join([f"{k}:{v}" for k, v in sorted(r['worker_dist'].items())])
            print(f"{r['complexity']:<10} {r['total_tasks']:<8} {r['throughput']:<12.2f} {avg_exec:<12.2f} {r['total_duration']:<12.2f} {worker_dist_str}")
            
    finally:
        print("\n🛑 Engine kapatılıyor...")
        engine.shutdown()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Task Submission Latency Performance Testi

Bu test, task submit etme hızını ölçer.
Submit call duration, queue insertion time ve API responsiveness ölçer.
"""

import sys
import time
import statistics
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, field

# Proje root'unu path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from axion import Engine, EngineConfig, Task, TaskType


@dataclass
class SubmissionLatencyResult:
    """Task submission latency test sonuçları"""
    test_name: str
    task_count: int
    task_type: str
    total_submit_time: float = 0.0
    avg_submit_latency: float = 0.0
    min_submit_latency: float = 0.0
    max_submit_latency: float = 0.0
    p50_submit_latency: float = 0.0
    p95_submit_latency: float = 0.0
    p99_submit_latency: float = 0.0
    submit_throughput: float = 0.0  # Görev/saniye
    queue_insertion_time: float = 0.0  # Ortalama queue insertion time
    metrics: Dict[str, Any] = field(default_factory=dict)


def run_submission_latency_test(
    engine: Engine,
    script_path: str,
    test_name: str,
    task_params: Dict,
    task_count: int,
    task_type: TaskType
) -> SubmissionLatencyResult:
    """
    Task submission latency test çalıştırır
    
    Args:
        engine: Engine instance
        script_path: Test script path
        test_name: Test adı
        task_params: Task parametreleri
        task_count: Görev sayısı
        task_type: Görev tipi (CPU_BOUND veya IO_BOUND)
    
    Returns:
        SubmissionLatencyResult: Test sonuçları
    """
    print(f"\n{'='*70}")
    print(f"🧪 Test: {test_name}")
    print(f"{'='*70}")
    print(f"   - Görev sayısı: {task_count:,}")
    print(f"   - Görev tipi: {task_type.value}")
    
    # Submit latency'leri ölç
    submit_latencies = []
    task_ids = []
    
    print(f"\n📤 {task_count:,} görev gönderiliyor (latency ölçümü ile)...")
    
    total_start = time.time()
    
    for i in range(task_count):
        # Her submit çağrısının süresini ölç
        submit_start = time.time()
        
        # Task oluştur
        task = Task.create(
            script_path=script_path,
            params=task_params,
            task_type=task_type
        )
        
        # Submit et
        task_id = engine.submit_task(task)
        
        submit_end = time.time()
        submit_latency = (submit_end - submit_start) * 1000  # ms
        submit_latencies.append(submit_latency)
        task_ids.append(task_id)
        
        # İlerleme göster (büyük görev sayıları için)
        if task_count >= 1000 and (i + 1) % max(1, task_count // 20) == 0:
            elapsed = time.time() - total_start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            avg_latency = statistics.mean(submit_latencies) if submit_latencies else 0
            print(f"   📊 {i + 1:,}/{task_count:,} görev gönderildi "
                  f"({rate:.0f} görev/s, avg latency: {avg_latency:.3f} ms)")
    
    total_submit_time = time.time() - total_start
    
    # Queue durumunu kontrol et (insertion time için)
    queue_insertion_time = 0.0
    try:
        status = engine.get_status()
        if "input_queue" in status["components"]:
            queue_metrics = status["components"]["input_queue"]["metrics"]
            # Queue size ve total_put bilgisi varsa insertion time hesaplanabilir
            # Ancak bu bilgi mevcut değilse, submit latency'den tahmin edilebilir
            queue_insertion_time = statistics.mean(submit_latencies) if submit_latencies else 0.0
    except:
        queue_insertion_time = statistics.mean(submit_latencies) if submit_latencies else 0.0
    
    # Latency istatistikleri
    latency_stats = {}
    if submit_latencies:
        sorted_latencies = sorted(submit_latencies)
        latency_stats = {
            "avg": statistics.mean(submit_latencies),
            "min": min(submit_latencies),
            "max": max(submit_latencies),
            "p50": statistics.median(submit_latencies),
            "p95": sorted_latencies[int(len(sorted_latencies) * 0.95)] if len(sorted_latencies) > 0 else 0,
            "p99": sorted_latencies[int(len(sorted_latencies) * 0.99)] if len(sorted_latencies) > 0 else 0,
        }
    
    # Throughput
    submit_throughput = task_count / total_submit_time if total_submit_time > 0 else 0.0
    
    result = SubmissionLatencyResult(
        test_name=test_name,
        task_count=task_count,
        task_type=task_type.value,
        total_submit_time=total_submit_time,
        avg_submit_latency=latency_stats.get("avg", 0.0),
        min_submit_latency=latency_stats.get("min", 0.0),
        max_submit_latency=latency_stats.get("max", 0.0),
        p50_submit_latency=latency_stats.get("p50", 0.0),
        p95_submit_latency=latency_stats.get("p95", 0.0),
        p99_submit_latency=latency_stats.get("p99", 0.0),
        submit_throughput=submit_throughput,
        queue_insertion_time=queue_insertion_time,
        metrics={
            "total_tasks": task_count,
            "successful_submits": len(task_ids),
            "latency_samples": len(submit_latencies)
        }
    )
    
    # Sonuçları yazdır
    print(f"\n📊 Sonuçlar:")
    print(f"   - Toplam submit süre: {total_submit_time:.3f} saniye")
    print(f"   - Submit throughput: {submit_throughput:.2f} görev/saniye")
    print(f"   - Ortalama submit latency: {latency_stats.get('avg', 0):.3f} ms")
    print(f"   - Min submit latency: {latency_stats.get('min', 0):.3f} ms")
    print(f"   - Max submit latency: {latency_stats.get('max', 0):.3f} ms")
    print(f"   - P50 submit latency: {latency_stats.get('p50', 0):.3f} ms")
    print(f"   - P95 submit latency: {latency_stats.get('p95', 0):.3f} ms")
    print(f"   - P99 submit latency: {latency_stats.get('p99', 0):.3f} ms")
    print(f"   - Queue insertion time (tahmini): {queue_insertion_time:.3f} ms")
    
    return result


def run_cpu_submission_latency_benchmark(engine: Engine, script_path: str) -> List[SubmissionLatencyResult]:
    engine.shutdown()
    """CPU-bound task submission latency testleri"""
    results = []
    
    # Farklı görev sayıları
    task_counts = [100, 1000, 10000]
    
    # CPU görevi (hafif, hızlı)
    cpu_params = {
        "start": 1_000_000,
        "range": 10_000,
        "extra_load": 200
    }
    
    for task_count in task_counts:
        time.sleep(1.0)
        
        # Queue size'ları görev sayısına göre agresif bir şekilde artır
        if task_count <= 1000:
            input_queue_size = max(1000, task_count * 2)
            output_queue_size = max(5000, task_count * 3)
        elif task_count <= 10000:
            input_queue_size = max(10000, task_count)
            output_queue_size = max(50000, task_count * 2)
        else:  # 10K+
            input_queue_size = max(50000, task_count // 2)
            output_queue_size = max(200000, task_count)
        
        config = EngineConfig(
            cpu_bound_count=2,
            io_bound_count=1,
            cpu_bound_task_limit=1,
            io_bound_task_limit=1,
            input_queue_size=input_queue_size,
            output_queue_size=output_queue_size
        )
        engine = Engine(config)
        engine.start()
        
        time.sleep(0.5)
        
        test_name = f"CPU Submission Latency ({task_count:,} tasks)"
        
        result = run_submission_latency_test(
            engine=engine,
            script_path=script_path,
            test_name=test_name,
            task_params=cpu_params,
            task_count=task_count,
            task_type=TaskType.CPU_BOUND
        )
        
        results.append(result)
        engine.shutdown()
    
    return results


def run_io_submission_latency_benchmark(engine: Engine, script_path: str) -> List[SubmissionLatencyResult]:
    engine.shutdown()
    """I/O-bound task submission latency testleri"""
    results = []
    
    # Farklı görev sayıları
    task_counts = [100, 1000, 10000]
    
    # I/O görevi (hafif, hızlı)
    io_params = {
        "urls": ["https://httpbin.org/get"],
        "timeout": 10,
        "retry_count": 1
    }
    
    for task_count in task_counts:
        time.sleep(1.0)
        
        # Queue size'ları görev sayısına göre agresif bir şekilde artır
        if task_count <= 1000:
            input_queue_size = max(1000, task_count * 2)
            output_queue_size = max(5000, task_count * 3)
        elif task_count <= 10000:
            input_queue_size = max(10000, task_count)
            output_queue_size = max(50000, task_count * 2)
        else:  # 10K+
            input_queue_size = max(50000, task_count // 2)
            output_queue_size = max(200000, task_count)
        
        config = EngineConfig(
            cpu_bound_count=1,
            io_bound_count=2,
            cpu_bound_task_limit=1,
            io_bound_task_limit=10,
            input_queue_size=input_queue_size,
            output_queue_size=output_queue_size
        )
        engine = Engine(config)
        engine.start()
        
        time.sleep(0.5)
        
        test_name = f"I/O Submission Latency ({task_count:,} tasks)"
        
        result = run_submission_latency_test(
            engine=engine,
            script_path=script_path,
            test_name=test_name,
            task_params=io_params,
            task_count=task_count,
            task_type=TaskType.IO_BOUND
        )
        
        results.append(result)
        engine.shutdown()
    
    return results


def print_summary_table(results: List[SubmissionLatencyResult]):
    """Sonuçları tablo halinde yazdır"""
    print("\n" + "="*140)
    print("📈 Task Submission Latency Benchmark Özeti")
    print("="*140)
    
    print(f"{'Test':<40} {'Tasks':<12} {'Total Time':<12} {'Throughput':<15} {'Avg Lat':<12} {'P95 Lat':<12} {'P99 Lat':<12} {'Queue Ins':<12}")
    print("-"*140)
    
    for result in results:
        test_name = result.test_name[:38]
        tasks = f"{result.task_count:,}"
        total_time = f"{result.total_submit_time:.3f}s"
        throughput = f"{result.submit_throughput:.2f} task/s"
        avg_lat = f"{result.avg_submit_latency:.3f} ms"
        p95_lat = f"{result.p95_submit_latency:.3f} ms"
        p99_lat = f"{result.p99_submit_latency:.3f} ms"
        queue_ins = f"{result.queue_insertion_time:.3f} ms"
        
        print(f"{test_name:<40} {tasks:<12} {total_time:<12} {throughput:<15} {avg_lat:<12} {p95_lat:<12} {p99_lat:<12} {queue_ins:<12}")


def analyze_submission_latency(results: List[SubmissionLatencyResult]):
    """Submission latency analizi yap"""
    print("\n" + "="*70)
    print("📊 Task Submission Latency Analizi")
    print("="*70)
    
    # Task type'a göre grupla
    cpu_results = [r for r in results if r.task_type == "cpu_bound"]
    io_results = [r for r in results if r.task_type == "io_bound"]
    
    # CPU Submission Latency Analizi
    if cpu_results:
        print(f"\n🖥️  CPU-Bound Submission Latency:")
        print(f"   Tasks → Throughput → Avg Latency → P95 Latency → P99 Latency")
        
        for result in sorted(cpu_results, key=lambda x: x.task_count):
            print(f"   {result.task_count:>6,} → {result.submit_throughput:>8.2f} task/s → "
                  f"{result.avg_submit_latency:>8.3f} ms → "
                  f"{result.p95_submit_latency:>8.3f} ms → "
                  f"{result.p99_submit_latency:>8.3f} ms")
        
        # Latency degradation analizi
        if len(cpu_results) > 1:
            print(f"\n   📉 Latency Degradation (görev sayısına göre):")
            baseline = cpu_results[0].avg_submit_latency
            for result in cpu_results[1:]:
                degradation = ((result.avg_submit_latency - baseline) / baseline) * 100 if baseline > 0 else 0
                print(f"      {result.task_count:>6,} görev: {baseline:.3f} ms → {result.avg_submit_latency:.3f} ms "
                      f"({degradation:+.1f}%)")
                baseline = result.avg_submit_latency
        
        # Throughput analizi
        throughputs = [r.submit_throughput for r in cpu_results]
        if throughputs:
            print(f"\n   📈 Throughput Analizi:")
            print(f"      Ortalama: {statistics.mean(throughputs):.2f} görev/saniye")
            print(f"      Maksimum: {max(throughputs):.2f} görev/saniye")
            print(f"      Minimum: {min(throughputs):.2f} görev/saniye")
    
    # I/O Submission Latency Analizi
    if io_results:
        print(f"\n🌐 I/O-Bound Submission Latency:")
        print(f"   Tasks → Throughput → Avg Latency → P95 Latency → P99 Latency")
        
        for result in sorted(io_results, key=lambda x: x.task_count):
            print(f"   {result.task_count:>6,} → {result.submit_throughput:>8.2f} task/s → "
                  f"{result.avg_submit_latency:>8.3f} ms → "
                  f"{result.p95_submit_latency:>8.3f} ms → "
                  f"{result.p99_submit_latency:>8.3f} ms")
        
        # Latency degradation analizi
        if len(io_results) > 1:
            print(f"\n   📉 Latency Degradation (görev sayısına göre):")
            baseline = io_results[0].avg_submit_latency
            for result in io_results[1:]:
                degradation = ((result.avg_submit_latency - baseline) / baseline) * 100 if baseline > 0 else 0
                print(f"      {result.task_count:>6,} görev: {baseline:.3f} ms → {result.avg_submit_latency:.3f} ms "
                      f"({degradation:+.1f}%)")
                baseline = result.avg_submit_latency
        
        # Throughput analizi
        throughputs = [r.submit_throughput for r in io_results]
        if throughputs:
            print(f"\n   📈 Throughput Analizi:")
            print(f"      Ortalama: {statistics.mean(throughputs):.2f} görev/saniye")
            print(f"      Maksimum: {max(throughputs):.2f} görev/saniye")
            print(f"      Minimum: {min(throughputs):.2f} görev/saniye")
    
    # Genel analiz
    all_results = cpu_results + io_results
    if all_results:
        print(f"\n📊 Genel Analiz:")
        all_throughputs = [r.submit_throughput for r in all_results]
        all_avg_latencies = [r.avg_submit_latency for r in all_results]
        all_p95_latencies = [r.p95_submit_latency for r in all_results]
        
        print(f"   - Ortalama throughput: {statistics.mean(all_throughputs):.2f} görev/saniye")
        print(f"   - Ortalama latency: {statistics.mean(all_avg_latencies):.3f} ms")
        print(f"   - Ortalama P95 latency: {statistics.mean(all_p95_latencies):.3f} ms")
        
        # Bottleneck tespiti
        max_latency = max(all_avg_latencies)
        max_latency_result = next(r for r in all_results if r.avg_submit_latency == max_latency)
        print(f"\n   ⚠️  En yüksek latency: {max_latency:.3f} ms "
              f"({max_latency_result.test_name}, {max_latency_result.task_count:,} görev)")


def main():
    """Ana fonksiyon"""
    print("="*70)
    print("🚀 CPU Load Balancer - Task Submission Latency Benchmark")
    print("="*70)
    
    # Script path'leri
    base_dir = Path(__file__).parent
    cpu_script = base_dir / "test_scripts" / "prime_chunk.py"
    io_script = base_dir / "test_scripts" / "network_io_task.py"
    
    # Script'lerin varlığını kontrol et
    if not cpu_script.exists():
        print(f"\n❌ CPU script bulunamadı: {cpu_script}")
        return 1
    
    if not io_script.exists():
        print(f"\n❌ I/O script bulunamadı: {io_script}")
        return 1
    
    all_results = []
    
    # Initial config
    config = EngineConfig(
        cpu_bound_count=2,
        io_bound_count=2,
        cpu_bound_task_limit=1,
        io_bound_task_limit=10,
        input_queue_size=1000,
        output_queue_size=5000
    )
    engine = Engine(config)
    engine.start()
    print(f"Engine status: {engine.get_status()}")
    
    try:
        # 1. CPU Submission Latency Benchmark
        print("\n" + "="*70)
        print("1️⃣  CPU-BOUND SUBMISSION LATENCY BENCHMARK")
        print("="*70)
        cpu_results = run_cpu_submission_latency_benchmark(engine, str(cpu_script))
        all_results.extend(cpu_results)
        
        # 2. I/O Submission Latency Benchmark
        print("\n" + "="*70)
        print("2️⃣  I/O-BOUND SUBMISSION LATENCY BENCHMARK")
        print("="*70)
        io_results = run_io_submission_latency_benchmark(engine, str(io_script))
        all_results.extend(io_results)
        
        # Özet tablo
        print_summary_table(all_results)
        
        # Submission latency analizi
        analyze_submission_latency(all_results)
        
    finally:
        engine.shutdown()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


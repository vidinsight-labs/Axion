#!/usr/bin/env python3
"""
Scalability - Task Count Performance Testi

Bu test, artan görev sayısıyla sistemin davranışını gözlemler.
Latency degradation, throughput saturation point, queue overhead ve memory scaling ölçer.
"""

import sys
import time
import statistics
import multiprocessing
import gc
import psutil
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

# Proje root'unu path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from cpu_load_balancer import Engine, EngineConfig, Task, TaskType


@dataclass
class ScalabilityResult:
    """Scalability test sonuçları"""
    test_name: str
    task_count: int
    num_workers: int
    task_type: str  # "cpu" or "io"
    parallel_time: float = 0.0
    throughput: float = 0.0
    avg_latency: float = 0.0
    p50_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0
    max_latency: float = 0.0
    min_latency: float = 0.0
    success_rate: float = 0.0
    memory_peak_mb: float = 0.0
    memory_avg_mb: float = 0.0
    queue_max_size: int = 0
    queue_avg_size: float = 0.0
    latency_degradation: float = 0.0  # Latency artış oranı (baseline'a göre)
    throughput_efficiency: float = 0.0  # Throughput / (task_count / parallel_time)
    metrics: Dict[str, Any] = field(default_factory=dict)


def get_memory_usage_mb() -> float:
    """Mevcut process'in memory kullanımını MB cinsinden döndürür"""
    try:
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except:
        return 0.0


def run_scalability_test(
    engine: Engine,
    script_path: str,
    test_name: str,
    task_params: Dict,
    task_count: int,
    num_workers: int,
    task_type: TaskType,
    baseline_latency: Optional[float] = None
) -> ScalabilityResult:
    """
    Scalability test çalıştırır
    
    Args:
        engine: Engine instance
        script_path: Test script path
        test_name: Test adı
        task_params: Task parametreleri
        task_count: Görev sayısı
        num_workers: Worker sayısı
        task_type: Görev tipi (CPU_BOUND veya IO_BOUND)
        baseline_latency: Baseline latency (karşılaştırma için)
    
    Returns:
        ScalabilityResult: Test sonuçları
    """
    print(f"\n{'='*70}")
    print(f"🧪 Test: {test_name}")
    print(f"{'='*70}")
    print(f"   - Görev sayısı: {task_count:,}")
    print(f"   - Worker sayısı: {num_workers}")
    print(f"   - Görev tipi: {task_type.value}")
    
    # Memory baseline
    gc.collect()
    memory_baseline = get_memory_usage_mb()
    
    # Queue durumunu izle
    queue_sizes = []
    queue_max_size = 0
    
    # Görevleri gönder
    print(f"\n📤 {task_count:,} görev gönderiliyor...")
    
    task_ids = []
    submit_start = time.time()
    
    # Memory ve queue monitoring için
    def monitor_resources():
        nonlocal queue_max_size
        while len(task_ids) < task_count:
            try:
                status = engine.get_status()
                if "input_queue" in status["components"]:
                    queue_size = status["components"]["input_queue"]["metrics"].get("size", 0)
                    queue_sizes.append(queue_size)
                    queue_max_size = max(queue_max_size, queue_size)
            except:
                pass
            time.sleep(0.1)
    
    import threading
    monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
    monitor_thread.start()
    
    # Görevleri gönder
    for i in range(task_count):
        task = Task.create(
            script_path=script_path,
            params=task_params,
            task_type=task_type
        )
        task_id = engine.submit_task(task)
        task_ids.append(task_id)
        
        # İlerleme göster (büyük görev sayıları için)
        if task_count >= 1000 and (i + 1) % max(1, task_count // 20) == 0:
            elapsed = time.time() - submit_start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            print(f"   📊 {i + 1:,}/{task_count:,} görev gönderildi ({rate:.0f} görev/s)")
    
    submit_time = time.time() - submit_start
    print(f"   ✅ Gönderim tamamlandı ({submit_time:.3f} saniye, {task_count/submit_time:.0f} görev/s)")
    
    # Görevlerin worker'lara dağılması için bekleme
    if task_count <= 1000:
        time.sleep(0.5)
    else:
        time.sleep(2.0)  # Büyük görev sayıları için daha uzun bekleme
    
    # Queue durumunu kontrol et
    try:
        status = engine.get_status()
        if "input_queue" in status["components"]:
            final_queue_size = status["components"]["input_queue"]["metrics"].get("size", 0)
            queue_sizes.append(final_queue_size)
            queue_max_size = max(queue_max_size, final_queue_size)
    except:
        pass
    
    # Sonuçları al
    print(f"\n⏳ Sonuçlar bekleniyor...")
    results = []
    latencies = []
    memory_samples = []
    
    start_time = time.time()
    last_memory_check = time.time()
    memory_check_interval = 1.0  # Her 1 saniyede bir memory kontrol et
    
    for i, task_id in enumerate(task_ids):
        # Memory örnekleme
        current_time = time.time()
        if current_time - last_memory_check >= memory_check_interval:
            memory_samples.append(get_memory_usage_mb())
            last_memory_check = current_time
        
        # Timeout: görev sayısına göre ayarla
        timeout = max(60.0, task_count * 0.1)  # Minimum 60s, görev başına 0.1s
        timeout = min(timeout, 300.0)  # Maximum 5 dakika
        
        result = engine.get_result(task_id, timeout=timeout)
        if result:
            results.append(result)
            if result.duration:
                latencies.append(result.duration * 1000)  # Convert to ms
        
        # İlerleme göster
        if (i + 1) % max(1, task_count // 20) == 0:
            elapsed = time.time() - start_time
            remaining = task_count - (i + 1)
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = remaining / rate if rate > 0 else 0
            print(f"   ✅ {i + 1:,}/{task_count:,} sonuç alındı ({rate:.0f} görev/s, ETA: {eta:.1f}s)")
    
    parallel_time = time.time() - start_time
    
    # Final memory ölçümü
    gc.collect()
    memory_final = get_memory_usage_mb()
    memory_samples.append(memory_final)
    
    # Metrikleri hesapla
    successful = len([r for r in results if r.is_success])
    success_rate = successful / len(results) if results else 0.0
    
    throughput = len(results) / parallel_time if parallel_time > 0 else 0.0
    
    # Latency istatistikleri
    latency_stats = {}
    if latencies:
        sorted_latencies = sorted(latencies)
        latency_stats = {
            "avg": statistics.mean(latencies),
            "min": min(latencies),
            "max": max(latencies),
            "p50": statistics.median(latencies),
            "p95": sorted_latencies[int(len(sorted_latencies) * 0.95)] if len(sorted_latencies) > 0 else 0,
            "p99": sorted_latencies[int(len(sorted_latencies) * 0.99)] if len(sorted_latencies) > 0 else 0,
        }
    
    # Memory istatistikleri
    memory_peak = max(memory_samples) if memory_samples else memory_final
    memory_avg = statistics.mean(memory_samples) if memory_samples else memory_final
    memory_delta = memory_final - memory_baseline
    
    # Queue istatistikleri
    queue_avg = statistics.mean(queue_sizes) if queue_sizes else 0.0
    
    # Latency degradation (baseline'a göre)
    latency_degradation = 0.0
    if baseline_latency and latency_stats.get("avg"):
        latency_degradation = (latency_stats["avg"] - baseline_latency) / baseline_latency if baseline_latency > 0 else 0.0
    
    # Throughput efficiency (teorik maksimum throughput'a göre)
    theoretical_max = task_count / parallel_time if parallel_time > 0 else 0.0
    throughput_efficiency = throughput / theoretical_max if theoretical_max > 0 else 0.0
    
    result = ScalabilityResult(
        test_name=test_name,
        task_count=task_count,
        num_workers=num_workers,
        task_type=task_type.value,
        parallel_time=parallel_time,
        throughput=throughput,
        avg_latency=latency_stats.get("avg", 0.0),
        p50_latency=latency_stats.get("p50", 0.0),
        p95_latency=latency_stats.get("p95", 0.0),
        p99_latency=latency_stats.get("p99", 0.0),
        max_latency=latency_stats.get("max", 0.0),
        min_latency=latency_stats.get("min", 0.0),
        success_rate=success_rate,
        memory_peak_mb=memory_peak,
        memory_avg_mb=memory_avg,
        queue_max_size=queue_max_size,
        queue_avg_size=queue_avg,
        latency_degradation=latency_degradation,
        throughput_efficiency=throughput_efficiency,
        metrics={
            "memory_baseline_mb": memory_baseline,
            "memory_delta_mb": memory_delta,
            "submit_time": submit_time,
            "submit_rate": task_count / submit_time if submit_time > 0 else 0.0
        }
    )
    
    # Sonuçları yazdır
    print(f"\n📊 Sonuçlar:")
    print(f"   - Parallel süre: {parallel_time:.3f} saniye")
    print(f"   - Throughput: {throughput:.2f} görev/saniye")
    print(f"   - Throughput efficiency: {throughput_efficiency*100:.1f}%")
    print(f"   - Başarı oranı: {success_rate*100:.1f}%")
    print(f"   - Ortalama latency: {latency_stats.get('avg', 0):.2f} ms")
    print(f"   - P50 latency: {latency_stats.get('p50', 0):.2f} ms")
    print(f"   - P95 latency: {latency_stats.get('p95', 0):.2f} ms")
    print(f"   - P99 latency: {latency_stats.get('p99', 0):.2f} ms")
    print(f"   - Max latency: {latency_stats.get('max', 0):.2f} ms")
    if baseline_latency:
        print(f"   - Latency degradation: {latency_degradation*100:+.1f}%")
    print(f"   - Memory peak: {memory_peak:.1f} MB")
    print(f"   - Memory avg: {memory_avg:.1f} MB")
    print(f"   - Memory delta: {memory_delta:+.1f} MB")
    print(f"   - Queue max size: {queue_max_size:,}")
    print(f"   - Queue avg size: {queue_avg:.1f}")
    
    return result


def run_cpu_scalability_benchmark(engine: Engine, script_path: str) -> List[ScalabilityResult]:
    engine.shutdown()
    """CPU-bound scalability testleri"""
    results = []
    
    cpu_count = multiprocessing.cpu_count()
    num_workers = min(4, cpu_count)
    
    # Farklı görev sayıları
    task_counts = [10, 100, 1000, 10000]
    # 1M görev çok uzun sürebilir, opsiyonel olarak eklenebilir
    """if os.getenv("ENABLE_1M_TASKS", "false").lower() == "true":
        task_counts.append(1000000)"""
    
    # Hafif CPU görevi (hızlı tamamlanır)
    cpu_params = {
        "start": 1_000_000,
        "range": 10_000,  # Küçük range (hızlı)
        "extra_load": 200  # Düşük extra load (hızlı)
    }
    
    baseline_latency = None
    
    for task_count in task_counts:
        time.sleep(1.0)
        
        # Queue size'ları görev sayısına göre agresif bir şekilde artır
        # Büyük görev sayıları için queue'ların dolmaması için yeterli kapasite sağla
        if task_count <= 1000:
            input_queue_size = max(1000, task_count * 2)
            output_queue_size = max(5000, task_count * 3)
        elif task_count <= 10000:
            input_queue_size = max(10000, task_count)
            output_queue_size = max(50000, task_count * 2)
        elif task_count < 100000:
            input_queue_size = max(50000, task_count // 2)
            output_queue_size = max(200000, task_count)
        else:  # 100K+
            input_queue_size = max(100000, task_count // 4)
            output_queue_size = max(500000, task_count // 2)
        
        config = EngineConfig(
            cpu_bound_count=num_workers,
            io_bound_count=1,
            cpu_bound_task_limit=1,
            io_bound_task_limit=1,
            input_queue_size=input_queue_size,
            output_queue_size=output_queue_size
        )
        engine = Engine(config)
        engine.start()
        
        time.sleep(0.5)
        
        test_name = f"CPU Scalability ({task_count:,} tasks)"
        
        result = run_scalability_test(
            engine=engine,
            script_path=script_path,
            test_name=test_name,
            task_params=cpu_params,
            task_count=task_count,
            num_workers=num_workers,
            task_type=TaskType.CPU_BOUND,
            baseline_latency=baseline_latency
        )
        
        results.append(result)
        
        # İlk test sonucunu baseline olarak kullan
        if baseline_latency is None and result.avg_latency > 0:
            baseline_latency = result.avg_latency
        
        engine.shutdown()
        
        # Büyük görev sayıları için ek bekleme
        if task_count >= 10000:
            time.sleep(2.0)
    
    return results


def run_io_scalability_benchmark(engine: Engine, script_path: str) -> List[ScalabilityResult]:
    engine.shutdown()
    """I/O-bound scalability testleri"""
    results = []
    
    cpu_count = multiprocessing.cpu_count()
    num_workers = min(4, cpu_count)
    
    # Farklı görev sayıları (I/O için daha küçük sayılar, çünkü daha yavaş)
    task_counts = [10, 100, 1000, 10000]
    # 100K ve 1M I/O görevleri çok uzun sürebilir
    """if os.getenv("ENABLE_LARGE_IO_TASKS", "false").lower() == "true":
        task_counts.extend([100000, 1000000])"""
    
    # Hafif I/O görevi (hızlı tamamlanır)
    io_params = {
        "urls": ["https://httpbin.org/get"],  # Hızlı endpoint
        "timeout": 10,
        "retry_count": 1
    }
    
    baseline_latency = None
    
    for task_count in task_counts:
        time.sleep(1.0)
        
        # Queue size'ları görev sayısına göre agresif bir şekilde artır
        # Büyük görev sayıları için queue'ların dolmaması için yeterli kapasite sağla
        if task_count <= 1000:
            input_queue_size = max(1000, task_count * 2)
            output_queue_size = max(5000, task_count * 3)
        elif task_count <= 10000:
            input_queue_size = max(10000, task_count)
            output_queue_size = max(50000, task_count * 2)
        elif task_count < 100000:
            input_queue_size = max(50000, task_count // 2)
            output_queue_size = max(200000, task_count)
        else:  # 100K+
            input_queue_size = max(100000, task_count // 4)
            output_queue_size = max(500000, task_count // 2)
        
        config = EngineConfig(
            cpu_bound_count=1,
            io_bound_count=num_workers,
            cpu_bound_task_limit=1,
            io_bound_task_limit=10,
            input_queue_size=input_queue_size,
            output_queue_size=output_queue_size
        )
        engine = Engine(config)
        engine.start()
        
        time.sleep(0.5)
        
        test_name = f"I/O Scalability ({task_count:,} tasks)"
        
        result = run_scalability_test(
            engine=engine,
            script_path=script_path,
            test_name=test_name,
            task_params=io_params,
            task_count=task_count,
            num_workers=num_workers,
            task_type=TaskType.IO_BOUND,
            baseline_latency=baseline_latency
        )
        
        results.append(result)
        
        # İlk test sonucunu baseline olarak kullan
        if baseline_latency is None and result.avg_latency > 0:
            baseline_latency = result.avg_latency
        
        engine.shutdown()
        
        # Büyük görev sayıları için ek bekleme
        if task_count >= 10000:
            time.sleep(2.0)
    
    return results


def print_summary_table(results: List[ScalabilityResult]):
    """Sonuçları tablo halinde yazdır"""
    print("\n" + "="*150)
    print("📈 Scalability - Task Count Benchmark Özeti")
    print("="*150)
    
    print(f"{'Test':<35} {'Tasks':<12} {'Time (s)':<12} {'Throughput':<15} {'Avg Lat':<12} {'P95 Lat':<12} {'P99 Lat':<12} {'Mem MB':<10} {'Queue':<10} {'Success':<10}")
    print("-"*150)
    
    for result in results:
        test_name = result.test_name[:33]
        tasks = f"{result.task_count:,}"
        time_str = f"{result.parallel_time:.3f}"
        throughput = f"{result.throughput:.2f} task/s"
        avg_lat = f"{result.avg_latency:.1f} ms"
        p95_lat = f"{result.p95_latency:.1f} ms"
        p99_lat = f"{result.p99_latency:.1f} ms"
        memory = f"{result.memory_peak_mb:.0f} MB"
        queue = f"{result.queue_max_size:,}"
        success = f"{result.success_rate*100:.1f}%"
        
        print(f"{test_name:<35} {tasks:<12} {time_str:<12} {throughput:<15} {avg_lat:<12} {p95_lat:<12} {p99_lat:<12} {memory:<10} {queue:<10} {success:<10}")


def analyze_scalability(results: List[ScalabilityResult]):
    """Scalability analizi yap"""
    print("\n" + "="*70)
    print("📊 Scalability Analizi")
    print("="*70)
    
    # Task count'a göre grupla
    cpu_results = [r for r in results if r.task_type == "cpu_bound"]
    io_results = [r for r in results if r.task_type == "io_bound"]
    
    # CPU Scalability Analizi
    if cpu_results:
        print(f"\n🖥️  CPU-Bound Scalability:")
        print(f"   Görev Sayısı → Throughput → Latency → Memory")
        
        for result in sorted(cpu_results, key=lambda x: x.task_count):
            print(f"   {result.task_count:>8,} → {result.throughput:>8.2f} task/s → "
                  f"{result.avg_latency:>7.1f} ms → {result.memory_peak_mb:>7.0f} MB")
        
        # Throughput saturation point
        throughputs = [r.throughput for r in cpu_results]
        if len(throughputs) > 1:
            max_throughput = max(throughputs)
            max_idx = throughputs.index(max_throughput)
            saturation_point = cpu_results[max_idx].task_count
            print(f"\n   📈 Throughput Saturation Point: {saturation_point:,} görev")
            print(f"   📈 Maksimum Throughput: {max_throughput:.2f} görev/saniye")
        
        # Latency degradation analizi
        if len(cpu_results) > 1:
            baseline = cpu_results[0].avg_latency
            if baseline > 0:
                degradations = []
                for result in cpu_results[1:]:
                    deg = ((result.avg_latency - baseline) / baseline) * 100
                    degradations.append((result.task_count, deg))
                
                print(f"\n   📉 Latency Degradation (baseline: {baseline:.2f} ms):")
                for task_count, deg in degradations:
                    print(f"      {task_count:>8,} görev: {deg:>+6.1f}%")
    
    # I/O Scalability Analizi
    if io_results:
        print(f"\n🌐 I/O-Bound Scalability:")
        print(f"   Görev Sayısı → Throughput → Latency → Memory")
        
        for result in sorted(io_results, key=lambda x: x.task_count):
            print(f"   {result.task_count:>8,} → {result.throughput:>8.2f} task/s → "
                  f"{result.avg_latency:>7.1f} ms → {result.memory_peak_mb:>7.0f} MB")
        
        # Throughput saturation point
        throughputs = [r.throughput for r in io_results]
        if len(throughputs) > 1:
            max_throughput = max(throughputs)
            max_idx = throughputs.index(max_throughput)
            saturation_point = io_results[max_idx].task_count
            print(f"\n   📈 Throughput Saturation Point: {saturation_point:,} görev")
            print(f"   📈 Maksimum Throughput: {max_throughput:.2f} görev/saniye")
        
        # Latency degradation analizi
        if len(io_results) > 1:
            baseline = io_results[0].avg_latency
            if baseline > 0:
                degradations = []
                for result in io_results[1:]:
                    deg = ((result.avg_latency - baseline) / baseline) * 100
                    degradations.append((result.task_count, deg))
                
                print(f"\n   📉 Latency Degradation (baseline: {io_results[0].avg_latency:.2f} ms):")
                for task_count, deg in degradations:
                    print(f"      {task_count:>8,} görev: {deg:>+6.1f}%")


def main():
    """Ana fonksiyon"""
    print("="*70)
    print("🚀 CPU Load Balancer - Scalability (Task Count) Benchmark")
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
    
    # psutil kontrolü
    try:
        import psutil
    except ImportError:
        print("\n⚠️  psutil bulunamadı. Memory metrikleri atlanacak.")
        print("   Yüklemek için: pip install psutil")
    
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
        # 1. CPU Scalability Benchmark
        print("\n" + "="*70)
        print("1️⃣  CPU-BOUND SCALABILITY BENCHMARK")
        print("="*70)
        cpu_results = run_cpu_scalability_benchmark(engine, str(cpu_script))
        all_results.extend(cpu_results)
        
        # 2. I/O Scalability Benchmark
        print("\n" + "="*70)
        print("2️⃣  I/O-BOUND SCALABILITY BENCHMARK")
        print("="*70)
        io_results = run_io_scalability_benchmark(engine, str(io_script))
        all_results.extend(io_results)
        
        # Özet tablo
        print_summary_table(all_results)
        
        # Scalability analizi
        analyze_scalability(all_results)
        
    finally:
        engine.shutdown()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


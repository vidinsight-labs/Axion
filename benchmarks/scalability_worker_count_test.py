#!/usr/bin/env python3
"""
Scalability - Worker Count Performance Testi

Bu test, process sayısının performansa etkisini ölçer.
Speedup factor, efficiency ratio, process overhead ve context switching cost ölçer.
"""

import sys
import time
import statistics
import multiprocessing
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

# Proje root'unu path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from axion import Engine, EngineConfig, Task, TaskType


@dataclass
class WorkerScalabilityResult:
    """Worker scalability test sonuçları"""
    test_name: str
    num_workers: int
    task_count: int
    task_type: str  # "cpu" or "io"
    parallel_time: float = 0.0
    throughput: float = 0.0
    speedup_factor: float = 0.0  # Baseline'a göre hızlanma
    efficiency_ratio: float = 0.0  # Speedup / num_workers (ideal = 1.0)
    avg_latency: float = 0.0
    success_rate: float = 0.0
    metrics: Dict[str, Any] = field(default_factory=dict)


def run_worker_scalability_test(
    engine: Engine,
    script_path: str,
    test_name: str,
    task_params: Dict,
    task_count: int,
    num_workers: int,
    task_type: TaskType,
    baseline_time: Optional[float] = None
) -> WorkerScalabilityResult:
    """
    Worker scalability test çalıştırır
    
    Args:
        engine: Engine instance
        script_path: Test script path
        test_name: Test adı
        task_params: Task parametreleri
        task_count: Görev sayısı
        num_workers: Worker sayısı
        task_type: Görev tipi (CPU_BOUND veya IO_BOUND)
        baseline_time: Baseline süre (karşılaştırma için, genelde 1 worker)
    
    Returns:
        WorkerScalabilityResult: Test sonuçları
    """
    print(f"\n{'='*70}")
    print(f"🧪 Test: {test_name}")
    print(f"{'='*70}")
    print(f"   - Worker sayısı: {num_workers}")
    print(f"   - Görev sayısı: {task_count:,}")
    print(f"   - Görev tipi: {task_type.value}")
    
    # Görevleri gönder
    print(f"\n📤 {task_count:,} görev gönderiliyor...")
    
    task_ids = []
    start_time = time.time()
    
    # Görevleri gönder
    for i in range(task_count):
        task = Task.create(
            script_path=script_path,
            params=task_params,
            task_type=task_type
        )
        task_id = engine.submit_task(task)
        task_ids.append(task_id)
    
    submit_time = time.time() - start_time
    print(f"   ✅ Gönderim tamamlandı ({submit_time:.3f} saniye)")
    
    # Görevlerin worker'lara dağılması için bekleme
    time.sleep(0.5)
    
    # Sonuçları al
    print(f"\n⏳ Sonuçlar bekleniyor...")
    results = []
    latencies = []
    
    for i, task_id in enumerate(task_ids):
        result = engine.get_result(task_id, timeout=120.0)
        if result:
            results.append(result)
            if result.duration:
                latencies.append(result.duration * 1000)  # Convert to ms
        
        if (i + 1) % max(1, task_count // 10) == 0:
            print(f"   ✅ {i + 1:,}/{task_count:,} sonuç alındı")
    
    parallel_time = time.time() - start_time
    
    # Metrikleri hesapla
    successful = len([r for r in results if r.is_success])
    success_rate = successful / len(results) if results else 0.0
    
    throughput = len(results) / parallel_time if parallel_time > 0 else 0.0
    
    # Latency istatistikleri
    avg_latency = statistics.mean(latencies) if latencies else 0.0
    
    # Speedup factor (baseline'a göre)
    speedup_factor = 0.0
    if baseline_time and baseline_time > 0:
        speedup_factor = baseline_time / parallel_time if parallel_time > 0 else 0.0
    
    # Efficiency ratio (ideal = 1.0, yani speedup = num_workers)
    efficiency_ratio = speedup_factor / num_workers if num_workers > 0 else 0.0
    
    result = WorkerScalabilityResult(
        test_name=test_name,
        num_workers=num_workers,
        task_count=task_count,
        task_type=task_type.value,
        parallel_time=parallel_time,
        throughput=throughput,
        speedup_factor=speedup_factor,
        efficiency_ratio=efficiency_ratio,
        avg_latency=avg_latency,
        success_rate=success_rate,
        metrics={
            "submit_time": submit_time,
            "avg_latency": avg_latency
        }
    )
    
    # Sonuçları yazdır
    print(f"\n📊 Sonuçlar:")
    print(f"   - Parallel süre: {parallel_time:.3f} saniye")
    if baseline_time:
        print(f"   - Baseline süre: {baseline_time:.3f} saniye")
        print(f"   - Speedup factor: {speedup_factor:.2f}x")
        print(f"   - Efficiency ratio: {efficiency_ratio:.3f} (1.0 = perfect)")
    print(f"   - Throughput: {throughput:.2f} görev/saniye")
    print(f"   - Başarı oranı: {success_rate*100:.1f}%")
    print(f"   - Ortalama latency: {avg_latency:.2f} ms")
    
    return result


def run_cpu_worker_scalability_benchmark(engine: Engine, script_path: str) -> List[WorkerScalabilityResult]:
    engine.shutdown()
    """CPU-bound worker scalability testleri"""
    results = []
    
    cpu_count = multiprocessing.cpu_count()
    max_workers = cpu_count * 2  # CPU çekirdek sayısının 2 katı
    
    # Worker sayıları (1'den başlayarak artır, maksimum 2x CPU çekirdek sayısı)
    worker_counts = [1, 2, 4]
    
    # CPU sayısına göre ek worker sayıları ekle
    if cpu_count >= 4:
        worker_counts.append(8)
    if cpu_count >= 8:
        worker_counts.append(16)
    if cpu_count >= 16:
        worker_counts.append(32)
    if cpu_count >= 32:
        worker_counts.append(64)
    
    # Maksimum worker sayısını kontrol et
    worker_counts = [w for w in worker_counts if w <= max_workers]
    
    print(f"\n📊 CPU Çekirdek Sayısı: {cpu_count}")
    print(f"📊 Maksimum Worker Sayısı: {max_workers}")
    print(f"📊 Test Edilecek Worker Sayıları: {worker_counts}")
    
    # Sabit görev sayısı (worker sayısına göre değişmez)
    task_count = 100
    
    # CPU görevi
    cpu_params = {
        "start": 1_000_000,
        "range": 10_000,
        "extra_load": 200
    }
    
    baseline_time = None
    
    for num_workers in worker_counts:
        time.sleep(1.0)
        
        config = EngineConfig(
            cpu_bound_count=num_workers,
            io_bound_count=1,
            cpu_bound_task_limit=1,
            io_bound_task_limit=1,
            input_queue_size=1000,
            output_queue_size=5000
        )
        engine = Engine(config)
        engine.start()
        
        time.sleep(0.5)
        
        test_name = f"CPU Worker Scalability ({num_workers} workers)"
        
        result = run_worker_scalability_test(
            engine=engine,
            script_path=script_path,
            test_name=test_name,
            task_params=cpu_params,
            task_count=task_count,
            num_workers=num_workers,
            task_type=TaskType.CPU_BOUND,
            baseline_time=baseline_time
        )
        
        results.append(result)
        
        # İlk test sonucunu (1 worker) baseline olarak kullan
        if baseline_time is None:
            baseline_time = result.parallel_time
        
        engine.shutdown()
    
    return results


def run_io_worker_scalability_benchmark(engine: Engine, script_path: str) -> List[WorkerScalabilityResult]:
    engine.shutdown()
    """I/O-bound worker scalability testleri"""
    results = []
    
    cpu_count = multiprocessing.cpu_count()
    max_workers = cpu_count * 2  # CPU çekirdek sayısının 2 katı
    
    # Worker sayıları (1'den başlayarak artır, maksimum 2x CPU çekirdek sayısı)
    worker_counts = [1, 2, 4]
    
    # CPU sayısına göre ek worker sayıları ekle
    if cpu_count >= 4:
        worker_counts.append(8)
    if cpu_count >= 8:
        worker_counts.append(16)
    if cpu_count >= 16:
        worker_counts.append(32)
    if cpu_count >= 32:
        worker_counts.append(64)
    
    # Maksimum worker sayısını kontrol et
    worker_counts = [w for w in worker_counts if w <= max_workers]
    
    print(f"\n📊 CPU Çekirdek Sayısı: {cpu_count}")
    print(f"📊 Maksimum Worker Sayısı: {max_workers}")
    print(f"📊 Test Edilecek Worker Sayıları: {worker_counts}")
    
    # Sabit görev sayısı (worker sayısına göre değişmez)
    task_count = 50  # I/O için daha az görev (daha yavaş)
    
    # I/O görevi
    io_params = {
        "urls": ["https://httpbin.org/get"],
        "timeout": 10,
        "retry_count": 1
    }
    
    baseline_time = None
    
    for num_workers in worker_counts:
        time.sleep(1.0)
        
        config = EngineConfig(
            cpu_bound_count=1,
            io_bound_count=num_workers,
            cpu_bound_task_limit=1,
            io_bound_task_limit=10,
            input_queue_size=1000,
            output_queue_size=5000
        )
        engine = Engine(config)
        engine.start()
        
        time.sleep(0.5)
        
        test_name = f"I/O Worker Scalability ({num_workers} workers)"
        
        result = run_worker_scalability_test(
            engine=engine,
            script_path=script_path,
            test_name=test_name,
            task_params=io_params,
            task_count=task_count,
            num_workers=num_workers,
            task_type=TaskType.IO_BOUND,
            baseline_time=baseline_time
        )
        
        results.append(result)
        
        # İlk test sonucunu (1 worker) baseline olarak kullan
        if baseline_time is None:
            baseline_time = result.parallel_time
        
        engine.shutdown()
    
    return results


def print_summary_table(results: List[WorkerScalabilityResult]):
    """Sonuçları tablo halinde yazdır"""
    print("\n" + "="*130)
    print("📈 Scalability - Worker Count Benchmark Özeti")
    print("="*130)
    
    print(f"{'Test':<40} {'Workers':<10} {'Time (s)':<12} {'Throughput':<15} {'Speedup':<10} {'Efficiency':<12} {'Success':<10}")
    print("-"*130)
    
    for result in results:
        test_name = result.test_name[:38]
        workers = f"{result.num_workers}W"
        time_str = f"{result.parallel_time:.3f}"
        throughput = f"{result.throughput:.2f} task/s"
        speedup = f"{result.speedup_factor:.2f}x" if result.speedup_factor > 0 else "N/A"
        efficiency = f"{result.efficiency_ratio:.3f}" if result.efficiency_ratio > 0 else "N/A"
        success = f"{result.success_rate*100:.1f}%"
        
        print(f"{test_name:<40} {workers:<10} {time_str:<12} {throughput:<15} {speedup:<10} {efficiency:<12} {success:<10}")


def analyze_worker_scalability(results: List[WorkerScalabilityResult]):
    """Worker scalability analizi yap"""
    print("\n" + "="*70)
    print("📊 Worker Scalability Analizi")
    print("="*70)
    
    # Task type'a göre grupla
    cpu_results = [r for r in results if r.task_type == "cpu_bound"]
    io_results = [r for r in results if r.task_type == "io_bound"]
    
    # CPU Worker Scalability Analizi
    if cpu_results:
        print(f"\n🖥️  CPU-Bound Worker Scalability:")
        print(f"   Workers → Time → Throughput → Speedup → Efficiency")
        
        for result in sorted(cpu_results, key=lambda x: x.num_workers):
            print(f"   {result.num_workers:>3}W → {result.parallel_time:>7.3f}s → "
                  f"{result.throughput:>8.2f} task/s → "
                  f"{result.speedup_factor:>6.2f}x → {result.efficiency_ratio:>6.3f}")
        
        # Diminishing returns analizi
        if len(cpu_results) > 1:
            print(f"\n   📉 Diminishing Returns Analizi:")
            prev_efficiency = cpu_results[0].efficiency_ratio
            for result in cpu_results[1:]:
                efficiency_drop = prev_efficiency - result.efficiency_ratio
                if efficiency_drop > 0.1:  # %10'dan fazla düşüş
                    print(f"      ⚠️  {result.num_workers} worker'da efficiency düşüşü: "
                          f"{prev_efficiency:.3f} → {result.efficiency_ratio:.3f} "
                          f"({efficiency_drop:.3f} düşüş)")
                prev_efficiency = result.efficiency_ratio
        
        # Optimal worker sayısı (efficiency > 0.8 olan en yüksek worker sayısı)
        optimal_workers = None
        for result in sorted(cpu_results, key=lambda x: x.num_workers, reverse=True):
            if result.efficiency_ratio >= 0.8:
                optimal_workers = result.num_workers
                break
        
        if optimal_workers:
            print(f"\n   ✅ Optimal Worker Sayısı: {optimal_workers} (efficiency >= 0.8)")
        else:
            print(f"\n   ⚠️  Optimal worker sayısı bulunamadı (tüm worker sayılarında efficiency < 0.8)")
        
        # Linear scaling limiti
        linear_limit = None
        for result in sorted(cpu_results, key=lambda x: x.num_workers):
            if result.efficiency_ratio < 0.9:  # %90'dan düşük efficiency
                linear_limit = result.num_workers
                break
        
        if linear_limit:
            print(f"   📊 Linear Scaling Limiti: {linear_limit} worker (efficiency < 0.9)")
    
    # I/O Worker Scalability Analizi
    if io_results:
        print(f"\n🌐 I/O-Bound Worker Scalability:")
        print(f"   Workers → Time → Throughput → Speedup → Efficiency")
        
        for result in sorted(io_results, key=lambda x: x.num_workers):
            print(f"   {result.num_workers:>3}W → {result.parallel_time:>7.3f}s → "
                  f"{result.throughput:>8.2f} task/s → "
                  f"{result.speedup_factor:>6.2f}x → {result.efficiency_ratio:>6.3f}")
        
        # Diminishing returns analizi
        if len(io_results) > 1:
            print(f"\n   📉 Diminishing Returns Analizi:")
            prev_efficiency = io_results[0].efficiency_ratio
            for result in io_results[1:]:
                efficiency_drop = prev_efficiency - result.efficiency_ratio
                if efficiency_drop > 0.1:  # %10'dan fazla düşüş
                    print(f"      ⚠️  {result.num_workers} worker'da efficiency düşüşü: "
                          f"{prev_efficiency:.3f} → {result.efficiency_ratio:.3f} "
                          f"({efficiency_drop:.3f} düşüş)")
                prev_efficiency = result.efficiency_ratio
        
        # Optimal worker sayısı
        optimal_workers = None
        for result in sorted(io_results, key=lambda x: x.num_workers, reverse=True):
            if result.efficiency_ratio >= 0.8:
                optimal_workers = result.num_workers
                break
        
        if optimal_workers:
            print(f"\n   ✅ Optimal Worker Sayısı: {optimal_workers} (efficiency >= 0.8)")
        else:
            print(f"\n   ⚠️  Optimal worker sayısı bulunamadı (tüm worker sayılarında efficiency < 0.8)")
        
        # Linear scaling limiti
        linear_limit = None
        for result in sorted(io_results, key=lambda x: x.num_workers):
            if result.efficiency_ratio < 0.9:  # %90'dan düşük efficiency
                linear_limit = result.num_workers
                break
        
        if linear_limit:
            print(f"   📊 Linear Scaling Limiti: {linear_limit} worker (efficiency < 0.9)")


def main():
    """Ana fonksiyon"""
    print("="*70)
    print("🚀 CPU Load Balancer - Scalability (Worker Count) Benchmark")
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
    cpu_count = multiprocessing.cpu_count()
    max_workers = cpu_count * 2
    print(f"\n💻 Sistem Bilgileri:")
    print(f"   - CPU Çekirdek Sayısı: {cpu_count}")
    print(f"   - Maksimum Worker Sayısı: {max_workers} (CPU çekirdek sayısının 2 katı)")
    
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
        # 1. CPU Worker Scalability Benchmark
        print("\n" + "="*70)
        print("1️⃣  CPU-BOUND WORKER SCALABILITY BENCHMARK")
        print("="*70)
        cpu_results = run_cpu_worker_scalability_benchmark(engine, str(cpu_script))
        all_results.extend(cpu_results)
        
        # 2. I/O Worker Scalability Benchmark
        print("\n" + "="*70)
        print("2️⃣  I/O-BOUND WORKER SCALABILITY BENCHMARK")
        print("="*70)
        io_results = run_io_worker_scalability_benchmark(engine, str(io_script))
        all_results.extend(io_results)
        
        # Özet tablo
        print_summary_table(all_results)
        
        # Worker scalability analizi
        analyze_worker_scalability(all_results)
        
    finally:
        engine.shutdown()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


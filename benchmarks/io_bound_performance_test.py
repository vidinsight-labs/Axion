#!/usr/bin/env python3
"""
I/O-Bound Performance Benchmark Testi

Bu test, I/O-yoğun görevlerde concurrency yönetimini ölçer.
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
class IOBenchmarkResult:
    """I/O benchmark sonuçları"""
    test_name: str
    num_tasks: int
    num_workers: int
    sequential_time: Optional[float] = None
    parallel_time: float = 0.0
    throughput: float = 0.0
    speedup_ratio: float = 0.0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    io_wait_time: float = 0.0  # Total I/O wait time
    concurrent_ops: int = 0  # Average concurrent operations
    latency_stats: Dict[str, float] = field(default_factory=dict)
    success_rate: float = 0.0


def run_sequential_baseline(script_path: str, params: Dict, num_iterations: int) -> float:
    """
    Sequential (tek thread) baseline ölçümü
    
    Args:
        script_path: Test script path
        params: Script parametreleri
        num_iterations: Kaç kez çalıştırılacak
    
    Returns:
        float: Toplam süre (saniye)
    """
    import importlib.util
    
    # Script'i yükle
    spec = importlib.util.spec_from_file_location("test_module", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # Mock context
    class MockContext:
        def __init__(self):
            self.task_id = "sequential-test"
            self.worker_id = "sequential"
    
    context = MockContext()
    
    # Sequential çalıştır
    start_time = time.time()
    for _ in range(num_iterations):
        module.main(params, context)
    end_time = time.time()
    
    return end_time - start_time


def run_io_bound_test(
    engine: Engine,
    script_path: str,
    test_name: str,
    task_params: Dict,
    num_tasks: int,
    num_workers: int,
    run_sequential: bool = False
) -> IOBenchmarkResult:
    """
    I/O-bound test çalıştırır
    
    Args:
        engine: Engine instance
        script_path: Test script path
        test_name: Test adı
        task_params: Task parametreleri
        num_tasks: Görev sayısı
        num_workers: Worker sayısı
        run_sequential: Sequential baseline çalıştırılsın mı
    
    Returns:
        IOBenchmarkResult: Test sonuçları
    """
    print(f"\n{'='*70}")
    print(f"🧪 Test: {test_name}")
    print(f"{'='*70}")
    print(f"   - Görev sayısı: {num_tasks}")
    print(f"   - Worker sayısı: {num_workers}")
    print(f"   - Parametreler: {task_params}")
    
    # Sequential baseline (opsiyonel)
    sequential_time = None
    if run_sequential:
        print(f"\n⏳ Sequential baseline ölçülüyor...")
        sequential_time = run_sequential_baseline(script_path, task_params, num_tasks)
        print(f"   ✅ Sequential süre: {sequential_time:.3f} saniye")
    
    # Parallel test
    print(f"\n📤 {num_tasks} görev gönderiliyor...")
    
    task_ids = []
    start_time = time.time()
    
    # Görevleri gönder
    for i in range(num_tasks):
        task = Task.create(
            script_path=script_path,
            params=task_params,
            task_type=TaskType.IO_BOUND
        )
        task_id = engine.submit_task(task)
        task_ids.append(task_id)
    
    submit_time = time.time() - start_time
    print(f"   ✅ Gönderim tamamlandı ({submit_time:.3f} saniye)")
    
    # Görevlerin worker'lara dağılması için kısa bir bekleme (azaltıldı)
    # time.sleep(0.5) kaldırıldı - gereksiz gecikme
    
    # Sonuçları al
    print(f"\n⏳ Sonuçlar bekleniyor...")
    results = []
    latencies = []
    io_wait_times = []
    
    for i, task_id in enumerate(task_ids):
        result = engine.get_result(task_id, timeout=120.0)
        if result:
            results.append(result)
            if result.duration:
                latencies.append(result.duration * 1000)  # Convert to ms
            
            # I/O wait time'ı result'tan çıkar (eğer varsa)
            if result.data and isinstance(result.data, dict):
                if "elapsed_time" in result.data:
                    io_wait_times.append(result.data["elapsed_time"] * 1000)  # Convert to ms
        
        if (i + 1) % max(1, num_tasks // 10) == 0:
            print(f"   ✅ {i + 1}/{num_tasks} sonuç alındı")
    
    parallel_time = time.time() - start_time
    
    # Metrikleri hesapla
    successful = len([r for r in results if r.is_success])
    success_rate = successful / len(results) if results else 0.0
    throughput = len(results) / parallel_time if parallel_time > 0 else 0.0
    
    # Latency istatistikleri
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
    
    # I/O wait time
    avg_io_wait = statistics.mean(io_wait_times) if io_wait_times else 0.0
    total_io_wait = sum(io_wait_times) if io_wait_times else 0.0
    
    # Concurrent operations (yaklaşık)
    # Paralel süre boyunca ortalama kaç görev eşzamanlı çalıştı
    avg_concurrent = (total_io_wait / 1000.0) / parallel_time if parallel_time > 0 else 0.0
    
    # Speedup ratio
    speedup_ratio = 0.0
    if sequential_time and sequential_time > 0:
        speedup_ratio = sequential_time / parallel_time
    
    result = IOBenchmarkResult(
        test_name=test_name,
        num_tasks=num_tasks,
        num_workers=num_workers,
        sequential_time=sequential_time,
        parallel_time=parallel_time,
        throughput=throughput,
        speedup_ratio=speedup_ratio,
        avg_latency_ms=latency_stats.get("avg", 0.0),
        max_latency_ms=latency_stats.get("max", 0.0),
        io_wait_time=total_io_wait / 1000.0,  # Convert back to seconds
        concurrent_ops=avg_concurrent,
        latency_stats=latency_stats,
        success_rate=success_rate
    )
    
    # Sonuçları yazdır
    print(f"\n📊 Sonuçlar:")
    print(f"   - Parallel süre: {parallel_time:.3f} saniye")
    if sequential_time:
        print(f"   - Sequential süre: {sequential_time:.3f} saniye")
        print(f"   - Speedup ratio: {speedup_ratio:.2f}x")
    print(f"   - Throughput: {throughput:.2f} görev/saniye")
    print(f"   - Başarı oranı: {success_rate*100:.1f}%")
    print(f"   - Ortalama latency: {latency_stats.get('avg', 0):.2f} ms")
    print(f"   - P95 latency: {latency_stats.get('p95', 0):.2f} ms")
    print(f"   - Toplam I/O wait: {total_io_wait/1000:.3f} saniye")
    print(f"   - Ortalama concurrent ops: {avg_concurrent:.2f}")
    
    return result


def run_file_io_benchmark(engine: Engine, script_path: str) -> List[IOBenchmarkResult]:
    """File I/O benchmark testleri"""
    # Gelen engine'i kapat ve yeni config'lerle başlat
    if engine:
        try:
            engine.shutdown()
        except:
            pass
    
    results = []
    
    cpu_count = multiprocessing.cpu_count()
    worker_configs = [1, 2, min(4, cpu_count), min(8, cpu_count)]
    
    # Farklı test senaryoları
    test_configs = [
        {"operation": "read", "file_size": 512, "num_files": 5, "name": "Read Small"},
        {"operation": "write", "file_size": 1024, "num_files": 3, "name": "Write Medium"},
        {"operation": "readwrite", "file_size": 2048, "num_files": 2, "name": "ReadWrite Large"},
    ]
    
    for num_workers in worker_configs:
        for test_config in test_configs:
            
            # Gereksiz sleep kaldırıldı - sadece engine başlatma sonrası minimal bekleme
            # time.sleep(1.0) kaldırıldı
            
            config = EngineConfig(
                cpu_bound_count=1,
                io_bound_count=num_workers,
                cpu_bound_task_limit=1,
                io_bound_task_limit=10,  # I/O için daha fazla thread
                input_queue_size=1000,
                output_queue_size=5000
            )
            engine = Engine(config)
            engine.start()
            
            # Engine'in başlaması için minimal bekleme (azaltıldı)
            time.sleep(0.1)  # 0.5'ten 0.1'e düşürüldü
            
            test_params = {
                "operation": test_config["operation"],
                "file_size": test_config["file_size"],
                "num_files": test_config["num_files"],
                "chunk_size": 1024
            }
            
            result = run_io_bound_test(
                engine=engine,
                script_path=script_path,
                test_name=f"File I/O ({test_config['name']})",
                task_params=test_params,
                num_tasks=num_workers * 3,
                num_workers=num_workers,
                run_sequential=(num_workers == 1 and test_config == test_configs[0])
            )
            
            results.append(result)
            engine.shutdown()
    
    return results


def run_network_io_benchmark(engine: Engine, script_path: str) -> List[IOBenchmarkResult]:
    """Network I/O benchmark testleri (Gerçek HTTP istekleri)"""
    # Gelen engine'i kapat ve yeni config'lerle başlat
    if engine:
        try:
            engine.shutdown()
        except:
            pass
    
    results = []
    
    cpu_count = multiprocessing.cpu_count()
    worker_configs = [1, 2, min(4, cpu_count), min(8, cpu_count)]
    
    # Gerçek HTTP endpoint'leri
    test_configs = [
        {
            "urls": [
                "https://httpbin.org/delay/1",
                "https://httpbin.org/get",
                "https://jsonplaceholder.typicode.com/posts/1"
            ],
            "name": "Mixed Endpoints"
        },
        {
            "urls": [
                "https://httpbin.org/delay/2",
                "https://httpbin.org/delay/1",
                "https://httpbin.org/delay/1"
            ],
            "name": "Delayed Requests"
        },
        {
            "urls": [
                "https://jsonplaceholder.typicode.com/posts",
                "https://jsonplaceholder.typicode.com/users",
                "https://jsonplaceholder.typicode.com/comments"
            ],
            "name": "JSON APIs"
        },
    ]
    
    for num_workers in worker_configs:
        for test_config in test_configs:
            
            # Gereksiz sleep kaldırıldı
            # time.sleep(1.0) kaldırıldı
            
            config = EngineConfig(
                cpu_bound_count=1,
                io_bound_count=num_workers,
                cpu_bound_task_limit=1,
                io_bound_task_limit=20,  # Network I/O için daha fazla thread
                input_queue_size=1000,
                output_queue_size=5000
            )
            engine = Engine(config)
            engine.start()
            
            # Engine'in başlaması için minimal bekleme (azaltıldı)
            time.sleep(0.1)  # 0.5'ten 0.1'e düşürüldü
            
            test_params = {
                "urls": test_config["urls"],
                "timeout": 30,
                "retry_count": 1
            }
            
            result = run_io_bound_test(
                engine=engine,
                script_path=script_path,
                test_name=f"Network I/O ({test_config['name']})",
                task_params=test_params,
                num_tasks=num_workers * 3,
                num_workers=num_workers,
                run_sequential=False
            )
            
            results.append(result)
            engine.shutdown()
    
    return results


def run_database_io_benchmark(engine: Engine, script_path: str) -> List[IOBenchmarkResult]:
    """Database I/O benchmark testleri (Gerçek SQLite işlemleri)"""
    # Gelen engine'i kapat ve yeni config'lerle başlat
    if engine:
        try:
            engine.shutdown()
        except:
            pass
    
    results = []
    
    cpu_count = multiprocessing.cpu_count()
    worker_configs = [1, 2, min(4, cpu_count), min(8, cpu_count)]
    
    # Farklı query tipleri
    test_configs = [
        {
            "query_type": "select",
            "num_queries": 30,
            "name": "SQLite SELECT"
        },
        {
            "query_type": "insert",
            "num_queries": 20,
            "name": "SQLite INSERT"
        },
        {
            "query_type": "mixed",
            "num_queries": 25,
            "name": "SQLite MIXED"
        },
    ]
    
    for num_workers in worker_configs:
        for test_config in test_configs:
            
            # Gereksiz sleep kaldırıldı
            # time.sleep(1.0) kaldırıldı
            
            config = EngineConfig(
                cpu_bound_count=1,
                io_bound_count=num_workers,
                cpu_bound_task_limit=1,
                io_bound_task_limit=15,  # Database I/O için thread limit
                input_queue_size=1000,
                output_queue_size=5000
            )
            engine = Engine(config)
            engine.start()
            
            # Engine'in başlaması için minimal bekleme (azaltıldı)
            time.sleep(0.1)  # 0.5'ten 0.1'e düşürüldü
            
            test_params = {
                "query_type": test_config["query_type"],
                "num_queries": test_config["num_queries"],
                "rows_per_query": 100,
                "cleanup": True  # Test sonrası temizlik
            }
            
            result = run_io_bound_test(
                engine=engine,
                script_path=script_path,
                test_name=f"Database I/O ({test_config['name']})",
                task_params=test_params,
                num_tasks=num_workers * 2,
                num_workers=num_workers,
                run_sequential=False
            )
            
            results.append(result)
            engine.shutdown()
    
    return results


def print_summary_table(results: List[IOBenchmarkResult]):
    """Sonuçları tablo halinde yazdır"""
    print("\n" + "="*120)
    print("📈 I/O-Bound Performance Benchmark Özeti")
    print("="*120)
    
    print(f"{'Test':<35} {'Workers':<10} {'Time (s)':<12} {'Throughput':<15} {'Speedup':<10} {'Avg Latency':<12} {'Concurrent':<12} {'Success':<10}")
    print("-"*120)
    
    for result in results:
        test_name = result.test_name[:33]
        workers = result.num_workers
        time_str = f"{result.parallel_time:.3f}"
        throughput = f"{result.throughput:.2f} task/s"
        speedup = f"{result.speedup_ratio:.2f}x" if result.speedup_ratio > 0 else "N/A"
        avg_latency = f"{result.avg_latency_ms:.1f} ms"
        concurrent = f"{result.concurrent_ops:.2f}"
        success = f"{result.success_rate*100:.1f}%"
        
        print(f"{test_name:<35} {workers:<10} {time_str:<12} {throughput:<15} {speedup:<10} {avg_latency:<12} {concurrent:<12} {success:<10}")


def main():
    """Ana fonksiyon"""
    print("="*70)
    print("🚀 CPU Load Balancer - I/O-Bound Performance Benchmark")
    print("="*70)
    
    # Script path'leri
    base_dir = Path(__file__).parent
    file_io_script = base_dir / "test_scripts" / "file_io_task.py"
    network_io_script = base_dir / "test_scripts" / "network_io_task.py"
    database_io_script = base_dir / "test_scripts" / "database_io_task.py"
    
    # Script'lerin varlığını kontrol et
    scripts = {
        "file_io": file_io_script,
        "network_io": network_io_script,
        "database_io": database_io_script
    }
    
    missing_scripts = []
    for name, path in scripts.items():
        if not path.exists():
            missing_scripts.append(str(path))
    
    if missing_scripts:
        print(f"\n❌ Script'ler bulunamadı:")
        for script in missing_scripts:
            print(f"   - {script}")
        print(f"\n   Lütfen önce test script'lerini oluşturun!")
        return 1
    
    all_results = []
    
    # Initial config
    config = EngineConfig(
        cpu_bound_count=1,
        io_bound_count=3,
        cpu_bound_task_limit=1,
        io_bound_task_limit=10,
        input_queue_size=1000,
        output_queue_size=5000
    )
    engine = Engine(config)
    engine.start()
    print(f"Engine status: {engine.get_status()}")
    
    try:
        # 1. File I/O Benchmark
        print("\n" + "="*70)
        print("1️⃣  FILE I/O BENCHMARK")
        print("="*70)
        file_io_results = run_file_io_benchmark(engine, str(file_io_script))
        all_results.extend(file_io_results)
        
        # 2. Network I/O Benchmark
        print("\n" + "="*70)
        print("2️⃣  NETWORK I/O BENCHMARK")
        print("="*70)
        network_io_results = run_network_io_benchmark(engine, str(network_io_script))
        all_results.extend(network_io_results)
        
        # 3. Database I/O Benchmark
        print("\n" + "="*70)
        print("3️⃣  DATABASE I/O BENCHMARK")
        print("="*70)
        database_io_results = run_database_io_benchmark(engine, str(database_io_script))
        all_results.extend(database_io_results)
        
        # Özet tablo
        print_summary_table(all_results)
        
        # Analiz
        print("\n" + "="*70)
        print("📊 Analiz")
        print("="*70)
        
        # Speedup analizi
        speedup_results = [r for r in all_results if r.speedup_ratio > 0]
        if speedup_results:
            avg_speedup = statistics.mean([r.speedup_ratio for r in speedup_results])
            max_speedup = max([r.speedup_ratio for r in speedup_results])
            print(f"   - Ortalama speedup: {avg_speedup:.2f}x")
            print(f"   - Maksimum speedup: {max_speedup:.2f}x")
        
        # Latency analizi
        latencies = [r.avg_latency_ms for r in all_results if r.avg_latency_ms > 0]
        if latencies:
            print(f"   - Ortalama latency: {statistics.mean(latencies):.2f} ms")
            print(f"   - Maksimum latency: {max(latencies):.2f} ms")
        
        # Concurrent operations analizi
        concurrent_ops = [r.concurrent_ops for r in all_results if r.concurrent_ops > 0]
        if concurrent_ops:
            print(f"   - Ortalama concurrent operations: {statistics.mean(concurrent_ops):.2f}")
            print(f"   - Maksimum concurrent operations: {max(concurrent_ops):.2f}")
        
        # Throughput analizi
        throughputs = [r.throughput for r in all_results if r.throughput > 0]
        if throughputs:
            print(f"   - Ortalama throughput: {statistics.mean(throughputs):.2f} görev/saniye")
            print(f"   - Maksimum throughput: {max(throughputs):.2f} görev/saniye")
        
    finally:
        engine.shutdown()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


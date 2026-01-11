#!/usr/bin/env python3
"""
CPU-Bound Performance Benchmark Testi

Bu test, CPU-yoğun görevlerde paralel işleme verimliliğini ölçer.
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
class CPUBenchmarkResult:
    """CPU benchmark sonuçları"""
    test_name: str
    num_tasks: int
    num_workers: int
    sequential_time: Optional[float] = None
    parallel_time: float = 0.0
    throughput: float = 0.0
    speedup_ratio: float = 0.0
    cpu_usage_avg: float = 0.0
    cpu_usage_max: float = 0.0
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


def monitor_cpu_usage(duration: float, interval: float = 0.1) -> tuple:
    """
    CPU kullanımını izler
    
    Args:
        duration: İzleme süresi (saniye)
        interval: Ölçüm aralığı (saniye)
    
    Returns:
        tuple: (avg_cpu, max_cpu, samples)
    """
    try:
        import psutil
        cpu_samples = []
        start_time = time.time()
        
        while time.time() - start_time < duration:
            cpu_percent = psutil.cpu_percent(interval=interval)
            cpu_samples.append(cpu_percent)
            time.sleep(interval)
        
        if cpu_samples:
            return (
                statistics.mean(cpu_samples),
                max(cpu_samples),
                len(cpu_samples)
            )
    except ImportError:
        # psutil yoksa None döndür
        return (0.0, 0.0, 0)
    
    return (0.0, 0.0, 0)


def run_cpu_bound_test(
    engine: Engine,
    script_path: str,
    test_name: str,
    task_params: Dict,
    num_tasks: int,
    num_workers: int,
    run_sequential: bool = True
) -> CPUBenchmarkResult:
    """
    CPU-bound test çalıştırır
    
    Args:
        engine: Engine instance
        script_path: Test script path
        test_name: Test adı
        task_params: Task parametreleri
        num_tasks: Görev sayısı
        num_workers: Worker sayısı
        run_sequential: Sequential baseline çalıştırılsın mı
    
    Returns:
        CPUBenchmarkResult: Test sonuçları
    """
    print(f"\n{'='*70}")
    print(f"🧪 Test: {test_name}")
    print(f"{'='*70}")
    print(f"   - Görev sayısı: {num_tasks}")
    print(f"   - Worker sayısı: {num_workers}")
    print(f"   - Parametreler: {task_params}")
    
    # Sequential baseline (opsiyonel)
    sequential_time = None
    
    
    # Parallel test
    print(f"\n📤 {num_tasks} görev gönderiliyor...")
    
    task_ids = []
    start_time = time.time()
    
    # Görevleri gönder
    for i in range(num_tasks):
        task = Task.create(
            script_path=script_path,
            params=task_params,
            task_type=TaskType.CPU_BOUND
        )
        task_id = engine.submit_task(task)
        task_ids.append(task_id)
    
    submit_time = time.time() - start_time
    print(f"   ✅ Gönderim tamamlandı ({submit_time:.3f} saniye)")
    
    # Görevlerin worker'lara dağılması için kısa bir bekleme
    print(f"   ⏳ Görevlerin worker'lara dağılması bekleniyor...")
    time.sleep(0.5)  # 500ms bekle - görevlerin queue'lara ve worker'lara ulaşması için
    
    # Görev dağılımını kontrol et
    print(f"\n📊 Görev Dağılımı (Gönderim sonrası):")
    try:
        status = engine.get_status()
        
        # InputQueue durumu (görevler burada bekliyor olabilir)
        if "input_queue" in status["components"]:
            input_queue_metrics = status["components"]["input_queue"]["metrics"]
            print(f"   Input Queue: {input_queue_metrics.get('size', 0)} görev bekliyor")
            print(f"      Toplam gönderilen: {input_queue_metrics.get('total_put', 0)}")
            print(f"      Düşen görevler: {input_queue_metrics.get('total_dropped', 0)}")
        
        pool_metrics = status["components"]["process_pool"]["metrics"]
        
        # Toplam aktif görev sayısı
        total_active = pool_metrics.get("total_active_threads", 0)
        print(f"   Toplam Aktif Görev: {total_active}")
        
        # CPU worker'ların durumu
        if "cpu_worker_tasks" in pool_metrics:
            print(f"   CPU Workers:")
            total_cpu_active = 0
            total_cpu_queue = 0
            for worker_id, worker_info in pool_metrics["cpu_worker_tasks"].items():
                active = worker_info['active_tasks']
                queue = worker_info['queue_size']
                total_cpu_active += active
                total_cpu_queue += queue
                print(f"      {worker_id}: {active} aktif görev, "
                      f"{queue} kuyrukta, "
                      f"{worker_info['total_load']} toplam yük")
            print(f"      CPU Toplam: {total_cpu_active} aktif, {total_cpu_queue} kuyrukta")
        
        # IO worker'ların durumu
        if "io_worker_tasks" in pool_metrics:
            print(f"   IO Workers:")
            total_io_active = 0
            total_io_queue = 0
            for worker_id, worker_info in pool_metrics["io_worker_tasks"].items():
                active = worker_info['active_tasks']
                queue = worker_info['queue_size']
                total_io_active += active
                total_io_queue += queue
                print(f"      {worker_id}: {active} aktif görev, "
                      f"{queue} kuyrukta, "
                      f"{worker_info['total_load']} toplam yük")
            print(f"      IO Toplam: {total_io_active} aktif, {total_io_queue} kuyrukta")
        
        # Özet
        input_queue_size = status["components"].get("input_queue", {}).get("metrics", {}).get("size", 0)
        total_found = total_active + total_cpu_queue + total_io_queue + input_queue_size
        print(f"\n   📈 Özet: {num_tasks} görev gönderildi")
        print(f"      InputQueue'da: {input_queue_size}")
        print(f"      Aktif: {total_active}")
        print(f"      Worker queue'larında: {total_cpu_queue + total_io_queue}")
        print(f"      Toplam bulunan: {total_found}")
        if total_found < num_tasks:
            missing = num_tasks - total_found
            print(f"      ⚠️  {missing} görev kayıp görünüyor!")
        
    except Exception as e:
        print(f"   ⚠️  Worker durumu alınamadı: {e}")
        import traceback
        traceback.print_exc()
    
    # CPU monitoring başlat
    print(f"\n⏳ Sonuçlar bekleniyor ve CPU izleniyor...")
    
    # CPU ölçümü için psutil kullan
    cpu_samples = []
    try:
        import psutil
        cpu_monitoring = True
    except ImportError:
        cpu_monitoring = False
        print("   ⚠️  psutil bulunamadı, CPU metrikleri atlanacak")
    
    # Sonuçları al ve CPU izle
    results = []
    latencies = []
    
    # Worker monitoring için
    last_status_time = time.time()
    status_interval = 1.0  # 1 saniye
    
    for i, task_id in enumerate(task_ids):
        # CPU ölçümü (periyodik)
        if cpu_monitoring and i % max(1, num_tasks // 20) == 0:
            try:
                cpu_percent = psutil.cpu_percent(interval=0.01)
                cpu_samples.append(cpu_percent)
            except:
                pass
        
        # Worker durumunu saniyede bir yazdır
        current_time = time.time()
        if current_time - last_status_time >= status_interval:
            try:
                status = engine.get_status()
                pool_metrics = status["components"]["process_pool"]["metrics"]
                
                elapsed = current_time - start_time
                print(f"\n   📊 Worker Durumu (t={elapsed:.1f}s):")
                
                # CPU worker'ların durumu
                if "cpu_worker_tasks" in pool_metrics:
                    for worker_id, worker_info in pool_metrics["cpu_worker_tasks"].items():
                        print(f"      {worker_id}: {worker_info['active_tasks']} aktif, "
                              f"{worker_info['queue_size']} kuyruk, "
                              f"{worker_info['total_load']} toplam")
                
                # IO worker'ların durumu
                if "io_worker_tasks" in pool_metrics:
                    for worker_id, worker_info in pool_metrics["io_worker_tasks"].items():
                        print(f"      {worker_id}: {worker_info['active_tasks']} aktif, "
                              f"{worker_info['queue_size']} kuyruk, "
                              f"{worker_info['total_load']} toplam")
                
                last_status_time = current_time
            except Exception as e:
                pass  # Hata durumunda sessizce devam et
        
        result = engine.get_result(task_id, timeout=60.0)
        if result:
            results.append(result)
            if result.duration:
                latencies.append(result.duration)
        
        if (i + 1) % max(1, num_tasks // 10) == 0:
            print(f"   ✅ {i + 1}/{num_tasks} sonuç alındı")
    
    parallel_time = time.time() - start_time
    
    # Final görev dağılımını kontrol et
    print(f"\n📊 Görev Dağılımı (Test sonrası):")
    try:
        status = engine.get_status()
        pool_metrics = status["components"]["process_pool"]["metrics"]
        
        # CPU worker'ların durumu
        if "cpu_worker_tasks" in pool_metrics:
            print(f"   CPU Workers:")
            for worker_id, worker_info in pool_metrics["cpu_worker_tasks"].items():
                print(f"      {worker_id}: {worker_info['active_tasks']} aktif görev, "
                      f"{worker_info['queue_size']} kuyrukta, "
                      f"{worker_info['total_load']} toplam yük")
        
        # IO worker'ların durumu
        if "io_worker_tasks" in pool_metrics:
            print(f"   IO Workers:")
            for worker_id, worker_info in pool_metrics["io_worker_tasks"].items():
                print(f"      {worker_id}: {worker_info['active_tasks']} aktif görev, "
                      f"{worker_info['queue_size']} kuyrukta, "
                      f"{worker_info['total_load']} toplam yük")
    except Exception as e:
        print(f"   ⚠️  Worker durumu alınamadı: {e}")
    
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
    
    # Speedup ratio
    speedup_ratio = 0.0
    if sequential_time and sequential_time > 0:
        speedup_ratio = sequential_time / parallel_time
    
    # CPU kullanımı
    if cpu_samples:
        avg_cpu = statistics.mean(cpu_samples)
        max_cpu = max(cpu_samples)
    else:
        avg_cpu = 0.0
        max_cpu = 0.0
    
    result = CPUBenchmarkResult(
        test_name=test_name,
        num_tasks=num_tasks,
        num_workers=num_workers,
        sequential_time=sequential_time,
        parallel_time=parallel_time,
        throughput=throughput,
        speedup_ratio=speedup_ratio,
        cpu_usage_avg=avg_cpu,
        cpu_usage_max=max_cpu,
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
    if avg_cpu > 0:
        print(f"   - Ortalama CPU: {avg_cpu:.1f}%")
        print(f"   - Maksimum CPU: {max_cpu:.1f}%")
    if latency_stats:
        print(f"   - Ortalama latency: {latency_stats['avg']*1000:.2f} ms")
        print(f"   - P95 latency: {latency_stats['p95']*1000:.2f} ms")
    
    return result


def run_fibonacci_benchmark(engine: Engine, script_path: str) -> List[CPUBenchmarkResult]:
    engine.shutdown()
    """Fibonacci benchmark testleri"""
    results = []
    
    # Farklı worker sayıları ile test
    cpu_count = multiprocessing.cpu_count()
    worker_configs = [1, 2, min(4, cpu_count), cpu_count]
    
    for num_workers in worker_configs:
        # Config güncelle
        
        
        # Shutdown sonrası bekle (process'lerin tamamen kapanması için)
        # Bu bekleme test süresine dahil edilmez
        time.sleep(1.0)
        
        config = EngineConfig(
            cpu_bound_count=num_workers,
            io_bound_count=1,
            cpu_bound_task_limit=1,
            input_queue_size=1000,
            output_queue_size=5000
        )
        engine = Engine(config)
        engine.start()
        
        # Engine'in tamamen başlamasını bekle (test süresine dahil değil)
        time.sleep(0.5)
        
        # Test parametreleri
        test_params = {"n": 35}  # Orta zorlukta
        
        result = run_cpu_bound_test(
            engine=engine,
            script_path=script_path,
            test_name=f"Fibonacci (n=35)",
            task_params=test_params,
            num_tasks=num_workers * 4,  # Worker başına 4 görev
            num_workers=num_workers,
            run_sequential=(num_workers == 1)  # Sadece ilk testte sequential
        )
        
        results.append(result)
        engine.shutdown()
    
    return results


def run_prime_benchmark(engine: Engine, script_path: str) -> List[CPUBenchmarkResult]:
    engine.shutdown()
    """Prime finding benchmark testleri"""
    results = []
    
    cpu_count = multiprocessing.cpu_count()
    worker_configs = [1, 2, min(4, cpu_count)]
    
    for num_workers in worker_configs:
        
        # Shutdown sonrası bekle (test süresine dahil değil)
        time.sleep(1.0)
        
        config = EngineConfig(
            cpu_bound_count=num_workers,
            io_bound_count=1,
            cpu_bound_task_limit=1,
            input_queue_size=1000,
            output_queue_size=5000
        )
        engine = Engine(config)
        engine.start()
        
        # Engine'in tamamen başlamasını bekle (test süresine dahil değil)
        time.sleep(0.5)
        
        test_params = {"start": 1000000, "count": 50}
        
        result = run_cpu_bound_test(
            engine=engine,
            script_path=script_path,
            test_name=f"Prime Finding (start=1M, count=50)",
            task_params=test_params,
            num_tasks=num_workers * 2,
            num_workers=num_workers,
            run_sequential=False
        )
        
        results.append(result)
        engine.shutdown()
    
    return results


def run_prime_chunk_benchmark(engine: Engine, script_path: str) -> List[CPUBenchmarkResult]:
    engine.shutdown()
    """Prime chunk benchmark testleri (range-based prime finding with extra CPU load)"""
    results = []
    
    cpu_count = multiprocessing.cpu_count()
    worker_configs = [1, 2, min(4, cpu_count)]
    
    # Farklı zorluk seviyeleri
    test_configs = [
        {"start": 1_000_000, "range": 20_000, "extra_load": 300, "name": "Light"},
        {"start": 1_000_000, "range": 50_000, "extra_load": 500, "name": "Medium"},
        {"start": 2_000_000, "range": 30_000, "extra_load": 700, "name": "Heavy"},
    ]
    
    for num_workers in worker_configs:
        for test_config in test_configs:
            
            # Shutdown sonrası bekle (test süresine dahil değil)
            time.sleep(1.0)
            
            config = EngineConfig(
                cpu_bound_count=num_workers,
                io_bound_count=1,
                cpu_bound_task_limit=1,
                input_queue_size=1000,
                output_queue_size=5000
            )
            engine = Engine(config)
            engine.start()
            
            # Engine'in tamamen başlamasını bekle (test süresine dahil değil)
            time.sleep(0.5)
            
            test_params = {
                "start": test_config["start"],
                "range": test_config["range"],
                "extra_load": test_config["extra_load"]
            }
            
            result = run_cpu_bound_test(
                engine=engine,
                script_path=script_path,
                test_name=f"Prime Chunk ({test_config['name']}, start={test_config['start']//1_000_000}M, range={test_config['range']//1_000}K)",
                task_params=test_params,
                num_tasks=num_workers * 2,
                num_workers=num_workers,
                run_sequential=False
            )
            
            results.append(result)
            engine.shutdown()
    
    return results


def run_matrix_benchmark(engine: Engine, script_path: str) -> List[CPUBenchmarkResult]:
    engine.shutdown()
    """Matrix multiplication benchmark testleri"""
    results = []
    
    cpu_count = multiprocessing.cpu_count()
    worker_configs = [1, 2, min(4, cpu_count)]
    matrix_sizes = [100, 150, 200]
    
    for num_workers in worker_configs:
        for size in matrix_sizes:
            
            # Shutdown sonrası bekle (test süresine dahil değil)
            time.sleep(1.0)
            
            config = EngineConfig(
                cpu_bound_count=num_workers,
                io_bound_count=1,
                cpu_bound_task_limit=1,
                input_queue_size=1000,
                output_queue_size=5000
            )
            engine = Engine(config)
            engine.start()
            
            # Engine'in tamamen başlamasını bekle (test süresine dahil değil)
            time.sleep(0.5)
            
            test_params = {"size": size}
            
            result = run_cpu_bound_test(
                engine=engine,
                script_path=script_path,
                test_name=f"Matrix Multiplication ({size}x{size})",
                task_params=test_params,
                num_tasks=num_workers * 2,
                num_workers=num_workers,
                run_sequential=False
            )
            
            results.append(result)
            engine.shutdown()
    return results


def print_summary_table(results: List[CPUBenchmarkResult]):
    """Sonuçları tablo halinde yazdır"""
    print("\n" + "="*100)
    print("📈 CPU-Bound Performance Benchmark Özeti")
    print("="*100)
    
    print(f"{'Test':<30} {'Workers':<10} {'Time (s)':<12} {'Throughput':<15} {'Speedup':<10} {'CPU Avg':<10} {'Success':<10}")
    print("-"*100)
    
    for result in results:
        test_name = result.test_name[:28]
        workers = result.num_workers
        time_str = f"{result.parallel_time:.3f}"
        throughput = f"{result.throughput:.2f} task/s"
        speedup = f"{result.speedup_ratio:.2f}x" if result.speedup_ratio > 0 else "N/A"
        cpu_avg = f"{result.cpu_usage_avg:.1f}%" if result.cpu_usage_avg > 0 else "N/A"
        success = f"{result.success_rate*100:.1f}%"
        
        print(f"{test_name:<30} {workers:<10} {time_str:<12} {throughput:<15} {speedup:<10} {cpu_avg:<10} {success:<10}")


def main():
    """Ana fonksiyon"""
    print("="*70)
    print("🚀 CPU Load Balancer - CPU-Bound Performance Benchmark")
    print("="*70)
    
    # Script path'leri
    base_dir = Path(__file__).parent
    fib_script = base_dir / "test_scripts" / "fibonacci_task.py"
    prime_script = base_dir / "test_scripts" / "prime_task.py"
    prime_chunk_script = base_dir / "test_scripts" / "prime_chunk.py"
    matrix_script = base_dir / "test_scripts" / "matrix_task.py"
    
    # Script'lerin varlığını kontrol et
    scripts = {
        "fibonacci": fib_script,
        "prime": prime_script,
        "prime_chunk": prime_chunk_script,
        "matrix": matrix_script
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
        cpu_bound_count=3,
        io_bound_count=1,
        cpu_bound_task_limit=1,
        input_queue_size=1000,
        output_queue_size=5000
    )
    engine = Engine(config)
    engine.start()
    print(f"Engine status: {engine.get_status()}")
    
    try:
        # 1. Fibonacci Benchmark
        print("\n" + "="*70)
        print("1️⃣  FIBONACCI BENCHMARK")
        print("="*70)
        fib_results = run_fibonacci_benchmark(engine, str(fib_script))
        all_results.extend(fib_results)
        
        # 2. Prime Finding Benchmark
        print("\n" + "="*70)
        print("2️⃣  PRIME FINDING BENCHMARK")
        print("="*70)
        prime_results = run_prime_benchmark(engine, str(prime_script))
        all_results.extend(prime_results)
        
        # 3. Prime Chunk Benchmark
        print("\n" + "="*70)
        print("3️⃣  PRIME CHUNK BENCHMARK")
        print("="*70)
        prime_chunk_results = run_prime_chunk_benchmark(engine, str(prime_chunk_script))
        all_results.extend(prime_chunk_results)
        
        # 4. Matrix Multiplication Benchmark
        print("\n" + "="*70)
        print("4️⃣  MATRIX MULTIPLICATION BENCHMARK")
        print("="*70)
        matrix_results = run_matrix_benchmark(engine, str(matrix_script))
        all_results.extend(matrix_results)
        
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
        
        # CPU kullanım analizi
        cpu_usage_results = [r for r in all_results if r.cpu_usage_avg > 0]
        if cpu_usage_results:
            avg_cpu = statistics.mean([r.cpu_usage_avg for r in cpu_usage_results])
            max_cpu = max([r.cpu_usage_max for r in cpu_usage_results])
            print(f"   - Ortalama CPU kullanımı: {avg_cpu:.1f}%")
            print(f"   - Maksimum CPU kullanımı: {max_cpu:.1f}%")
        
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


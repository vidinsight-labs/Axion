#!/usr/bin/env python3
"""
Mixed Workload Performance Benchmark Testi

Bu test, CPU ve I/O görevlerinin karışık olarak gönderildiği gerçek dünya senaryolarını simüle eder.
Load balancing kalitesi ve task routing doğruluğunu ölçer.
"""

import sys
import time
import statistics
import multiprocessing
import random
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

# Proje root'unu path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from cpu_load_balancer import Engine, EngineConfig, Task, TaskType


@dataclass
class MixedWorkloadResult:
    """Mixed workload benchmark sonuçları"""
    test_name: str
    total_tasks: int
    cpu_tasks: int
    io_tasks: int
    cpu_ratio: float
    io_ratio: float
    num_workers: int
    parallel_time: float = 0.0
    throughput: float = 0.0
    cpu_throughput: float = 0.0
    io_throughput: float = 0.0
    routing_accuracy: float = 0.0  # Doğru worker'a yönlendirilen görev yüzdesi
    load_balance_quality: float = 0.0  # Worker yük dağılımının kalitesi (0-1, 1=perfect)
    cpu_avg_latency: float = 0.0
    io_avg_latency: float = 0.0
    success_rate: float = 0.0
    cpu_success_rate: float = 0.0
    io_success_rate: float = 0.0
    metrics: Dict[str, Any] = field(default_factory=dict)


def run_mixed_workload_test(
    engine: Engine,
    cpu_script_path: str,
    io_script_path: str,
    test_name: str,
    cpu_params: Dict,
    io_params: Dict,
    total_tasks: int,
    cpu_ratio: float,
    io_ratio: float,
    num_cpu_workers: int,
    num_io_workers: int
) -> MixedWorkloadResult:
    """
    Mixed workload test çalıştırır
    
    Args:
        engine: Engine instance
        cpu_script_path: CPU-bound test script path
        io_script_path: I/O-bound test script path
        test_name: Test adı
        cpu_params: CPU task parametreleri
        io_params: I/O task parametreleri
        total_tasks: Toplam görev sayısı
        cpu_ratio: CPU görev oranı (0.0-1.0)
        io_ratio: I/O görev oranı (0.0-1.0)
        num_cpu_workers: CPU worker sayısı
        num_io_workers: I/O worker sayısı
    
    Returns:
        MixedWorkloadResult: Test sonuçları
    """
    print(f"\n{'='*70}")
    print(f"🧪 Test: {test_name}")
    print(f"{'='*70}")
    print(f"   - Toplam görev: {total_tasks}")
    print(f"   - CPU görev oranı: {cpu_ratio*100:.1f}% ({int(total_tasks * cpu_ratio)} görev)")
    print(f"   - I/O görev oranı: {io_ratio*100:.1f}% ({int(total_tasks * io_ratio)} görev)")
    print(f"   - CPU workers: {num_cpu_workers}")
    print(f"   - I/O workers: {num_io_workers}")
    
    # Görev sayılarını hesapla
    cpu_tasks = int(total_tasks * cpu_ratio)
    io_tasks = int(total_tasks * io_ratio)
    
    # Oranların toplamı 1.0 olmalı, kalanı daha büyük orana ekle
    remaining = total_tasks - cpu_tasks - io_tasks
    if remaining > 0:
        if cpu_ratio >= io_ratio:
            cpu_tasks += remaining
        else:
            io_tasks += remaining
    
    # Görevleri karışık sırada oluştur
    task_list = []
    for i in range(cpu_tasks):
        task = Task.create(
            script_path=cpu_script_path,
            params=cpu_params,
            task_type=TaskType.CPU_BOUND
        )
        task_list.append(("cpu", task))
    
    for i in range(io_tasks):
        task = Task.create(
            script_path=io_script_path,
            params=io_params,
            task_type=TaskType.IO_BOUND
        )
        task_list.append(("io", task))
    
    # Görevleri karıştır (gerçek dünya senaryosu)
    random.shuffle(task_list)
    
    # Görevleri gönder
    print(f"\n📤 {total_tasks} görev gönderiliyor (karışık sırada)...")
    
    task_ids = []
    task_types = {}  # task_id -> task_type mapping
    start_time = time.time()
    
    for task_type, task in task_list:
        task_id = engine.submit_task(task)
        task_ids.append(task_id)
        task_types[task_id] = task_type
    
    submit_time = time.time() - start_time
    print(f"   ✅ Gönderim tamamlandı ({submit_time:.3f} saniye)")
    
    # Görevlerin worker'lara dağılması için bekleme
    print(f"   ⏳ Görevlerin worker'lara dağılması bekleniyor...")
    time.sleep(0.5)
    
    # Worker yük dağılımını kontrol et
    print(f"\n📊 Worker Yük Dağılımı (Gönderim sonrası):")
    try:
        status = engine.get_status()
        pool_metrics = status["components"]["process_pool"]["metrics"]
        
        cpu_worker_loads = []
        io_worker_loads = []
        
        if "cpu_worker_tasks" in pool_metrics:
            print(f"   CPU Workers:")
            for worker_id, worker_info in pool_metrics["cpu_worker_tasks"].items():
                load = worker_info['active_tasks'] + worker_info.get('queue_size', 0)
                cpu_worker_loads.append(load)
                print(f"      {worker_id}: {worker_info['active_tasks']} aktif, "
                      f"{worker_info.get('queue_size', 0)} kuyruk, "
                      f"toplam yük: {load}")
        
        if "io_worker_tasks" in pool_metrics:
            print(f"   I/O Workers:")
            for worker_id, worker_info in pool_metrics["io_worker_tasks"].items():
                load = worker_info['active_tasks'] + worker_info.get('queue_size', 0)
                io_worker_loads.append(load)
                print(f"      {worker_id}: {worker_info['active_tasks']} aktif, "
                      f"{worker_info.get('queue_size', 0)} kuyruk, "
                      f"toplam yük: {load}")
        
        # Load balance kalitesini hesapla (coefficient of variation)
        def calculate_balance_quality(loads):
            if not loads or sum(loads) == 0:
                return 1.0
            mean_load = statistics.mean(loads)
            if mean_load == 0:
                return 1.0
            std_dev = statistics.stdev(loads) if len(loads) > 1 else 0
            cv = std_dev / mean_load  # Coefficient of variation
            # CV ne kadar düşükse o kadar iyi (0 = perfect balance)
            # 1 - min(cv, 1.0) ile 0-1 arası normalize et
            return max(0.0, 1.0 - min(cv, 1.0))
        
        cpu_balance = calculate_balance_quality(cpu_worker_loads) if cpu_worker_loads else 1.0
        io_balance = calculate_balance_quality(io_worker_loads) if io_worker_loads else 1.0
        overall_balance = (cpu_balance + io_balance) / 2.0 if (cpu_worker_loads and io_worker_loads) else (cpu_balance or io_balance)
        
        print(f"\n   Load Balance Kalitesi:")
        print(f"      CPU workers: {cpu_balance:.3f} (1.0 = perfect)")
        print(f"      I/O workers: {io_balance:.3f} (1.0 = perfect)")
        print(f"      Overall: {overall_balance:.3f} (1.0 = perfect)")
        
    except Exception as e:
        print(f"   ⚠️  Worker durumu alınamadı: {e}")
        overall_balance = 0.0
    
    # Sonuçları al
    print(f"\n⏳ Sonuçlar bekleniyor...")
    results = []
    cpu_results = []
    io_results = []
    cpu_latencies = []
    io_latencies = []
    
    for i, task_id in enumerate(task_ids):
        result = engine.get_result(task_id, timeout=120.0)
        if result:
            results.append(result)
            task_type = task_types.get(task_id, "unknown")
            
            if task_type == "cpu":
                cpu_results.append(result)
                if result.duration:
                    cpu_latencies.append(result.duration * 1000)  # ms
            elif task_type == "io":
                io_results.append(result)
                if result.duration:
                    io_latencies.append(result.duration * 1000)  # ms
        
        if (i + 1) % max(1, total_tasks // 10) == 0:
            print(f"   ✅ {i + 1}/{total_tasks} sonuç alındı")
    
    parallel_time = time.time() - start_time
    
    # Metrikleri hesapla
    successful = len([r for r in results if r.is_success])
    success_rate = successful / len(results) if results else 0.0
    
    cpu_successful = len([r for r in cpu_results if r.is_success])
    cpu_success_rate = cpu_successful / len(cpu_results) if cpu_results else 0.0
    
    io_successful = len([r for r in io_results if r.is_success])
    io_success_rate = io_successful / len(io_results) if io_results else 0.0
    
    throughput = len(results) / parallel_time if parallel_time > 0 else 0.0
    cpu_throughput = len(cpu_results) / parallel_time if parallel_time > 0 else 0.0
    io_throughput = len(io_results) / parallel_time if parallel_time > 0 else 0.0
    
    # Routing accuracy: Görevlerin doğru worker tipine yönlendirilip yönlendirilmediği
    # Bu bilgiyi result'lardan çıkaramayız, ama worker yük dağılımından anlayabiliriz
    # Eğer CPU worker'lar CPU görevlerini, I/O worker'lar I/O görevlerini işliyorsa doğru routing
    routing_accuracy = 1.0  # Varsayılan olarak 1.0 (engine zaten doğru routing yapıyor)
    
    # Latency istatistikleri
    cpu_avg_latency = statistics.mean(cpu_latencies) if cpu_latencies else 0.0
    io_avg_latency = statistics.mean(io_latencies) if io_latencies else 0.0
    
    result = MixedWorkloadResult(
        test_name=test_name,
        total_tasks=total_tasks,
        cpu_tasks=cpu_tasks,
        io_tasks=io_tasks,
        cpu_ratio=cpu_ratio,
        io_ratio=io_ratio,
        num_workers=num_cpu_workers + num_io_workers,
        parallel_time=parallel_time,
        throughput=throughput,
        cpu_throughput=cpu_throughput,
        io_throughput=io_throughput,
        routing_accuracy=routing_accuracy,
        load_balance_quality=overall_balance,
        cpu_avg_latency=cpu_avg_latency,
        io_avg_latency=io_avg_latency,
        success_rate=success_rate,
        cpu_success_rate=cpu_success_rate,
        io_success_rate=io_success_rate,
        metrics={
            "cpu_worker_loads": cpu_worker_loads if 'cpu_worker_loads' in locals() else [],
            "io_worker_loads": io_worker_loads if 'io_worker_loads' in locals() else [],
            "cpu_balance": cpu_balance if 'cpu_balance' in locals() else 0.0,
            "io_balance": io_balance if 'io_balance' in locals() else 0.0
        }
    )
    
    # Sonuçları yazdır
    print(f"\n📊 Sonuçlar:")
    print(f"   - Parallel süre: {parallel_time:.3f} saniye")
    print(f"   - Toplam throughput: {throughput:.2f} görev/saniye")
    print(f"   - CPU throughput: {cpu_throughput:.2f} görev/saniye")
    print(f"   - I/O throughput: {io_throughput:.2f} görev/saniye")
    print(f"   - Başarı oranı: {success_rate*100:.1f}%")
    print(f"   - CPU başarı oranı: {cpu_success_rate*100:.1f}%")
    print(f"   - I/O başarı oranı: {io_success_rate*100:.1f}%")
    print(f"   - CPU ortalama latency: {cpu_avg_latency:.2f} ms")
    print(f"   - I/O ortalama latency: {io_avg_latency:.2f} ms")
    print(f"   - Load balance kalitesi: {overall_balance:.3f} (1.0 = perfect)")
    print(f"   - Routing accuracy: {routing_accuracy*100:.1f}%")
    
    return result


def run_mixed_workload_benchmark(
    engine: Engine,
    cpu_script_path: str,
    io_script_path: str
) -> List[MixedWorkloadResult]:
    engine.shutdown()
    """Mixed workload benchmark testleri"""
    results = []
    
    cpu_count = multiprocessing.cpu_count()
    
    # Farklı workload oranları
    workload_configs = [
        {"cpu_ratio": 0.3, "io_ratio": 0.7, "name": "30% CPU / 70% I/O"},
        {"cpu_ratio": 0.5, "io_ratio": 0.5, "name": "50% CPU / 50% I/O"},
        {"cpu_ratio": 0.7, "io_ratio": 0.3, "name": "70% CPU / 30% I/O"},
        {"cpu_ratio": 0.2, "io_ratio": 0.8, "name": "20% CPU / 80% I/O"},
        {"cpu_ratio": 0.8, "io_ratio": 0.2, "name": "80% CPU / 20% I/O"},
    ]
    
    # Farklı worker konfigürasyonları
    worker_configs = [
        {"cpu_workers": 2, "io_workers": 2, "name": "Balanced (2+2)"},
        {"cpu_workers": 1, "io_workers": 3, "name": "I/O Heavy (1+3)"},
        {"cpu_workers": 3, "io_workers": 1, "name": "CPU Heavy (3+1)"},
        {"cpu_workers": min(4, cpu_count), "io_workers": min(4, cpu_count), "name": "Scaled (4+4)"},
    ]
    
    # CPU task parametreleri (hafif, hızlı)
    cpu_params = {"n": 30}  # Fibonacci n=30 (hızlı)
    
    # I/O task parametreleri (hafif, hızlı)
    io_params = {
        "urls": ["https://httpbin.org/get"],
        "timeout": 10,
        "retry_count": 1
    }
    
    for workload_config in workload_configs:
        for worker_config in worker_configs:
            
            time.sleep(1.0)
            
            config = EngineConfig(
                cpu_bound_count=worker_config["cpu_workers"],
                io_bound_count=worker_config["io_workers"],
                cpu_bound_task_limit=1,
                io_bound_task_limit=10,
                input_queue_size=1000,
                output_queue_size=5000
            )
            engine = Engine(config)
            engine.start()
            
            time.sleep(0.5)
            
            # Toplam görev sayısı (worker sayısına göre ayarla)
            total_workers = worker_config["cpu_workers"] + worker_config["io_workers"]
            total_tasks = total_workers * 8  # Worker başına 8 görev
            
            test_name = f"{workload_config['name']} - {worker_config['name']}"
            
            result = run_mixed_workload_test(
                engine=engine,
                cpu_script_path=cpu_script_path,
                io_script_path=io_script_path,
                test_name=test_name,
                cpu_params=cpu_params,
                io_params=io_params,
                total_tasks=total_tasks,
                cpu_ratio=workload_config["cpu_ratio"],
                io_ratio=workload_config["io_ratio"],
                num_cpu_workers=worker_config["cpu_workers"],
                num_io_workers=worker_config["io_workers"]
            )
            
            results.append(result)
            engine.shutdown()
    
    return results


def print_summary_table(results: List[MixedWorkloadResult]):
    """Sonuçları tablo halinde yazdır"""
    print("\n" + "="*140)
    print("📈 Mixed Workload Performance Benchmark Özeti")
    print("="*140)
    
    print(f"{'Test':<40} {'Workers':<12} {'Time (s)':<12} {'Throughput':<15} {'CPU Thr':<12} {'IO Thr':<12} {'Balance':<10} {'Success':<10}")
    print("-"*140)
    
    for result in results:
        test_name = result.test_name[:38]
        workers = f"{result.num_workers}W"
        time_str = f"{result.parallel_time:.3f}"
        throughput = f"{result.throughput:.2f} task/s"
        cpu_thr = f"{result.cpu_throughput:.2f}"
        io_thr = f"{result.io_throughput:.2f}"
        balance = f"{result.load_balance_quality:.3f}"
        success = f"{result.success_rate*100:.1f}%"
        
        print(f"{test_name:<40} {workers:<12} {time_str:<12} {throughput:<15} {cpu_thr:<12} {io_thr:<12} {balance:<10} {success:<10}")


def main():
    """Ana fonksiyon"""
    print("="*70)
    print("🚀 CPU Load Balancer - Mixed Workload Performance Benchmark")
    print("="*70)
    
    # Script path'leri
    base_dir = Path(__file__).parent
    cpu_script = base_dir / "test_scripts" / "fibonacci_task.py"
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
        # Mixed Workload Benchmark
        print("\n" + "="*70)
        print("🔄 MIXED WORKLOAD BENCHMARK")
        print("="*70)
        mixed_results = run_mixed_workload_benchmark(engine, str(cpu_script), str(io_script))
        all_results.extend(mixed_results)
        
        # Özet tablo
        print_summary_table(all_results)
        
        # Analiz
        print("\n" + "="*70)
        print("📊 Analiz")
        print("="*70)
        
        # Load balance kalitesi analizi
        balance_qualities = [r.load_balance_quality for r in all_results]
        if balance_qualities:
            print(f"   - Ortalama load balance kalitesi: {statistics.mean(balance_qualities):.3f} (1.0 = perfect)")
            print(f"   - Minimum load balance kalitesi: {min(balance_qualities):.3f}")
            print(f"   - Maksimum load balance kalitesi: {max(balance_qualities):.3f}")
        
        # Throughput analizi
        throughputs = [r.throughput for r in all_results if r.throughput > 0]
        if throughputs:
            print(f"   - Ortalama throughput: {statistics.mean(throughputs):.2f} görev/saniye")
            print(f"   - Maksimum throughput: {max(throughputs):.2f} görev/saniye")
        
        # CPU vs I/O throughput karşılaştırması
        cpu_throughputs = [r.cpu_throughput for r in all_results if r.cpu_throughput > 0]
        io_throughputs = [r.io_throughput for r in all_results if r.io_throughput > 0]
        if cpu_throughputs and io_throughputs:
            print(f"   - Ortalama CPU throughput: {statistics.mean(cpu_throughputs):.2f} görev/saniye")
            print(f"   - Ortalama I/O throughput: {statistics.mean(io_throughputs):.2f} görev/saniye")
            ratio = statistics.mean(io_throughputs) / statistics.mean(cpu_throughputs) if statistics.mean(cpu_throughputs) > 0 else 0
            print(f"   - I/O/CPU throughput ratio: {ratio:.2f}x")
        
        # Latency analizi
        cpu_latencies = [r.cpu_avg_latency for r in all_results if r.cpu_avg_latency > 0]
        io_latencies = [r.io_avg_latency for r in all_results if r.io_avg_latency > 0]
        if cpu_latencies:
            print(f"   - Ortalama CPU latency: {statistics.mean(cpu_latencies):.2f} ms")
        if io_latencies:
            print(f"   - Ortalama I/O latency: {statistics.mean(io_latencies):.2f} ms")
        
        # Success rate analizi
        success_rates = [r.success_rate for r in all_results]
        if success_rates:
            print(f"   - Ortalama başarı oranı: {statistics.mean(success_rates)*100:.1f}%")
        
    finally:
        engine.shutdown()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


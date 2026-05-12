#!/usr/bin/env python3
"""
CPU-Bound Performance Benchmark Testi (Isolation Modu)

Bu test, `cpu_bound_performance_test.py` ile aynı senaryoları çalıştırır
ancak Engine'i CPU isolation aktif olacak şekilde başlatır. Üç mod desteklenir:

    --affinity        (varsayılan)  psutil tabanlı CPU pinning. Linux + Windows.
    --full-isolation                Linux systemd + cgroup v2 (root gerekli).
    --no-isolation                  İzolasyonu tamamen kapat (regresyon baseline'ı).

Kullanım:
    python benchmarks/cpu_bound_performance_test_isolated.py
    python benchmarks/cpu_bound_performance_test_isolated.py --full-isolation
    python benchmarks/cpu_bound_performance_test_isolated.py --profile performance
"""

import argparse
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
from axion.config.cpu_isolation_config import CpuIsolationConfig


# ============================================================================
# ISOLATION HELPERS
# ============================================================================

ISOLATION_MODE_AFFINITY = "affinity"
ISOLATION_MODE_FULL = "full"
ISOLATION_MODE_OFF = "off"


def build_isolation_config(mode: str, profile: str) -> CpuIsolationConfig:
    """
    İzolasyon modu + profile için CpuIsolationConfig üretir.

    - "affinity": enabled=False + affinity_mode=auto → AffinityBackend
    - "full":     enabled=True + backend=auto      → LinuxSystemdCgroupBackend (root)
    - "off":      hiçbir şey aktif değil           → NoopBackend
    """
    if mode == ISOLATION_MODE_FULL:
        return CpuIsolationConfig(
            enabled=True,
            backend="auto",
            profile=profile,
            affinity_mode="disabled",
            fail_on_error=False,  # backend kuramazsa NoopBackend'e düş
        )
    if mode == ISOLATION_MODE_AFFINITY:
        return CpuIsolationConfig(
            enabled=False,
            profile=profile,
            affinity_mode="auto",
            fail_on_error=False,
        )
    # mode == OFF
    return CpuIsolationConfig(
        enabled=False,
        affinity_mode="disabled",
    )


def print_isolation_status(engine: Engine, header: str = "Isolation status"):
    """Engine'in mevcut izolasyon durumunu insancıl şekilde yazdırır."""
    print(f"\n[{header}]")
    mgr = getattr(engine, "_isolation_manager", None)
    if mgr is None:
        print("   isolation: <disabled>")
        return
    try:
        status = mgr.status()
    except Exception as e:
        print(f"   isolation: status alınamadı ({e})")
        return

    print(f"   config_enabled: {status.get('config_enabled')}")
    print(f"   config_backend: {status.get('config_backend')}")
    print(f"   affinity_mode:  {status.get('affinity_mode')}")

    partition = status.get("partition") or {}
    if partition:
        print(
            f"   partition: enabled={partition.get('enabled')} "
            f"profile={partition.get('profile')} "
            f"system_cpus={partition.get('system_cpus')} "
            f"axion_cpus={partition.get('axion_cpus')}"
        )

    outcome = status.get("outcome") or {}
    if outcome:
        print(
            f"   outcome: backend={outcome.get('backend_name')} "
            f"active={outcome.get('active')} "
            f"reason={outcome.get('reason')}"
        )

    backend = status.get("backend") or {}
    if backend:
        print(f"   backend_status: {backend}")


# ============================================================================
# BENCHMARK RESULT
# ============================================================================


@dataclass
class CPUBenchmarkResult:
    """CPU benchmark sonuçları"""
    test_name: str
    num_tasks: int
    num_workers: int
    isolation_mode: str = ISOLATION_MODE_OFF
    isolation_active: bool = False
    sequential_time: Optional[float] = None
    parallel_time: float = 0.0
    throughput: float = 0.0
    speedup_ratio: float = 0.0
    cpu_usage_avg: float = 0.0
    cpu_usage_max: float = 0.0
    latency_stats: Dict[str, float] = field(default_factory=dict)
    success_rate: float = 0.0


# ============================================================================
# CORE TEST RUNNER
# ============================================================================


def _isolation_active(engine: Engine) -> bool:
    mgr = getattr(engine, "_isolation_manager", None)
    if not mgr:
        return False
    try:
        status = mgr.status()
        outcome = status.get("outcome") or {}
        return bool(outcome.get("active"))
    except Exception:
        return False


def run_cpu_bound_test(
    engine: Engine,
    script_path: str,
    test_name: str,
    task_params: Dict,
    num_tasks: int,
    num_workers: int,
    isolation_mode: str,
) -> CPUBenchmarkResult:
    print(f"\n{'=' * 70}")
    print(f"Test: {test_name}")
    print(f"{'=' * 70}")
    print(f"   - Görev sayısı: {num_tasks}")
    print(f"   - Worker sayısı: {num_workers}")
    print(f"   - Parametreler: {task_params}")
    print(f"   - Isolation modu: {isolation_mode}")

    # Parallel test
    print(f"\nGörev gönderiliyor ({num_tasks} task)...")

    task_ids: List[str] = []
    start_time = time.time()

    for _ in range(num_tasks):
        task = Task.create(
            script_path=script_path,
            params=task_params,
            task_type=TaskType.CPU_BOUND,
        )
        task_id = engine.submit_task(task)
        task_ids.append(task_id)

    submit_time = time.time() - start_time
    print(f"   Gönderim tamamlandı ({submit_time:.3f}s)")

    # Görevlerin worker'lara dağılması için kısa bekleme
    time.sleep(0.5)

    # CPU monitoring
    try:
        import psutil
        cpu_monitoring = True
    except ImportError:
        cpu_monitoring = False
        print("   uyarı: psutil yok, CPU metrikleri atlanacak")

    cpu_samples: List[float] = []
    results = []
    latencies = []

    for i, task_id in enumerate(task_ids):
        if cpu_monitoring and i % max(1, num_tasks // 20) == 0:
            try:
                cpu_samples.append(psutil.cpu_percent(interval=0.01))
            except Exception:
                pass

        result = engine.get_result(task_id, timeout=60.0)
        if result:
            results.append(result)
            if result.duration:
                latencies.append(result.duration)

        if (i + 1) % max(1, num_tasks // 10) == 0:
            print(f"   {i + 1}/{num_tasks} sonuç alındı")

    parallel_time = time.time() - start_time

    # Metrikler
    successful = len([r for r in results if r.is_success])
    success_rate = successful / len(results) if results else 0.0
    throughput = len(results) / parallel_time if parallel_time > 0 else 0.0

    latency_stats: Dict[str, float] = {}
    if latencies:
        latency_stats = {
            "avg": statistics.mean(latencies),
            "min": min(latencies),
            "max": max(latencies),
            "p50": statistics.median(latencies),
            "p95": sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0,
            "p99": sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0,
        }

    avg_cpu = statistics.mean(cpu_samples) if cpu_samples else 0.0
    max_cpu = max(cpu_samples) if cpu_samples else 0.0

    result = CPUBenchmarkResult(
        test_name=test_name,
        num_tasks=num_tasks,
        num_workers=num_workers,
        isolation_mode=isolation_mode,
        isolation_active=_isolation_active(engine),
        parallel_time=parallel_time,
        throughput=throughput,
        cpu_usage_avg=avg_cpu,
        cpu_usage_max=max_cpu,
        latency_stats=latency_stats,
        success_rate=success_rate,
    )

    print(f"\nSonuçlar:")
    print(f"   - Parallel süre: {parallel_time:.3f} s")
    print(f"   - Throughput:    {throughput:.2f} task/s")
    print(f"   - Başarı oranı:  {success_rate * 100:.1f}%")
    if avg_cpu > 0:
        print(f"   - CPU ortalama:  {avg_cpu:.1f}%")
        print(f"   - CPU maksimum:  {max_cpu:.1f}%")
    if latency_stats:
        print(f"   - Latency avg:   {latency_stats['avg'] * 1000:.2f} ms")
        print(f"   - Latency p95:   {latency_stats['p95'] * 1000:.2f} ms")
    print(f"   - Isolation:     mode={isolation_mode} active={result.isolation_active}")

    return result


# ============================================================================
# BENCHMARK SUITES
# ============================================================================


def _make_engine(num_cpu_workers: int, isolation_mode: str, profile: str) -> Engine:
    """Worker sayısı ve isolation modu ile yeni bir Engine üret + başlat."""
    config = EngineConfig(
        cpu_bound_count=num_cpu_workers,
        io_bound_count=1,
        cpu_bound_task_limit=1,
        input_queue_size=1000,
        output_queue_size=5000,
    )
    config.cpu_isolation = build_isolation_config(isolation_mode, profile)
    engine = Engine(config)
    engine.start()
    time.sleep(0.5)  # warm-up
    return engine


def run_fibonacci_benchmark(script_path: str, isolation_mode: str, profile: str) -> List[CPUBenchmarkResult]:
    results: List[CPUBenchmarkResult] = []
    cpu_count = multiprocessing.cpu_count()
    worker_configs = [1, 2, min(4, cpu_count), cpu_count]

    for num_workers in worker_configs:
        engine = _make_engine(num_workers, isolation_mode, profile)
        try:
            print_isolation_status(engine, f"Fibonacci / workers={num_workers}")
            results.append(run_cpu_bound_test(
                engine=engine,
                script_path=script_path,
                test_name="Fibonacci (n=35)",
                task_params={"n": 35},
                num_tasks=num_workers * 4,
                num_workers=num_workers,
                isolation_mode=isolation_mode,
            ))
        finally:
            engine.shutdown()
            time.sleep(1.0)

    return results


def run_prime_benchmark(script_path: str, isolation_mode: str, profile: str) -> List[CPUBenchmarkResult]:
    results: List[CPUBenchmarkResult] = []
    cpu_count = multiprocessing.cpu_count()
    worker_configs = [1, 2, min(4, cpu_count)]

    for num_workers in worker_configs:
        engine = _make_engine(num_workers, isolation_mode, profile)
        try:
            print_isolation_status(engine, f"Prime / workers={num_workers}")
            results.append(run_cpu_bound_test(
                engine=engine,
                script_path=script_path,
                test_name="Prime Finding (start=1M, count=50)",
                task_params={"start": 1_000_000, "count": 50},
                num_tasks=num_workers * 2,
                num_workers=num_workers,
                isolation_mode=isolation_mode,
            ))
        finally:
            engine.shutdown()
            time.sleep(1.0)

    return results


def run_prime_chunk_benchmark(script_path: str, isolation_mode: str, profile: str) -> List[CPUBenchmarkResult]:
    results: List[CPUBenchmarkResult] = []
    cpu_count = multiprocessing.cpu_count()
    worker_configs = [1, 2, min(4, cpu_count)]

    test_configs = [
        {"start": 1_000_000, "range": 20_000, "extra_load": 300, "name": "Light"},
        {"start": 1_000_000, "range": 50_000, "extra_load": 500, "name": "Medium"},
        {"start": 2_000_000, "range": 30_000, "extra_load": 700, "name": "Heavy"},
    ]

    for num_workers in worker_configs:
        for test_config in test_configs:
            engine = _make_engine(num_workers, isolation_mode, profile)
            try:
                print_isolation_status(
                    engine,
                    f"PrimeChunk {test_config['name']} / workers={num_workers}",
                )
                results.append(run_cpu_bound_test(
                    engine=engine,
                    script_path=script_path,
                    test_name=(
                        f"Prime Chunk ({test_config['name']}, "
                        f"start={test_config['start'] // 1_000_000}M, "
                        f"range={test_config['range'] // 1_000}K)"
                    ),
                    task_params={
                        "start": test_config["start"],
                        "range": test_config["range"],
                        "extra_load": test_config["extra_load"],
                    },
                    num_tasks=num_workers * 2,
                    num_workers=num_workers,
                    isolation_mode=isolation_mode,
                ))
            finally:
                engine.shutdown()
                time.sleep(1.0)

    return results


def run_matrix_benchmark(script_path: str, isolation_mode: str, profile: str) -> List[CPUBenchmarkResult]:
    results: List[CPUBenchmarkResult] = []
    cpu_count = multiprocessing.cpu_count()
    worker_configs = [1, 2, min(4, cpu_count)]
    matrix_sizes = [100, 150, 200]

    for num_workers in worker_configs:
        for size in matrix_sizes:
            engine = _make_engine(num_workers, isolation_mode, profile)
            try:
                print_isolation_status(
                    engine,
                    f"Matrix {size}x{size} / workers={num_workers}",
                )
                results.append(run_cpu_bound_test(
                    engine=engine,
                    script_path=script_path,
                    test_name=f"Matrix Multiplication ({size}x{size})",
                    task_params={"size": size},
                    num_tasks=num_workers * 2,
                    num_workers=num_workers,
                    isolation_mode=isolation_mode,
                ))
            finally:
                engine.shutdown()
                time.sleep(1.0)

    return results


# ============================================================================
# REPORT
# ============================================================================


def print_summary_table(results: List[CPUBenchmarkResult]):
    print("\n" + "=" * 110)
    print("CPU-Bound Performance Benchmark Özeti (Isolation Modu)")
    print("=" * 110)

    header = (
        f"{'Test':<30} {'Workers':<8} {'Iso':<10} {'Active':<7} "
        f"{'Time(s)':<10} {'Throughput':<15} {'CPU Avg':<10} {'Success':<10}"
    )
    print(header)
    print("-" * 110)

    for r in results:
        row = (
            f"{r.test_name[:28]:<30} {r.num_workers:<8} {r.isolation_mode:<10} "
            f"{('yes' if r.isolation_active else 'no'):<7} "
            f"{r.parallel_time:<10.3f} {r.throughput:<15.2f} "
            f"{(f'{r.cpu_usage_avg:.1f}%' if r.cpu_usage_avg > 0 else 'N/A'):<10} "
            f"{r.success_rate * 100:<9.1f}%"
        )
        print(row)


# ============================================================================
# ENTRY POINT
# ============================================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CPU-Bound benchmark with CPU isolation")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--affinity",
        action="store_const",
        dest="mode",
        const=ISOLATION_MODE_AFFINITY,
        help="psutil tabanlı CPU pinning (varsayılan, Windows+Linux)",
    )
    mode.add_argument(
        "--full-isolation",
        action="store_const",
        dest="mode",
        const=ISOLATION_MODE_FULL,
        help="Linux systemd + cgroup v2 (root gerekli)",
    )
    mode.add_argument(
        "--no-isolation",
        action="store_const",
        dest="mode",
        const=ISOLATION_MODE_OFF,
        help="İzolasyonu tamamen kapat (baseline)",
    )
    parser.set_defaults(mode=ISOLATION_MODE_AFFINITY)

    parser.add_argument(
        "--profile",
        choices=["safe", "balanced", "performance", "custom"],
        default="balanced",
        help="CPU isolation profili (default: balanced)",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    isolation_mode = args.mode
    profile = args.profile

    print("=" * 70)
    print("Axion - CPU-Bound Performance Benchmark (Isolated)")
    print(f"Mode: {isolation_mode}   Profile: {profile}")
    print("=" * 70)

    base_dir = Path(__file__).parent
    scripts = {
        "fibonacci": base_dir / "test_scripts" / "fibonacci_task.py",
        "prime": base_dir / "test_scripts" / "prime_task.py",
        "prime_chunk": base_dir / "test_scripts" / "prime_chunk.py",
        "matrix": base_dir / "test_scripts" / "matrix_task.py",
    }

    missing = [str(p) for p in scripts.values() if not p.exists()]
    if missing:
        print("\nScript'ler bulunamadı:")
        for m in missing:
            print(f"   - {m}")
        print("\nLütfen önce test script'lerini oluşturun.")
        return 1

    all_results: List[CPUBenchmarkResult] = []

    try:
        print("\n[1] FIBONACCI")
        all_results.extend(run_fibonacci_benchmark(str(scripts["fibonacci"]), isolation_mode, profile))

        print("\n[2] PRIME FINDING")
        all_results.extend(run_prime_benchmark(str(scripts["prime"]), isolation_mode, profile))

        print("\n[3] PRIME CHUNK")
        all_results.extend(run_prime_chunk_benchmark(str(scripts["prime_chunk"]), isolation_mode, profile))

        print("\n[4] MATRIX MULTIPLICATION")
        all_results.extend(run_matrix_benchmark(str(scripts["matrix"]), isolation_mode, profile))

        print_summary_table(all_results)

        # Analiz
        print("\n" + "=" * 70)
        print("Analiz")
        print("=" * 70)

        active_count = sum(1 for r in all_results if r.isolation_active)
        print(f"   - Isolation aktif olan test sayısı: {active_count}/{len(all_results)}")

        cpu_avgs = [r.cpu_usage_avg for r in all_results if r.cpu_usage_avg > 0]
        if cpu_avgs:
            print(f"   - Ortalama CPU kullanımı:  {statistics.mean(cpu_avgs):.1f}%")
            print(f"   - Maksimum CPU kullanımı:  {max(r.cpu_usage_max for r in all_results):.1f}%")

        tputs = [r.throughput for r in all_results if r.throughput > 0]
        if tputs:
            print(f"   - Ortalama throughput:     {statistics.mean(tputs):.2f} task/s")
            print(f"   - Maksimum throughput:     {max(tputs):.2f} task/s")

    except KeyboardInterrupt:
        print("\n[!] Test kullanıcı tarafından durduruldu.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

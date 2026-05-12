#!/usr/bin/env python3
"""
I/O-Bound Performance Benchmark Testi (Isolation Modu)

Bu test, `io_bound_performance_test.py` ile aynı senaryoları çalıştırır
ancak Engine'i CPU isolation aktif olacak şekilde başlatır. Üç mod desteklenir:

    --affinity        (varsayılan)  psutil tabanlı CPU pinning. Linux + Windows.
    --full-isolation                Linux systemd + cgroup v2 (root gerekli).
    --no-isolation                  İzolasyonu tamamen kapat (regresyon baseline'ı).

Kullanım:
    python benchmarks/io_bound_performance_test_isolated.py
    python benchmarks/io_bound_performance_test_isolated.py --full-isolation
    python benchmarks/io_bound_performance_test_isolated.py --profile performance
"""

import argparse
import sys
import time
import statistics
import multiprocessing
from pathlib import Path
from typing import List, Dict, Optional
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
    if mode == ISOLATION_MODE_FULL:
        return CpuIsolationConfig(
            enabled=True,
            backend="auto",
            profile=profile,
            affinity_mode="disabled",
            fail_on_error=False,
        )
    if mode == ISOLATION_MODE_AFFINITY:
        return CpuIsolationConfig(
            enabled=False,
            profile=profile,
            affinity_mode="auto",
            fail_on_error=False,
        )
    return CpuIsolationConfig(
        enabled=False,
        affinity_mode="disabled",
    )


def print_isolation_status(engine: Engine, header: str = "Isolation status"):
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


def _isolation_active(engine: Engine) -> bool:
    mgr = getattr(engine, "_isolation_manager", None)
    if not mgr:
        return False
    try:
        outcome = (mgr.status() or {}).get("outcome") or {}
        return bool(outcome.get("active"))
    except Exception:
        return False


# ============================================================================
# BENCHMARK RESULT
# ============================================================================


@dataclass
class IOBenchmarkResult:
    test_name: str
    num_tasks: int
    num_workers: int
    isolation_mode: str = ISOLATION_MODE_OFF
    isolation_active: bool = False
    sequential_time: Optional[float] = None
    parallel_time: float = 0.0
    throughput: float = 0.0
    speedup_ratio: float = 0.0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    io_wait_time: float = 0.0
    concurrent_ops: float = 0.0
    latency_stats: Dict[str, float] = field(default_factory=dict)
    success_rate: float = 0.0


# ============================================================================
# CORE RUNNER
# ============================================================================


def run_io_bound_test(
    engine: Engine,
    script_path: str,
    test_name: str,
    task_params: Dict,
    num_tasks: int,
    num_workers: int,
    isolation_mode: str,
) -> IOBenchmarkResult:
    print(f"\n{'=' * 70}")
    print(f"Test: {test_name}")
    print(f"{'=' * 70}")
    print(f"   - Görev sayısı:  {num_tasks}")
    print(f"   - Worker sayısı: {num_workers}")
    print(f"   - Parametreler:  {task_params}")
    print(f"   - Isolation:     {isolation_mode}")

    task_ids: List[str] = []
    start_time = time.time()

    for _ in range(num_tasks):
        task = Task.create(
            script_path=script_path,
            params=task_params,
            task_type=TaskType.IO_BOUND,
        )
        task_id = engine.submit_task(task)
        task_ids.append(task_id)

    submit_time = time.time() - start_time
    print(f"   Gönderim tamamlandı ({submit_time:.3f}s)")

    results = []
    latencies: List[float] = []
    io_wait_times: List[float] = []

    for i, task_id in enumerate(task_ids):
        result = engine.get_result(task_id, timeout=120.0)
        if result:
            results.append(result)
            if result.duration:
                latencies.append(result.duration * 1000.0)
            if result.data and isinstance(result.data, dict):
                if "elapsed_time" in result.data:
                    io_wait_times.append(result.data["elapsed_time"] * 1000.0)

        if (i + 1) % max(1, num_tasks // 10) == 0:
            print(f"   {i + 1}/{num_tasks} sonuç alındı")

    parallel_time = time.time() - start_time

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

    total_io_wait = sum(io_wait_times) if io_wait_times else 0.0
    avg_concurrent = (total_io_wait / 1000.0) / parallel_time if parallel_time > 0 else 0.0

    result = IOBenchmarkResult(
        test_name=test_name,
        num_tasks=num_tasks,
        num_workers=num_workers,
        isolation_mode=isolation_mode,
        isolation_active=_isolation_active(engine),
        parallel_time=parallel_time,
        throughput=throughput,
        avg_latency_ms=latency_stats.get("avg", 0.0),
        max_latency_ms=latency_stats.get("max", 0.0),
        io_wait_time=total_io_wait / 1000.0,
        concurrent_ops=avg_concurrent,
        latency_stats=latency_stats,
        success_rate=success_rate,
    )

    print(f"\nSonuçlar:")
    print(f"   - Parallel süre:     {parallel_time:.3f} s")
    print(f"   - Throughput:        {throughput:.2f} task/s")
    print(f"   - Başarı oranı:      {success_rate * 100:.1f}%")
    print(f"   - Latency ortalama:  {latency_stats.get('avg', 0):.2f} ms")
    print(f"   - Latency p95:       {latency_stats.get('p95', 0):.2f} ms")
    print(f"   - Toplam I/O wait:   {total_io_wait / 1000:.3f} s")
    print(f"   - Concurrent ops:    {avg_concurrent:.2f}")
    print(f"   - Isolation:         mode={isolation_mode} active={result.isolation_active}")

    return result


# ============================================================================
# BENCHMARK SUITES
# ============================================================================


def _make_engine(
    num_io_workers: int,
    io_task_limit: int,
    isolation_mode: str,
    profile: str,
) -> Engine:
    config = EngineConfig(
        cpu_bound_count=1,
        io_bound_count=num_io_workers,
        cpu_bound_task_limit=1,
        io_bound_task_limit=io_task_limit,
        input_queue_size=1000,
        output_queue_size=5000,
    )
    config.cpu_isolation = build_isolation_config(isolation_mode, profile)
    engine = Engine(config)
    engine.start()
    time.sleep(0.1)
    return engine


def run_file_io_benchmark(script_path: str, isolation_mode: str, profile: str) -> List[IOBenchmarkResult]:
    results: List[IOBenchmarkResult] = []
    cpu_count = multiprocessing.cpu_count()
    worker_configs = [1, 2, min(4, cpu_count), min(8, cpu_count)]

    test_configs = [
        {"operation": "read", "file_size": 512, "num_files": 5, "name": "Read Small"},
        {"operation": "write", "file_size": 1024, "num_files": 3, "name": "Write Medium"},
        {"operation": "readwrite", "file_size": 2048, "num_files": 2, "name": "ReadWrite Large"},
    ]

    for num_workers in worker_configs:
        for test_config in test_configs:
            engine = _make_engine(num_workers, io_task_limit=10, isolation_mode=isolation_mode, profile=profile)
            try:
                print_isolation_status(
                    engine,
                    f"FileIO {test_config['name']} / workers={num_workers}",
                )
                results.append(run_io_bound_test(
                    engine=engine,
                    script_path=script_path,
                    test_name=f"File I/O ({test_config['name']})",
                    task_params={
                        "operation": test_config["operation"],
                        "file_size": test_config["file_size"],
                        "num_files": test_config["num_files"],
                        "chunk_size": 1024,
                    },
                    num_tasks=num_workers * 3,
                    num_workers=num_workers,
                    isolation_mode=isolation_mode,
                ))
            finally:
                engine.shutdown()

    return results


def run_network_io_benchmark(script_path: str, isolation_mode: str, profile: str) -> List[IOBenchmarkResult]:
    results: List[IOBenchmarkResult] = []
    cpu_count = multiprocessing.cpu_count()
    worker_configs = [1, 2, min(4, cpu_count), min(8, cpu_count)]

    test_configs = [
        {
            "urls": [
                "https://httpbin.org/delay/1",
                "https://httpbin.org/get",
                "https://jsonplaceholder.typicode.com/posts/1",
            ],
            "name": "Mixed Endpoints",
        },
        {
            "urls": [
                "https://httpbin.org/delay/2",
                "https://httpbin.org/delay/1",
                "https://httpbin.org/delay/1",
            ],
            "name": "Delayed Requests",
        },
        {
            "urls": [
                "https://jsonplaceholder.typicode.com/posts",
                "https://jsonplaceholder.typicode.com/users",
                "https://jsonplaceholder.typicode.com/comments",
            ],
            "name": "JSON APIs",
        },
    ]

    for num_workers in worker_configs:
        for test_config in test_configs:
            engine = _make_engine(num_workers, io_task_limit=20, isolation_mode=isolation_mode, profile=profile)
            try:
                print_isolation_status(
                    engine,
                    f"NetworkIO {test_config['name']} / workers={num_workers}",
                )
                results.append(run_io_bound_test(
                    engine=engine,
                    script_path=script_path,
                    test_name=f"Network I/O ({test_config['name']})",
                    task_params={
                        "urls": test_config["urls"],
                        "timeout": 30,
                        "retry_count": 1,
                    },
                    num_tasks=num_workers * 3,
                    num_workers=num_workers,
                    isolation_mode=isolation_mode,
                ))
            finally:
                engine.shutdown()

    return results


def run_database_io_benchmark(script_path: str, isolation_mode: str, profile: str) -> List[IOBenchmarkResult]:
    results: List[IOBenchmarkResult] = []
    cpu_count = multiprocessing.cpu_count()
    worker_configs = [1, 2, min(4, cpu_count), min(8, cpu_count)]

    test_configs = [
        {"query_type": "select", "num_queries": 30, "name": "SQLite SELECT"},
        {"query_type": "insert", "num_queries": 20, "name": "SQLite INSERT"},
        {"query_type": "mixed", "num_queries": 25, "name": "SQLite MIXED"},
    ]

    for num_workers in worker_configs:
        for test_config in test_configs:
            engine = _make_engine(num_workers, io_task_limit=15, isolation_mode=isolation_mode, profile=profile)
            try:
                print_isolation_status(
                    engine,
                    f"DBIO {test_config['name']} / workers={num_workers}",
                )
                results.append(run_io_bound_test(
                    engine=engine,
                    script_path=script_path,
                    test_name=f"Database I/O ({test_config['name']})",
                    task_params={
                        "query_type": test_config["query_type"],
                        "num_queries": test_config["num_queries"],
                        "rows_per_query": 100,
                        "cleanup": True,
                    },
                    num_tasks=num_workers * 2,
                    num_workers=num_workers,
                    isolation_mode=isolation_mode,
                ))
            finally:
                engine.shutdown()

    return results


# ============================================================================
# REPORT
# ============================================================================


def print_summary_table(results: List[IOBenchmarkResult]):
    print("\n" + "=" * 130)
    print("I/O-Bound Performance Benchmark Özeti (Isolation Modu)")
    print("=" * 130)

    header = (
        f"{'Test':<35} {'Workers':<8} {'Iso':<10} {'Active':<7} "
        f"{'Time(s)':<10} {'Throughput':<15} {'AvgLat(ms)':<12} "
        f"{'Concurrent':<11} {'Success':<10}"
    )
    print(header)
    print("-" * 130)

    for r in results:
        row = (
            f"{r.test_name[:33]:<35} {r.num_workers:<8} {r.isolation_mode:<10} "
            f"{('yes' if r.isolation_active else 'no'):<7} "
            f"{r.parallel_time:<10.3f} {r.throughput:<15.2f} "
            f"{r.avg_latency_ms:<12.1f} {r.concurrent_ops:<11.2f} "
            f"{r.success_rate * 100:<9.1f}%"
        )
        print(row)


# ============================================================================
# ENTRY POINT
# ============================================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="I/O-Bound benchmark with CPU isolation")

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

    parser.add_argument(
        "--skip-network",
        action="store_true",
        help="İnternet gerektiren network I/O testlerini atla",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    isolation_mode = args.mode
    profile = args.profile

    print("=" * 70)
    print("Axion - I/O-Bound Performance Benchmark (Isolated)")
    print(f"Mode: {isolation_mode}   Profile: {profile}")
    print("=" * 70)

    base_dir = Path(__file__).parent
    scripts = {
        "file_io": base_dir / "test_scripts" / "file_io_task.py",
        "network_io": base_dir / "test_scripts" / "network_io_task.py",
        "database_io": base_dir / "test_scripts" / "database_io_task.py",
    }

    required = ["file_io", "database_io"]
    if not args.skip_network:
        required.append("network_io")

    missing = [str(scripts[k]) for k in required if not scripts[k].exists()]
    if missing:
        print("\nScript'ler bulunamadı:")
        for m in missing:
            print(f"   - {m}")
        print("\nLütfen önce test script'lerini oluşturun.")
        return 1

    all_results: List[IOBenchmarkResult] = []

    try:
        print("\n[1] FILE I/O")
        all_results.extend(run_file_io_benchmark(str(scripts["file_io"]), isolation_mode, profile))

        if not args.skip_network:
            print("\n[2] NETWORK I/O")
            all_results.extend(run_network_io_benchmark(str(scripts["network_io"]), isolation_mode, profile))
        else:
            print("\n[2] NETWORK I/O — atlandı (--skip-network)")

        print("\n[3] DATABASE I/O")
        all_results.extend(run_database_io_benchmark(str(scripts["database_io"]), isolation_mode, profile))

        print_summary_table(all_results)

        # Analiz
        print("\n" + "=" * 70)
        print("Analiz")
        print("=" * 70)

        active_count = sum(1 for r in all_results if r.isolation_active)
        print(f"   - Isolation aktif olan test sayısı: {active_count}/{len(all_results)}")

        lats = [r.avg_latency_ms for r in all_results if r.avg_latency_ms > 0]
        if lats:
            print(f"   - Ortalama latency:        {statistics.mean(lats):.2f} ms")
            print(f"   - Maksimum latency:        {max(lats):.2f} ms")

        concs = [r.concurrent_ops for r in all_results if r.concurrent_ops > 0]
        if concs:
            print(f"   - Ortalama concurrent ops: {statistics.mean(concs):.2f}")
            print(f"   - Maksimum concurrent ops: {max(concs):.2f}")

        tputs = [r.throughput for r in all_results if r.throughput > 0]
        if tputs:
            print(f"   - Ortalama throughput:     {statistics.mean(tputs):.2f} task/s")
            print(f"   - Maksimum throughput:     {max(tputs):.2f} task/s")

    except KeyboardInterrupt:
        print("\n[!] Test kullanıcı tarafından durduruldu.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

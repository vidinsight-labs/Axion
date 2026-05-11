#!/usr/bin/env python3
"""
Scalability - Task Count Performance Testi (Revised)

Bu sürümde:
- Warmup eklenmiştir
- Her task count birden fazla kez çalıştırılır, median alınır
- Throughput doğru şekilde uçtan uca (submit_start -> last_result_time) hesaplanır
- Sonuçlar submission sırasına göre bloklu beklenmez, polling ile tamamlananlar toplanır
- Queue/memory monitor test boyunca çalışır
- Saturation point daha anlamlı hesaplanır
"""

import sys
import time
import statistics
import multiprocessing
import gc
import psutil
import os
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

# Proje root'unu path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from axion import Engine, EngineConfig, Task, TaskType


@dataclass
class ScalabilityResult:
    test_name: str
    task_count: int
    num_workers: int
    task_type: str

    submit_time: float = 0.0
    execution_window_time: float = 0.0   # İlk submit -> son result
    collection_time: float = 0.0         # Sonuçları polling ile toplama süresi
    total_wall_time: float = 0.0         # Engine start sonrası test sonu

    throughput: float = 0.0              # result_count / execution_window_time
    avg_latency: float = 0.0
    p50_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0
    max_latency: float = 0.0
    min_latency: float = 0.0

    success_rate: float = 0.0
    completed_count: int = 0
    failed_count: int = 0
    timeout_count: int = 0

    memory_peak_mb: float = 0.0
    memory_avg_mb: float = 0.0
    memory_baseline_mb: float = 0.0
    memory_delta_mb: float = 0.0

    queue_max_size: int = 0
    queue_avg_size: float = 0.0

    latency_degradation: float = 0.0
    worker_efficiency: float = 0.0       # throughput / num_workers

    metrics: Dict[str, Any] = field(default_factory=dict)


def get_memory_usage_mb() -> float:
    try:
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0


def percentile(sorted_values: List[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]

    k = (len(sorted_values) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)

    if f == c:
        return sorted_values[f]

    d0 = sorted_values[f] * (c - k)
    d1 = sorted_values[c] * (k - f)
    return d0 + d1


def make_engine_config(task_count: int, num_workers: int, task_type: TaskType) -> EngineConfig:
    if task_count <= 1000:
        input_queue_size = max(1000, task_count * 2)
        output_queue_size = max(5000, task_count * 3)
    elif task_count <= 10000:
        input_queue_size = max(10000, task_count)
        output_queue_size = max(50000, task_count * 2)
    elif task_count < 100000:
        input_queue_size = max(50000, task_count // 2)
        output_queue_size = max(200000, task_count)
    else:
        input_queue_size = max(100000, task_count // 4)
        output_queue_size = max(500000, task_count // 2)

    if task_type == TaskType.CPU_BOUND:
        return EngineConfig(
            cpu_bound_count=num_workers,
            io_bound_count=1,
            cpu_bound_task_limit=1,
            io_bound_task_limit=1,
            input_queue_size=input_queue_size,
            output_queue_size=output_queue_size,
        )

    return EngineConfig(
        cpu_bound_count=1,
        io_bound_count=num_workers,
        cpu_bound_task_limit=1,
        io_bound_task_limit=10,
        input_queue_size=input_queue_size,
        output_queue_size=output_queue_size,
    )


def monitor_engine_resources(engine: Engine, stop_event: threading.Event,
                             queue_sizes: List[int], memory_samples: List[float], interval: float = 0.1):
    while not stop_event.is_set():
        try:
            status = engine.get_status()
            comps = status.get("components", {})
            if "input_queue" in comps:
                queue_size = comps["input_queue"]["metrics"].get("size", 0)
                queue_sizes.append(queue_size)
        except Exception:
            pass

        memory_samples.append(get_memory_usage_mb())
        time.sleep(interval)


def wait_for_results_polling(
    engine: Engine,
    task_ids: List[str],
    overall_timeout: float,
    poll_interval: float = 0.02,
    progress_label: str = ""
) -> Tuple[List[Any], int]:
    """
    Sonuçları submission sırasına göre bloklu beklemek yerine polling ile toplar.
    timeout_count döndürür.
    """
    pending = set(task_ids)
    results = []
    timeout_count = 0

    start = time.time()
    last_print = start

    while pending:
        now = time.time()
        if now - start > overall_timeout:
            timeout_count = len(pending)
            break

        completed_this_round = []

        for task_id in list(pending):
            try:
                result = engine.get_result(task_id, timeout=0.0)
            except TypeError:
                # Eğer timeout=0.0 desteklenmiyorsa, çok küçük timeout ile dene
                try:
                    result = engine.get_result(task_id, timeout=0.001)
                except Exception:
                    result = None
            except Exception:
                result = None

            if result is not None:
                results.append(result)
                completed_this_round.append(task_id)

        for task_id in completed_this_round:
            pending.discard(task_id)

        if now - last_print >= 1.0:
            done = len(task_ids) - len(pending)
            rate = done / (now - start) if now > start else 0
            print(f"   ✅ {progress_label} {done:,}/{len(task_ids):,} sonuç alındı ({rate:.1f} sonuç/s)")
            last_print = now

        if pending:
            time.sleep(poll_interval)

    return results, timeout_count


def run_scalability_test(
    script_path: str,
    test_name: str,
    task_params: Dict[str, Any],
    task_count: int,
    num_workers: int,
    task_type: TaskType,
    baseline_latency: Optional[float] = None,
) -> ScalabilityResult:
    print(f"\n{'=' * 80}")
    print(f"🧪 Test: {test_name}")
    print(f"{'=' * 80}")
    print(f"   - Görev sayısı: {task_count:,}")
    print(f"   - Worker sayısı: {num_workers}")
    print(f"   - Görev tipi: {task_type.value}")

    gc.collect()
    memory_baseline = get_memory_usage_mb()

    config = make_engine_config(task_count, num_workers, task_type)
    engine = Engine(config)
    engine.start()
    time.sleep(0.3)

    queue_sizes: List[int] = []
    memory_samples: List[float] = []
    stop_monitor = threading.Event()
    monitor_thread = threading.Thread(
        target=monitor_engine_resources,
        args=(engine, stop_monitor, queue_sizes, memory_samples, 0.1),
        daemon=True
    )
    monitor_thread.start()

    task_ids: List[str] = []

    total_test_start = time.time()
    submit_start = time.time()

    print(f"\n📤 {task_count:,} görev gönderiliyor...")

    for i in range(task_count):
        task = Task.create(
            script_path=script_path,
            params=task_params,
            task_type=task_type
        )
        task_id = engine.submit_task(task)
        task_ids.append(task_id)

        if task_count >= 1000 and (i + 1) % max(1, task_count // 20) == 0:
            elapsed = time.time() - submit_start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            print(f"   📊 {i + 1:,}/{task_count:,} görev gönderildi ({rate:.1f} görev/s)")

    submit_end = time.time()
    submit_time = submit_end - submit_start
    print(f"   ✅ Gönderim tamamlandı ({submit_time:.3f} saniye, {task_count / submit_time:.1f} görev/s)")

    print(f"\n⏳ Sonuçlar polling ile toplanıyor...")

    # Uçtan uca pencere: ilk submit ile son sonucun alınması
    execution_window_start = submit_start

    # Global timeout: task count ve task type'a göre daha mantıklı ölçekleme
    if task_type == TaskType.CPU_BOUND:
        overall_timeout = min(max(90.0, task_count * 0.05), 900.0)
    else:
        overall_timeout = min(max(120.0, task_count * 0.15), 1800.0)

    collection_start = time.time()
    results, timeout_count = wait_for_results_polling(
        engine=engine,
        task_ids=task_ids,
        overall_timeout=overall_timeout,
        poll_interval=0.02 if task_count <= 1000 else 0.05,
        progress_label=test_name
    )
    collection_end = time.time()

    execution_window_end = collection_end
    execution_window_time = execution_window_end - execution_window_start
    collection_time = collection_end - collection_start
    total_wall_time = collection_end - total_test_start

    stop_monitor.set()
    monitor_thread.join(timeout=1.0)

    gc.collect()
    memory_final = get_memory_usage_mb()
    memory_samples.append(memory_final)

    completed_count = len(results)
    successful = len([r for r in results if getattr(r, "is_success", False)])
    failed_count = completed_count - successful
    success_rate = successful / task_count if task_count > 0 else 0.0

    throughput = completed_count / execution_window_time if execution_window_time > 0 else 0.0

    latencies = []
    for r in results:
        duration = getattr(r, "duration", None)
        if duration is not None:
            latencies.append(duration * 1000.0)

    if latencies:
        sorted_latencies = sorted(latencies)
        avg_latency = statistics.mean(sorted_latencies)
        min_latency = sorted_latencies[0]
        max_latency = sorted_latencies[-1]
        p50_latency = percentile(sorted_latencies, 0.50)
        p95_latency = percentile(sorted_latencies, 0.95)
        p99_latency = percentile(sorted_latencies, 0.99)
    else:
        avg_latency = min_latency = max_latency = p50_latency = p95_latency = p99_latency = 0.0

    memory_peak = max(memory_samples) if memory_samples else memory_final
    memory_avg = statistics.mean(memory_samples) if memory_samples else memory_final
    memory_delta = memory_peak - memory_baseline

    queue_max_size = max(queue_sizes) if queue_sizes else 0
    queue_avg_size = statistics.mean(queue_sizes) if queue_sizes else 0.0

    latency_degradation = 0.0
    if baseline_latency and avg_latency > 0:
        latency_degradation = ((avg_latency - baseline_latency) / baseline_latency) if baseline_latency > 0 else 0.0

    worker_efficiency = throughput / num_workers if num_workers > 0 else 0.0

    result = ScalabilityResult(
        test_name=test_name,
        task_count=task_count,
        num_workers=num_workers,
        task_type=task_type.value,
        submit_time=submit_time,
        execution_window_time=execution_window_time,
        collection_time=collection_time,
        total_wall_time=total_wall_time,
        throughput=throughput,
        avg_latency=avg_latency,
        p50_latency=p50_latency,
        p95_latency=p95_latency,
        p99_latency=p99_latency,
        max_latency=max_latency,
        min_latency=min_latency,
        success_rate=success_rate,
        completed_count=completed_count,
        failed_count=failed_count,
        timeout_count=timeout_count,
        memory_peak_mb=memory_peak,
        memory_avg_mb=memory_avg,
        memory_baseline_mb=memory_baseline,
        memory_delta_mb=memory_delta,
        queue_max_size=queue_max_size,
        queue_avg_size=queue_avg_size,
        latency_degradation=latency_degradation,
        worker_efficiency=worker_efficiency,
        metrics={
            "submit_rate": task_count / submit_time if submit_time > 0 else 0.0,
            "results_received": completed_count,
            "successful_results": successful,
            "failed_results": failed_count,
            "timed_out_results": timeout_count,
        }
    )

    print(f"\n📊 Sonuçlar:")
    print(f"   - Submit süresi: {submit_time:.3f} saniye")
    print(f"   - Execution window: {execution_window_time:.3f} saniye")
    print(f"   - Collection süresi: {collection_time:.3f} saniye")
    print(f"   - Total wall time: {total_wall_time:.3f} saniye")
    print(f"   - Throughput: {throughput:.2f} görev/saniye")
    print(f"   - Worker efficiency: {worker_efficiency:.2f} görev/saniye/worker")
    print(f"   - Başarı oranı: {success_rate * 100:.1f}%")
    print(f"   - Tamamlanan: {completed_count:,}/{task_count:,}")
    print(f"   - Timeout sayısı: {timeout_count:,}")
    print(f"   - Ortalama latency: {avg_latency:.2f} ms")
    print(f"   - P50 latency: {p50_latency:.2f} ms")
    print(f"   - P95 latency: {p95_latency:.2f} ms")
    print(f"   - P99 latency: {p99_latency:.2f} ms")
    print(f"   - Max latency: {max_latency:.2f} ms")
    if baseline_latency:
        print(f"   - Latency degradation: {latency_degradation * 100:+.1f}%")
    print(f"   - Memory baseline: {memory_baseline:.1f} MB")
    print(f"   - Memory peak: {memory_peak:.1f} MB")
    print(f"   - Memory avg: {memory_avg:.1f} MB")
    print(f"   - Memory delta (peak-baseline): {memory_delta:+.1f} MB")
    print(f"   - Queue max size: {queue_max_size:,}")
    print(f"   - Queue avg size: {queue_avg_size:.1f}")

    engine.shutdown()
    return result


def median_result(results: List[ScalabilityResult]) -> ScalabilityResult:
    """
    Aynı testin tekrarlı koşularından throughput'a göre median sonucu seçer.
    """
    if len(results) == 1:
        return results[0]

    ordered = sorted(results, key=lambda r: r.throughput)
    return ordered[len(ordered) // 2]


def warmup_engine(script_path: str, task_type: TaskType, task_params: Dict[str, Any], num_workers: int):
    print("\n🔥 Warmup başlatılıyor...")
    try:
        _ = run_scalability_test(
            script_path=script_path,
            test_name=f"Warmup ({task_type.value})",
            task_params=task_params,
            task_count=5,
            num_workers=num_workers,
            task_type=task_type,
            baseline_latency=None
        )
    except Exception as e:
        print(f"   ⚠️ Warmup sırasında hata: {e}")
    print("🔥 Warmup tamamlandı.\n")


def run_repeated_benchmark(
    script_path: str,
    task_type: TaskType,
    task_params: Dict[str, Any],
    task_counts: List[int],
    num_workers: int,
    repeats: int = 3
) -> List[ScalabilityResult]:
    results = []
    baseline_latency = None

    for task_count in task_counts:
        run_results = []

        for run_no in range(1, repeats + 1):
            time.sleep(0.5)
            test_name = f"{task_type.value.upper()} Scalability ({task_count:,} tasks) [run {run_no}]"

            result = run_scalability_test(
                script_path=script_path,
                test_name=test_name,
                task_params=task_params,
                task_count=task_count,
                num_workers=num_workers,
                task_type=task_type,
                baseline_latency=baseline_latency
            )
            run_results.append(result)

        med = median_result(run_results)
        med.test_name = f"{task_type.value.upper()} Scalability ({task_count:,} tasks) [median of {repeats}]"
        results.append(med)

        if baseline_latency is None and med.avg_latency > 0:
            baseline_latency = med.avg_latency

    return results


def find_saturation_point(results: List[ScalabilityResult], improvement_threshold_pct: float = 10.0) -> Optional[Tuple[int, float]]:
    """
    Saturation point = throughput artışının bir önceki noktaya göre improvement_threshold_pct altına düştüğü ilk nokta.
    """
    if len(results) < 2:
        return None

    ordered = sorted(results, key=lambda r: r.task_count)

    for i in range(1, len(ordered)):
        prev_tp = ordered[i - 1].throughput
        curr_tp = ordered[i].throughput
        if prev_tp <= 0:
            continue

        improvement_pct = ((curr_tp - prev_tp) / prev_tp) * 100.0
        if improvement_pct < improvement_threshold_pct:
            return ordered[i].task_count, curr_tp

    return ordered[-1].task_count, ordered[-1].throughput


def print_summary_table(results: List[ScalabilityResult]):
    print("\n" + "=" * 180)
    print("📈 Scalability - Task Count Benchmark Özeti (Revised)")
    print("=" * 180)

    print(
        f"{'Test':<45} {'Tasks':<10} {'Exec(s)':<10} {'Submit(s)':<10} "
        f"{'Throughput':<18} {'Avg Lat':<12} {'P95 Lat':<12} {'P99 Lat':<12} "
        f"{'Peak Mem':<10} {'QueueMax':<10} {'Timeout':<10} {'Success':<10}"
    )
    print("-" * 180)

    for result in results:
        test_name = result.test_name[:43]
        tasks = f"{result.task_count:,}"
        exec_s = f"{result.execution_window_time:.3f}"
        submit_s = f"{result.submit_time:.3f}"
        throughput = f"{result.throughput:.2f} task/s"
        avg_lat = f"{result.avg_latency:.1f} ms"
        p95_lat = f"{result.p95_latency:.1f} ms"
        p99_lat = f"{result.p99_latency:.1f} ms"
        peak_mem = f"{result.memory_peak_mb:.0f} MB"
        qmax = f"{result.queue_max_size:,}"
        tout = f"{result.timeout_count:,}"
        success = f"{result.success_rate * 100:.1f}%"

        print(
            f"{test_name:<45} {tasks:<10} {exec_s:<10} {submit_s:<10} "
            f"{throughput:<18} {avg_lat:<12} {p95_lat:<12} {p99_lat:<12} "
            f"{peak_mem:<10} {qmax:<10} {tout:<10} {success:<10}"
        )


def analyze_scalability(results: List[ScalabilityResult]):
    print("\n" + "=" * 80)
    print("📊 Scalability Analizi (Revised)")
    print("=" * 80)

    cpu_results = [r for r in results if r.task_type == "cpu_bound"]
    io_results = [r for r in results if r.task_type == "io_bound"]

    def analyze_group(title: str, group: List[ScalabilityResult]):
        if not group:
            return

        group = sorted(group, key=lambda x: x.task_count)

        print(f"\n{title}")
        print(f"   Görev Sayısı → Throughput → Avg Latency → Peak Memory → Queue Max")

        for r in group:
            print(
                f"   {r.task_count:>8,} → {r.throughput:>8.2f} task/s → "
                f"{r.avg_latency:>8.1f} ms → {r.memory_peak_mb:>8.1f} MB → {r.queue_max_size:>8,}"
            )

        max_tp_result = max(group, key=lambda r: r.throughput)
        print(f"\n   📈 Maksimum Throughput: {max_tp_result.throughput:.2f} task/s @ {max_tp_result.task_count:,} görev")

        saturation = find_saturation_point(group, improvement_threshold_pct=10.0)
        if saturation:
            sat_tasks, sat_tp = saturation
            print(f"   📌 Yaklaşık Saturation Point: {sat_tasks:,} görev ({sat_tp:.2f} task/s civarı)")

        baseline = group[0].avg_latency
        if baseline > 0 and len(group) > 1:
            print(f"\n   📉 Latency Degradation (baseline: {baseline:.2f} ms):")
            for r in group[1:]:
                deg = ((r.avg_latency - baseline) / baseline) * 100.0
                print(f"      {r.task_count:>8,} görev: {deg:>+7.1f}%")

        baseline_mem = group[0].memory_peak_mb
        if baseline_mem > 0 and len(group) > 1:
            print(f"\n   🧠 Memory Growth (baseline peak: {baseline_mem:.1f} MB):")
            for r in group[1:]:
                growth = ((r.memory_peak_mb - baseline_mem) / baseline_mem) * 100.0
                print(f"      {r.task_count:>8,} görev: {growth:>+7.1f}%")

    analyze_group("🖥️  CPU-Bound Scalability:", cpu_results)
    analyze_group("🌐 I/O-Bound Scalability:", io_results)


def main():
    print("=" * 80)
    print("🚀 Axion Engine - Scalability (Task Count) Benchmark [Revised]")
    print("=" * 80)

    base_dir = Path(__file__).parent
    cpu_script = base_dir / "test_scripts" / "prime_chunk.py"
    io_script = base_dir / "test_scripts" / "network_io_task.py"

    if not cpu_script.exists():
        print(f"\n❌ CPU script bulunamadı: {cpu_script}")
        return 1

    if not io_script.exists():
        print(f"\n❌ I/O script bulunamadı: {io_script}")
        return 1

    try:
        import psutil  # noqa
    except ImportError:
        print("\n⚠️ psutil bulunamadı. Memory metrikleri eksik olabilir.")
        print("   Yüklemek için: pip install psutil")

    cpu_count = multiprocessing.cpu_count()
    num_workers = min(4, cpu_count)

    cpu_task_counts = [10, 100, 1000, 10000]
    io_task_counts = [10, 100, 1000, 10000]

    cpu_params = {
        "start": 1_000_000,
        "range": 10_000,
        "extra_load": 200
    }

    io_params = {
        "urls": ["https://httpbin.org/get"],
        "timeout": 10,
        "retry_count": 1
    }

    all_results: List[ScalabilityResult] = []

    print("\n" + "=" * 80)
    print("1️⃣  CPU-BOUND SCALABILITY BENCHMARK")
    print("=" * 80)

    warmup_engine(str(cpu_script), TaskType.CPU_BOUND, cpu_params, num_workers)
    cpu_results = run_repeated_benchmark(
        script_path=str(cpu_script),
        task_type=TaskType.CPU_BOUND,
        task_params=cpu_params,
        task_counts=cpu_task_counts,
        num_workers=num_workers,
        repeats=3
    )
    all_results.extend(cpu_results)

    print("\n" + "=" * 80)
    print("2️⃣  I/O-BOUND SCALABILITY BENCHMARK")
    print("=" * 80)

    warmup_engine(str(io_script), TaskType.IO_BOUND, io_params, num_workers)
    io_results = run_repeated_benchmark(
        script_path=str(io_script),
        task_type=TaskType.IO_BOUND,
        task_params=io_params,
        task_counts=io_task_counts,
        num_workers=num_workers,
        repeats=3
    )
    all_results.extend(io_results)

    print_summary_table(all_results)
    analyze_scalability(all_results)

    return 0


if __name__ == "__main__":
    sys.exit(main())
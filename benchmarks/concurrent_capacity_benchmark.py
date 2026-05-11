#!/usr/bin/env python3
"""
Concurrent Capacity Benchmark
==============================
Minimum sistem gereksinimi analizi icin:
  - Her (worker sayisi x gorev sayisi) kombinasyonunu adim adim calistirir.
  - Gercek anlamda kac gorevin ayni anda islendigi olculmektedir.
  - Sonunda tablo + doyum analizi yazdirilir.

Gorev: sort_and_reduce_task.py  (saf CPU, I/O yok, orta zorluk ~0.3 s/task)
"""

import sys
import time
import statistics
import multiprocessing
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from axion import Engine, EngineConfig, Task, TaskType


# ------------------------------------------------------------------------------
#  Veri yapilari
# ------------------------------------------------------------------------------

@dataclass
class StepResult:
    label: str
    workers: int
    task_count: int
    wall_time: float           # Tum gorevler bitene kadar gecen gercek sure (s)
    throughput: float          # gorev / saniye
    speedup: float             # 1-worker baseline'a gore hizlanma
    efficiency: float          # speedup / workers  (1.0 = mukemmel linear)
    avg_dur_ms: float          # ortalama gorev suresi (ms)
    p95_dur_ms: float          # p95 gorev suresi (ms)
    max_observed_parallel: int # ayni anda en fazla kac gorev aktif goruldu
    success_rate: float        # basarili / toplam
    finish_times: List[float] = field(default_factory=list)
    durations_ms: List[float] = field(default_factory=list)


# ------------------------------------------------------------------------------
#  Makine bilgisi
# ------------------------------------------------------------------------------

def get_machine_info() -> Dict:
    logical  = multiprocessing.cpu_count()
    physical = logical
    try:
        import psutil
        physical = psutil.cpu_count(logical=False) or logical
    except ImportError:
        pass
    return {"logical": logical, "physical": physical}


# ------------------------------------------------------------------------------
#  Engine fabrikasi
# ------------------------------------------------------------------------------

def make_engine(num_workers: int) -> Engine:
    config = EngineConfig(
        cpu_bound_count=num_workers,
        io_bound_count=1,
        cpu_bound_task_limit=1,
        input_queue_size=500,
        output_queue_size=2000,
    )
    engine = Engine(config)
    engine.start()
    time.sleep(0.5)  # Worker process'lerinin hazir olmasini bekle (test suresine dahil degil)
    return engine


# ------------------------------------------------------------------------------
#  Yardimci: bitis zamani kumelerini bul
# ------------------------------------------------------------------------------

def find_clusters(sorted_times: List[float], gap: float = 0.15) -> List[List[float]]:
    """
    Birbirine gap saniyeden yakin biten gorevleri ayni kumeye koyar.
    Ayni anda calisan gorevler birlikte ya da cok yakin biter.
    """
    if not sorted_times:
        return []
    clusters: List[List[float]] = [[sorted_times[0]]]
    for t in sorted_times[1:]:
        if t - clusters[-1][-1] <= gap:
            clusters[-1].append(t)
        else:
            clusters.append([t])
    return clusters


def format_clusters(clusters: List[List[float]]) -> str:
    parts = [f"[{len(c)}x ~{c[0]:.2f}s]" for c in clusters]
    return " -> ".join(parts) if parts else "-"


# ------------------------------------------------------------------------------
#  Tek adim calistir
# ------------------------------------------------------------------------------

def run_step(
    script_path: str,
    task_params: dict,
    num_workers: int,
    task_count: int,
    baseline_time: Optional[float],
    step_label: str,
) -> StepResult:

    sep = "-" * 68
    print(f"\n{sep}")
    print(f"  {step_label}")
    print(f"  Workers: {num_workers}   |   Gorev sayisi: {task_count}")
    print(sep)

    engine = make_engine(num_workers)

    # -- Gorevleri gonder ------------------------------------------------------
    task_ids: List[str] = []
    t_submit = time.perf_counter()

    for _ in range(task_count):
        task = Task.create(
            script_path=script_path,
            params=task_params,
            task_type=TaskType.CPU_BOUND,
        )
        task_ids.append(engine.submit_task(task))

    submit_ms = (time.perf_counter() - t_submit) * 1000
    print(f"  ^ {task_count} gorev gonderildi  ({submit_ms:.1f} ms)")

    # -- Sonuclari topla -------------------------------------------------------
    finish_times: List[float] = []   # her gorevin wall-clock bitis ani (s)
    durations_ms: List[float] = []   # her gorevin icsel execution suresi (ms)
    raw_results = []

    t_wall_start = time.perf_counter()

    for task_id in task_ids:
        result = engine.get_result(task_id, timeout=120.0)
        finish_t = time.perf_counter() - t_wall_start
        if result:
            raw_results.append(result)
            finish_times.append(finish_t)
            if result.duration:
                durations_ms.append(result.duration * 1000)

    wall_time = time.perf_counter() - t_wall_start

    engine.shutdown()
    time.sleep(0.5)  # Temiz kapanma (sonraki adimin suresine dahil degil)

    # -- Metrik hesapla --------------------------------------------------------
    successful   = sum(1 for r in raw_results if r.is_success)
    success_rate = successful / task_count if task_count else 0.0
    throughput   = len(raw_results) / wall_time if wall_time > 0 else 0.0

    speedup    = (baseline_time / wall_time) if (baseline_time and wall_time > 0) else 1.0
    efficiency = speedup / num_workers if num_workers > 0 else 0.0

    avg_dur_ms = statistics.mean(durations_ms) if durations_ms else 0.0
    p95_dur_ms = 0.0
    if durations_ms:
        sd = sorted(durations_ms)
        p95_dur_ms = sd[max(0, int(len(sd) * 0.95) - 1)]

    # Maksimum gozlemlenen paralellik:
    # Her gorevin tahmini baslangic zamani = bitis zamani - execution suresi
    max_observed_parallel = 0
    if durations_ms and finish_times and len(durations_ms) == len(finish_times):
        intervals = [
            (ft - dur / 1000.0, ft)
            for ft, dur in zip(finish_times, durations_ms)
        ]
        # Her bitis aninda kac interval aktifti?
        for _, end in intervals:
            overlap = sum(1 for s, e in intervals if s < end and e > (end - 1e-9))
            if overlap > max_observed_parallel:
                max_observed_parallel = overlap

    # -- Adim ciktisi ----------------------------------------------------------
    print(f"  Wall-clock sure    : {wall_time:.3f} s")
    print(f"  Throughput         : {throughput:.2f} gorev/s")
    speedup_str = f"{speedup:.2f}x" if speedup != 1.0 else "1.00x  (baseline)"
    print(f"  Speedup            : {speedup_str}")
    print(f"  Verimlilik         : {efficiency*100:.1f}%  (ideal=100%)")
    print(f"  Ort. gorev suresi  : {avg_dur_ms:.1f} ms")
    print(f"  P95 gorev suresi   : {p95_dur_ms:.1f} ms")
    print(f"  Max es zamanli     : {max_observed_parallel} gorev  (gozlemlenen)")
    print(f"  Basari orani       : {success_rate*100:.1f}%")

    # Bitis kumesi analizi -- paralel mi sirali mi calistiklarini gosterir
    if finish_times:
        clusters = find_clusters(sorted(finish_times))
        print(f"  Bitis dagilimi     : {format_clusters(clusters)}")
        if len(clusters) == 1:
            print(f"  [OK] Tum gorevler tek kumede bitti -> gercek paralellik yuksek")
        elif len(clusters) <= 3:
            print(f"  [~]  Gorevler {len(clusters)} dalgada bitti -> kismi paralellik")
        else:
            print(f"  [X]  Gorevler {len(clusters)} ayri dalgada bitti -> buyuk olasilikla sirali")

    return StepResult(
        label=step_label,
        workers=num_workers,
        task_count=task_count,
        wall_time=wall_time,
        throughput=throughput,
        speedup=speedup,
        efficiency=efficiency,
        avg_dur_ms=avg_dur_ms,
        p95_dur_ms=p95_dur_ms,
        max_observed_parallel=max_observed_parallel,
        success_rate=success_rate,
        finish_times=finish_times,
        durations_ms=durations_ms,
    )


# ------------------------------------------------------------------------------
#  Ozet tablo
# ------------------------------------------------------------------------------

def print_summary_table(results: List[StepResult], machine_info: Dict) -> None:
    logical  = machine_info["logical"]
    physical = machine_info["physical"]

    W = 108
    print(f"\n{'=' * W}")
    print(f"  CONCURRENT CAPACITY BENCHMARK  -  Ozet Tablosu")
    print(f"  Makine: {logical} mantiksal cekirdek  /  {physical} fiziksel cekirdek")
    print(f"{'=' * W}")

    # Sutun genislikleri
    C = {
        "Workers"  : 9,
        "Gorev"    : 7,
        "Wall(s)"  : 9,
        "task/s"   : 8,
        "Speedup"  : 9,
        "Verim%"   : 8,
        "OrtMs"    : 8,
        "P95Ms"    : 8,
        "MaxParal" : 10,
        "Basari%"  : 9,
    }

    header = "  " + "".join(f"{k:<{v}}" for k, v in C.items())
    print(header)
    print("  " + "-" * (sum(C.values())))

    prev_workers = None
    for r in results:
        # Worker grubu degistiyse bos satir ekle (okunabilirlik)
        if prev_workers is not None and r.workers != prev_workers:
            print()
        prev_workers = r.workers

        speedup_s = f"{r.speedup:.2f}x"
        row = (
            f"  {r.workers:<{C['Workers']}}"
            f"{r.task_count:<{C['Gorev']}}"
            f"{r.wall_time:<{C['Wall(s)']}.3f}"
            f"{r.throughput:<{C['task/s']}.2f}"
            f"{speedup_s:<{C['Speedup']}}"
            f"{r.efficiency*100:<{C['Verim%']}.1f}"
            f"{r.avg_dur_ms:<{C['OrtMs']}.1f}"
            f"{r.p95_dur_ms:<{C['P95Ms']}.1f}"
            f"{r.max_observed_parallel:<{C['MaxParal']}}"
            f"{r.success_rate*100:<{C['Basari%']}.1f}"
        )
        print(row)

    print(f"\n{'-' * W}")
    print("  KOLON ACIKLAMALARI")
    print(f"{'-' * W}")
    print("  Workers  -> Kac CPU worker (OS process) kullanildi")
    print("  Gorev    -> Ayni anda motor kuyruğuna gonderilen gorev sayisi")
    print("  Wall(s)  -> Tum gorevler tamamlanana kadar gecen gercek (duvar saati) sure")
    print("  task/s   -> Saniyede tamamlanan gorev sayisi (throughput)")
    print("  Speedup  -> Ayni gorev sayisi icin 1-worker baseline'a gore hizlanma")
    print("  Verim%   -> Speedup / Workers x 100  (100% = tam dogrusal olcekleme)")
    print("  OrtMs    -> Gorev basina ortalama calisma suresi (ms)")
    print("  P95Ms    -> Gorevlerin %%95'i bu esikten once tamamlandi (ms)")
    print("  MaxParal -> Zaman penceresinden cikarilan en yuksek es zamanli gorev sayisi")
    print("  Basari%  -> Hatasiz tamamlanan gorev yuzdesi")

    # -- Doyum analizi ---------------------------------------------------------
    print(f"\n{'-' * W}")
    print("  DOYUM ANALIZI  -  Ayni gorev sayisi, artan worker")
    print(f"{'-' * W}")

    task_groups: Dict[int, List[StepResult]] = {}
    for r in results:
        task_groups.setdefault(r.task_count, []).append(r)

    for tc, group in sorted(task_groups.items()):
        group = sorted(group, key=lambda x: x.workers)
        if len(group) < 2:
            continue
        print(f"\n  Gorev sayisi = {tc}")
        prev = group[0]
        for curr in group[1:]:
            delta_pct = (curr.throughput - prev.throughput) / max(prev.throughput, 1e-9) * 100
            if delta_pct > 5:
                verdict = "^ IYILESME"
            elif delta_pct > -5:
                verdict = "~ DOYUM"
            else:
                verdict = "v GERILEME"
            print(
                f"    {prev.workers:>2} -> {curr.workers:<2} worker : "
                f"{prev.throughput:5.2f} -> {curr.throughput:5.2f} task/s  "
                f"({delta_pct:+.1f}%)   {verdict}"
            )
            prev = curr

    # -- Minimum gereksinim tavsiyesi ------------------------------------------
    print(f"\n{'-' * W}")
    print("  MINIMUM SISTEM GEREKSINIMI TAVSIYESI")
    print(f"{'-' * W}")
    print(f"  Bu makine: {physical} fiziksel / {logical} mantiksal cekirdek")

    best_efficiency = max(results, key=lambda r: r.efficiency)
    best_throughput = max(results, key=lambda r: r.throughput)
    saturation_point = None

    for tc, group in sorted(task_groups.items()):
        group = sorted(group, key=lambda x: x.workers)
        for i in range(1, len(group)):
            delta = (group[i].throughput - group[i-1].throughput) / max(group[i-1].throughput, 1e-9)
            if delta < 0.05:
                saturation_point = (group[i-1].workers, tc)
                break
        if saturation_point:
            break

    print(f"\n  En yuksek verimlilik  : {best_efficiency.workers} worker x "
          f"{best_efficiency.task_count} gorev  ->  verim {best_efficiency.efficiency*100:.1f}%")
    print(f"  En yuksek throughput  : {best_throughput.workers} worker x "
          f"{best_throughput.task_count} gorev  ->  {best_throughput.throughput:.2f} task/s")
    if saturation_point:
        print(f"  Doyum noktasi tahmini : {saturation_point[0]} worker'da throughput artisi "
              f"durdu ({saturation_point[1]} gorev icin)")
        print(f"  -> Minimum oneri      : en az {saturation_point[0]} fiziksel cekirdek")
    else:
        print("  -> Doyum noktasi belirlenemedi; daha yuksek worker sayilari deneyin.")

    print(f"\n{'=' * W}\n")


# ------------------------------------------------------------------------------
#  Giris noktasi
# ------------------------------------------------------------------------------

def main() -> None:
    machine_info = get_machine_info()
    logical      = machine_info["logical"]
    physical     = machine_info["physical"]

    print("=" * 68)
    print("  AXION  -  Concurrent Capacity Benchmark")
    print("  Minimum Sistem Gereksinimi Analizi")
    print("=" * 68)
    print(f"  Fiziksel cekirdek  : {physical}")
    print(f"  Mantiksal cekirdek : {logical}")
    print("=" * 68)

    base_dir    = Path(__file__).parent
    task_script = base_dir / "test_scripts" / "sort_and_reduce_task.py"
    task_params = {"list_size": 300_000, "iterations": 5}

    # -- Test matrisi ----------------------------------------------------------
    # Sabit baslangic noktalari
    worker_candidates = [1, 2, 4]
    # 4'ten fiziksel cekirdege kadar 2'ser adimla ara degerler (6, 8, 10, ...)
    if physical > 4:
        worker_candidates += list(range(6, physical + 1, 2))
    # Fiziksel cekirdek sayisi (zaten listede degilse)
    if physical not in worker_candidates:
        worker_candidates.append(physical)
    # Mantiksal cekirdek sayisi (fiziksel'den farkliysa)
    if logical != physical:
        worker_candidates.append(logical)
    worker_counts = sorted(set(worker_candidates))

    task_counts = [5, 10, 20]

    test_matrix = [(w, t) for w in worker_counts for t in task_counts]
    total_steps = len(test_matrix)

    print(f"\n  Test matrisi      : {total_steps} adim")
    print(f"  Worker sayilari   : {worker_counts}")
    print(f"  Gorev sayilari    : {task_counts}")
    print(f"  Gorev scripti     : {task_script.name}")
    print(f"  Parametreler      : list_size={task_params['list_size']:,}  "
          f"iterations={task_params['iterations']}  (~300 ms/gorev beklenen)")
    print()

    all_results: List[StepResult] = []
    # Her gorev sayisi icin 1-worker sonucu baseline olarak kullanilir
    baseline_times: Dict[int, float] = {}

    for step_idx, (workers, tasks) in enumerate(test_matrix, 1):
        label = f"Adim {step_idx}/{total_steps}  -  {workers} worker x {tasks} gorev"
        baseline = baseline_times.get(tasks)

        result = run_step(
            script_path=str(task_script),
            task_params=task_params,
            num_workers=workers,
            task_count=tasks,
            baseline_time=baseline,
            step_label=label,
        )
        all_results.append(result)

        if workers == 1:
            baseline_times[tasks] = result.wall_time

    print_summary_table(all_results, machine_info)


if __name__ == "__main__":
    main()

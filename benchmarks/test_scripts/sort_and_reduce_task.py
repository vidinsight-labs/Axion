#!/usr/bin/env python3
"""
Sort & Reduce  —  CPU-Bound Görev (Orta Zorluk)

Büyük bir rastgele listeyi sıralar ve matematiksel indirgeme uygular.
Saf CPU yükü; hiç I/O yok.
Parametre olarak gelen list_size ve iterations ile zorluk ayarlanabilir.
"""
import random
import math


def main(params, context):
    """
    Args:
        params: {
            "list_size"  : int  — listede kaç eleman (varsayılan 80_000)
            "iterations" : int  — kaç tur tekrar (varsayılan 3)
        }
        context: task_id ve worker_id barındıran execution context

    Returns:
        dict: checksum, list_size, iterations, task_id, worker_id
    """
    list_size  = params.get("list_size",  80_000)
    iterations = params.get("iterations", 3)

    total_checksum = 0.0

    for iteration in range(iterations):
        # Her turda farklı ama deterministik veri üret
        seed = list_size * (iteration + 1)
        rng  = random.Random(seed)
        data = [rng.random() for _ in range(list_size)]

        # O(n log n)  —  sıralama
        data.sort()

        # O(n) float işlemi  —  sqrt indirgeme (bellek erişimi + FPU yükü)
        checksum = sum(math.sqrt(v) for v in data)
        total_checksum += checksum

    return {
        "checksum"   : total_checksum,
        "list_size"  : list_size,
        "iterations" : iterations,
        "task_id"    : context.task_id,
        "worker_id"  : context.worker_id,
    }


if __name__ == "__main__":
    class MockContext:
        task_id   = "test-task"
        worker_id = "test-worker"

    import time
    t      = time.perf_counter()
    result = main({"list_size": 300_000, "iterations": 5}, MockContext())
    elapsed = (time.perf_counter() - t) * 1000
    print(f"Checksum : {result['checksum']:.2f}")
    print(f"Süre     : {elapsed:.1f} ms")

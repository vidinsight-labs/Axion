#!/usr/bin/env python3
"""
CPU-Bound Multiprocessing Test Script
=====================================

Bu script, multiprocessing motorlarını test etmek için tasarlanmıştır.
- Saf CPU-bound
- Uzun süreli
- Worker sayısıyla düzgün ölçeklenir
"""

import math


def main(params, context):
    """
    Belirli bir aralıkta asal sayıları bulur ve ekstra CPU yükü oluşturur.

    Args:
        params:
            {
                "start": 1_000_000,
                "range": 50_000,
                "extra_load": 500
            }

        context:
            task_id, worker_id içerir

    Returns:
        dict
    """

    start = params.get("start", 1_000_000)
    search_range = params.get("range", 50_000)
    extra_load = params.get("extra_load", 500)

    end = start + search_range

    def is_prime(n: int) -> bool:
        if n < 2:
            return False
        if n == 2:
            return True
        if n % 2 == 0:
            return False

        limit = int(math.sqrt(n)) + 1
        for i in range(3, limit, 2):
            if n % i == 0:
                return False
        return True

    primes_found = 0
    cpu_checksum = 0.0

    for num in range(start, end):
        if is_prime(num):
            primes_found += 1

            # 🔥 Ek CPU yükü (branchless math)
            x = num * 0.0001
            for _ in range(extra_load):
                x = math.sin(x) ** 2 + math.cos(x) ** 2

            cpu_checksum += x

    return {
        "task_id": context.task_id,
        "worker_id": context.worker_id,
        "start": start,
        "end": end,
        "primes_found": primes_found,
        "checksum": round(cpu_checksum, 6),
    }


# --------------------------------------------------------------------
# Standalone test
# --------------------------------------------------------------------
if __name__ == "__main__":

    class MockContext:
        task_id = "cpu-test-task"
        worker_id = "local-worker"

    result = main(
        {
            "start": 1_000_000,
            "range": 20_000,
            "extra_load": 300,
        },
        MockContext()
    )

    print("Test sonucu:")
    for k, v in result.items():
        print(f"  {k}: {v}")

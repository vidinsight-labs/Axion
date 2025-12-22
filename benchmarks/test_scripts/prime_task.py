#!/usr/bin/env python3
"""
Asal Sayı Bulma - CPU-Bound Test Script

Bu script, CPU Load Balancer için asal sayıları bulan bir test script'idir.
"""


def main(params, context):
    """
    Belirli aralıkta asal sayıları bulur
    
    Args:
        params: {"start": 1000000, "count": 100} - Başlangıç sayısı ve bulunacak asal sayı adedi
        context: Execution context (task_id, worker_id içerir)
    
    Returns:
        dict: {"primes": [...], "count": count, "start": start}
    """
    start = params.get("start", 1000000)
    count = params.get("count", 100)
    
    def is_prime(n):
        """Bir sayının asal olup olmadığını kontrol eder"""
        if n < 2:
            return False
        if n == 2:
            return True
        if n % 2 == 0:
            return False
        
        # 3'ten başlayarak kareköküne kadar tek sayılarla kontrol et
        for i in range(3, int(n ** 0.5) + 1, 2):
            if n % i == 0:
                return False
        return True
    
    primes = []
    num = start
    while len(primes) < count:
        if is_prime(num):
            primes.append(num)
        num += 1
    
    return {
        "primes": primes,
        "count": len(primes),
        "start": start,
        "task_id": context.task_id,
        "worker_id": context.worker_id
    }


# Test için (script doğrudan çalıştırılırsa)
if __name__ == "__main__":
    class MockContext:
        task_id = "test-task"
        worker_id = "test-worker"
    
    result = main({"start": 1000000, "count": 10}, MockContext())
    print(f"İlk 10 asal sayı (1M'den sonra): {result['primes']}")


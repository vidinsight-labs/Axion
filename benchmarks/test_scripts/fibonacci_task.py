#!/usr/bin/env python3
"""
Fibonacci Hesaplama - CPU-Bound Test Script

Bu script, CPU Load Balancer için Fibonacci sayısı hesaplayan bir test script'idir.
"""


def main(params, context):
    """
    Fibonacci sayısı hesaplar
    
    Args:
        params: {"n": 35} - Hesaplanacak fibonacci sayısı
        context: Execution context (task_id, worker_id içerir)
    
    Returns:
        dict: {"result": fibonacci_value, "n": n, "task_id": task_id}
    """
    n = params.get("n", 30)
    
    def fibonacci(num):
        """Recursive Fibonacci hesaplama"""
        if num <= 1:
            return num
        return fibonacci(num - 1) + fibonacci(num - 2)
    
    result = fibonacci(n)
    
    return {
        "result": result,
        "n": n,
        "task_id": context.task_id,
        "worker_id": context.worker_id
    }


# Test için (script doğrudan çalıştırılırsa)
if __name__ == "__main__":
    class MockContext:
        task_id = "test-task"
        worker_id = "test-worker"
    
    result = main({"n": 35}, MockContext())
    print(f"Fibonacci(35) = {result['result']}")


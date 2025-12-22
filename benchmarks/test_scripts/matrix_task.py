#!/usr/bin/env python3
"""
Matrix Çarpımı - CPU-Bound Test Script

Bu script, CPU Load Balancer için matrix çarpımı yapan bir test script'idir.
"""


def main(params, context):
    """
    İki matrisi çarpar
    
    Args:
        params: {"size": 200} - Matris boyutu (size x size)
        context: Execution context (task_id, worker_id içerir)
    
    Returns:
        dict: {"result_sum": sum, "size": size, "task_id": task_id}
    """
    import random
    
    size = params.get("size", 100)
    
    # İki matris oluştur (rastgele değerlerle)
    matrix_a = [[random.random() for _ in range(size)] for _ in range(size)]
    matrix_b = [[random.random() for _ in range(size)] for _ in range(size)]
    
    # Matrix çarpımı: C = A * B
    result = [[0 for _ in range(size)] for _ in range(size)]
    
    for i in range(size):
        for j in range(size):
            for k in range(size):
                result[i][j] += matrix_a[i][k] * matrix_b[k][j]
    
    # Sonuç toplamı (doğrulama için)
    result_sum = sum(sum(row) for row in result)
    
    return {
        "result_sum": result_sum,
        "size": size,
        "task_id": context.task_id,
        "worker_id": context.worker_id
    }


# Test için (script doğrudan çalıştırılırsa)
if __name__ == "__main__":
    class MockContext:
        task_id = "test-task"
        worker_id = "test-worker"
    
    result = main({"size": 50}, MockContext())
    print(f"Matrix çarpımı (50x50) sonuç toplamı: {result['result_sum']:.2f}")


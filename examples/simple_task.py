#!/usr/bin/env python3
"""
Örnek Script - CPU Load Balancer için

Bu script, CPU Load Balancer'ın çalıştırabileceği örnek bir script'tir.
Script'te main(params, context) fonksiyonu olmalıdır.
"""


def main(params: dict, context) -> dict:
    """
    Ana fonksiyon - görev çalıştırma
    
    Args:
        params: Görev parametreleri
        context: Execution context (task_id, worker_id içerir)
    
    Returns:
        dict: Sonuç verisi
    """
    # Parametreleri al
    value = params.get("value", 0)
    test = params.get("test", False)
    
    # İşlem yap (örnek: basit hesaplama)
    result = value * 2
    
    # Context bilgilerini kullan
    task_id = context.task_id
    worker_id = context.worker_id
    
    # Sonuç döndür
    return {
        "result": result,
        "original_value": value,
        "test_mode": test,
        "task_id": task_id,
        "worker_id": worker_id,
        "status": "success"
    }


# Test için (script doğrudan çalıştırılırsa)
if __name__ == "__main__":
    class MockContext:
        task_id = "test-task"
        worker_id = "test-worker"
    
    result = main({"value": 42, "test": True}, MockContext())
    print(f"Test sonucu: {result}")


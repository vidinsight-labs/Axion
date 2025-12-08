#!/usr/bin/env python3
"""
Gerçek Hayat Örneği: Veri İşleme Script'i

Bu script, gerçek bir veri işleme görevini simüle eder:
- API'den veri çeker (IO-bound)
- Veriyi işler (CPU-bound)
- Sonucu döndürür
"""

import time
import json
from typing import Dict, Any


def main(params: dict, context) -> Dict[str, Any]:
    """
    Ana veri işleme fonksiyonu
    
    Args:
        params: Görev parametreleri
            - url: API URL'i (opsiyonel)
            - data: İşlenecek veri (opsiyonel)
            - operation: İşlem tipi (multiply, sum, filter)
        context: Execution context
    
    Returns:
        dict: İşlem sonucu
    """
    # Parametreleri al
    url = params.get("url")
    data = params.get("data", [])
    operation = params.get("operation", "sum")
    
    # API'den veri çek (simüle edilmiş - IO-bound)
    if url:
        # Gerçek hayatta burada HTTP isteği yapılır
        time.sleep(0.1)  # Network latency simülasyonu
        fetched_data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    else:
        fetched_data = data if data else [1, 2, 3, 4, 5]
    
    # Veriyi işle (CPU-bound)
    result = None
    
    if operation == "sum":
        result = sum(fetched_data)
    elif operation == "multiply":
        result = 1
        for x in fetched_data:
            result *= x
    elif operation == "filter":
        result = [x for x in fetched_data if x % 2 == 0]
    elif operation == "count":
        result = len(fetched_data)
    else:
        result = fetched_data
    
    # Sonuç döndür
    return {
        "success": True,
        "operation": operation,
        "input_count": len(fetched_data),
        "result": result,
        "task_id": context.task_id,
        "worker_id": context.worker_id,
        "processed_at": time.time()
    }


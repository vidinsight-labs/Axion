#!/usr/bin/env python3
"""
Gerçek Hayat Örneği: API Client Script'i

Bu script, harici API'lere istek yapar ve veri toplar.
"""

import time
import json
from typing import Dict, Any, List


def main(params: dict, context) -> Dict[str, Any]:
    """
    API client fonksiyonu
    
    Args:
        params: Görev parametreleri
            - endpoint: API endpoint
            - method: HTTP method (GET, POST)
            - payload: Request payload (POST için)
            - timeout: Timeout süresi
    
    Returns:
        dict: API yanıtı
    """
    endpoint = params.get("endpoint", "https://api.example.com/data")
    method = params.get("method", "GET")
    payload = params.get("payload", {})
    timeout = params.get("timeout", 5.0)
    
    # API isteği simülasyonu (IO-bound)
    # Gerçek hayatta burada requests, httpx vb. kullanılır
    request_time = min(0.5, timeout / 2)  # Network latency
    time.sleep(request_time)
    
    # Simüle edilmiş API yanıtı
    if method == "GET":
        response_data = {
            "status": "success",
            "data": [
                {"id": 1, "name": "Item 1", "value": 100},
                {"id": 2, "name": "Item 2", "value": 200},
                {"id": 3, "name": "Item 3", "value": 300},
            ],
            "count": 3,
            "timestamp": time.time()
        }
    else:  # POST
        response_data = {
            "status": "created",
            "id": 12345,
            "payload": payload,
            "created_at": time.time()
        }
    
    return {
        "success": True,
        "endpoint": endpoint,
        "method": method,
        "response": response_data,
        "request_time_seconds": request_time,
        "task_id": context.task_id,
        "worker_id": context.worker_id
    }


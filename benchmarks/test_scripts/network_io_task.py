#!/usr/bin/env python3
"""
Network I/O Test Script (Real HTTP Requests)
=============================================

Bu script, gerçek HTTP istekleri yapar.
"""

import time
import requests
import statistics
from typing import Dict, Any


def main(params, context):
    """
    Gerçek HTTP istekleri yapar.

    Args:
        params:
            {
                "urls": [
                    "https://httpbin.org/delay/1",
                    "https://httpbin.org/get",
                    "https://jsonplaceholder.typicode.com/posts/1"
                ],
                "timeout": 30,
                "retry_count": 2
            }
        context:
            task_id, worker_id içerir

    Returns:
        dict
    """
    try:
        # requests modülünü kontrol et
        try:
            import requests
        except ImportError:
            return {
                "task_id": getattr(context, 'task_id', 'unknown'),
                "worker_id": getattr(context, 'worker_id', 'unknown'),
                "error": "requests modülü bulunamadı. Lütfen 'pip install requests' ile yükleyin.",
                "successful_requests": 0,
                "failed_requests": 0
            }
        
        urls = params.get("urls", ["https://httpbin.org/get"])
        if not isinstance(urls, list):
            urls = [urls] if urls else ["https://httpbin.org/get"]
        
        timeout = params.get("timeout", 30)
        retry_count = params.get("retry_count", 2)
        
        start_time = time.time()
        successful_requests = 0
        failed_requests = 0
        total_bytes_sent = 0
        total_bytes_received = 0
        latencies = []
        
        for url in urls:
            if not url or not isinstance(url, str):
                failed_requests += 1
                continue
            
            for attempt in range(retry_count + 1):
                try:
                    request_start = time.time()
                    
                    # Gerçek HTTP isteği
                    response = requests.get(url, timeout=timeout)
                    
                    request_latency = (time.time() - request_start) * 1000  # ms
                    latencies.append(request_latency)
                    
                    # Response bilgileri
                    response_size = len(response.content) if response.content else 0
                    total_bytes_received += response_size
                    
                    # Request size (yaklaşık)
                    try:
                        request_size = len(str(response.request.headers)) if response.request else 0
                    except:
                        request_size = 0
                    total_bytes_sent += request_size
                    
                    if response.status_code == 200:
                        successful_requests += 1
                        break  # Başarılı, retry'e gerek yok
                    else:
                        if attempt == retry_count:
                            failed_requests += 1
                except requests.exceptions.Timeout:
                    if attempt == retry_count:
                        failed_requests += 1
                except requests.exceptions.RequestException as e:
                    if attempt == retry_count:
                        failed_requests += 1
                except Exception as e:
                    if attempt == retry_count:
                        failed_requests += 1
        
        elapsed = time.time() - start_time
        
        # Sonuç hesaplamaları (hata durumunda bile döndür)
        result = {
            "task_id": getattr(context, 'task_id', 'unknown'),
            "worker_id": getattr(context, 'worker_id', 'unknown'),
            "num_urls": len(urls),
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "total_bytes_sent": total_bytes_sent,
            "total_bytes_received": total_bytes_received,
            "elapsed_time": round(elapsed, 3),
        }
        
        # Latency istatistikleri (sadece varsa)
        if latencies:
            result["avg_latency_ms"] = round(statistics.mean(latencies), 2)
            result["min_latency_ms"] = round(min(latencies), 2)
            result["max_latency_ms"] = round(max(latencies), 2)
        else:
            result["avg_latency_ms"] = 0
            result["min_latency_ms"] = 0
            result["max_latency_ms"] = 0
        
        # Throughput hesaplama
        if elapsed > 0:
            total_bytes = total_bytes_sent + total_bytes_received
            result["throughput_mbps"] = round((total_bytes / (1024 * 1024)) / elapsed, 2)
        else:
            result["throughput_mbps"] = 0
        
        return result
    
    except Exception as e:
        # Herhangi bir beklenmeyen hata durumunda bile bir dict döndür
        return {
            "task_id": getattr(context, 'task_id', 'unknown'),
            "worker_id": getattr(context, 'worker_id', 'unknown'),
            "error": str(e),
            "successful_requests": 0,
            "failed_requests": 0,
            "elapsed_time": 0
        }


# Standalone test
if __name__ == "__main__":
    class MockContext:
        task_id = "network-test-task"
        worker_id = "local-worker"
    
    result = main(
        {
            "urls": [
                "https://httpbin.org/delay/1",
                "https://httpbin.org/get",
                "https://jsonplaceholder.typicode.com/posts/1"
            ],
            "timeout": 30,
            "retry_count": 1
        },
        MockContext()
    )
    
    print("Test sonucu:")
    for k, v in result.items():
        print(f"  {k}: {v}")


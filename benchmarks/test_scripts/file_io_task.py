#!/usr/bin/env python3
"""
File I/O Test Script
====================

Bu script, dosya I/O operasyonlarını test eder.
- Dosya okuma/yazma
- Büyük dosya işleme
- Concurrent file operations
"""

import os
import time
import tempfile
from pathlib import Path


def main(params, context):
    """
    Dosya I/O operasyonları gerçekleştirir.

    Args:
        params:
            {
                "operation": "read" | "write" | "readwrite",
                "file_size": 1024,  # KB
                "num_files": 5,
                "chunk_size": 1024  # bytes
            }
        context:
            task_id, worker_id içerir

    Returns:
        dict
    """
    operation = params.get("operation", "readwrite")
    file_size_kb = params.get("file_size", 1024)
    num_files = params.get("num_files", 5)
    chunk_size = params.get("chunk_size", 1024)
    
    file_size_bytes = file_size_kb * 1024
    temp_dir = tempfile.gettempdir()
    
    files_processed = 0
    total_bytes = 0
    start_time = time.time()
    
    try:
        if operation in ["write", "readwrite"]:
            # Dosya yazma
            for i in range(num_files):
                file_path = Path(temp_dir) / f"io_test_{context.task_id}_{i}.tmp"
                
                with open(file_path, "wb") as f:
                    written = 0
                    while written < file_size_bytes:
                        chunk = b"X" * min(chunk_size, file_size_bytes - written)
                        f.write(chunk)
                        written += len(chunk)
                        # I/O blocking simülasyonu
                        time.sleep(0.001)  # 1ms I/O wait
                
                total_bytes += file_size_bytes
                files_processed += 1
        
        if operation in ["read", "readwrite"]:
            # Dosya okuma
            for i in range(num_files):
                file_path = Path(temp_dir) / f"io_test_{context.task_id}_{i}.tmp"
                
                if file_path.exists():
                    with open(file_path, "rb") as f:
                        read_bytes = 0
                        while read_bytes < file_size_bytes:
                            chunk = f.read(chunk_size)
                            if not chunk:
                                break
                            read_bytes += len(chunk)
                            # I/O blocking simülasyonu
                            time.sleep(0.001)  # 1ms I/O wait
                    
                    total_bytes += read_bytes
                    files_processed += 1
        
        # Cleanup
        for i in range(num_files):
            file_path = Path(temp_dir) / f"io_test_{context.task_id}_{i}.tmp"
            if file_path.exists():
                try:
                    file_path.unlink()
                except:
                    pass
        
        elapsed = time.time() - start_time
        
        return {
            "task_id": context.task_id,
            "worker_id": context.worker_id,
            "operation": operation,
            "files_processed": files_processed,
            "total_bytes": total_bytes,
            "elapsed_time": round(elapsed, 3),
            "throughput_mbps": round((total_bytes / (1024 * 1024)) / elapsed, 2) if elapsed > 0 else 0
        }
    
    except Exception as e:
        return {
            "task_id": context.task_id,
            "worker_id": context.worker_id,
            "error": str(e),
            "files_processed": files_processed,
            "total_bytes": total_bytes
        }


# Standalone test
if __name__ == "__main__":
    class MockContext:
        task_id = "io-test-task"
        worker_id = "local-worker"
    
    result = main(
        {
            "operation": "readwrite",
            "file_size": 512,  # 512 KB
            "num_files": 3,
            "chunk_size": 1024
        },
        MockContext()
    )
    
    print("Test sonucu:")
    for k, v in result.items():
        print(f"  {k}: {v}")


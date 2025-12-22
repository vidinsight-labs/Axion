#!/usr/bin/env python3
"""
Database I/O Test Script (Real SQLite Operations)
==================================================

Bu script, gerçek SQLite veritabanı işlemleri yapar.
"""

import time
import sqlite3
import os
import tempfile
import statistics
from pathlib import Path
from typing import Dict, Any


def main(params, context):
    """
    Gerçek SQLite veritabanı işlemleri yapar.

    Args:
        params:
            {
                "db_path": "/path/to/db.db",  # Opsiyonel, yoksa geçici dosya oluşturulur
                "num_queries": 20,
                "query_type": "select" | "insert" | "update" | "mixed",
                "rows_per_query": 100,
                "cleanup": True  # Test sonrası tabloyu temizle
            }
        context:
            task_id, worker_id içerir

    Returns:
        dict
    """
    db_path = params.get("db_path")
    num_queries = params.get("num_queries", 20)
    query_type = params.get("query_type", "select")
    rows_per_query = params.get("rows_per_query", 100)
    cleanup = params.get("cleanup", False)
    
    # SQLite için geçici dosya oluştur (eğer path verilmemişse)
    is_temp = False
    if not db_path:
        temp_dir = tempfile.gettempdir()
        db_path = os.path.join(temp_dir, f"io_test_{context.task_id}_{int(time.time())}.db")
        is_temp = True
    
    start_time = time.time()
    queries_executed = 0
    successful_queries = 0
    failed_queries = 0
    total_rows = 0
    latencies = []
    
    conn = None
    
    try:
        # SQLite bağlantısı
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        
        # Test tablosu oluştur (yoksa)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS io_test_table (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                worker_id TEXT,
                value INTEGER,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # İlk test için bazı veriler ekle (SELECT için)
        cursor.execute("SELECT COUNT(*) FROM io_test_table")
        existing_count = cursor.fetchone()[0]
        if existing_count < rows_per_query:
            for i in range(rows_per_query - existing_count):
                cursor.execute("""
                    INSERT INTO io_test_table (task_id, worker_id, value, data)
                    VALUES (?, ?, ?, ?)
                """, (f"init-{context.task_id}", "init-worker", i, f"Initial data {i}"))
        conn.commit()
        
        # Query'leri çalıştır
        for i in range(num_queries):
            try:
                query_start = time.time()
                
                if query_type == "select" or (query_type == "mixed" and i % 3 == 0):
                    # SELECT query
                    cursor.execute("""
                        SELECT * FROM io_test_table 
                        WHERE value > ? 
                        LIMIT ?
                    """, (0, rows_per_query))
                    rows = cursor.fetchall()
                    total_rows += len(rows)
                
                elif query_type == "insert" or (query_type == "mixed" and i % 3 == 1):
                    # INSERT query
                    cursor.execute("""
                        INSERT INTO io_test_table (task_id, worker_id, value, data)
                        VALUES (?, ?, ?, ?)
                    """, (
                        context.task_id,
                        context.worker_id,
                        i,
                        f"Test data {i} from {context.worker_id}"
                    ))
                    total_rows += 1
                    conn.commit()
                
                elif query_type == "update" or (query_type == "mixed" and i % 3 == 2):
                    # UPDATE query
                    cursor.execute("""
                        UPDATE io_test_table 
                        SET value = ?, data = ?
                        WHERE id = (SELECT MIN(id) FROM io_test_table)
                    """, (i * 10, f"Updated {i} by {context.worker_id}"))
                    total_rows += cursor.rowcount
                    conn.commit()
                
                query_latency = (time.time() - query_start) * 1000  # ms
                latencies.append(query_latency)
                queries_executed += 1
                successful_queries += 1
            
            except Exception as e:
                failed_queries += 1
        
        elapsed = time.time() - start_time
        
        result = {
            "task_id": context.task_id,
            "worker_id": context.worker_id,
            "db_type": "sqlite",
            "query_type": query_type,
            "num_queries": num_queries,
            "queries_executed": queries_executed,
            "successful_queries": successful_queries,
            "failed_queries": failed_queries,
            "total_rows": total_rows,
            "elapsed_time": round(elapsed, 3),
            "avg_latency_ms": round(statistics.mean(latencies), 2) if latencies else 0,
            "min_latency_ms": round(min(latencies), 2) if latencies else 0,
            "max_latency_ms": round(max(latencies), 2) if latencies else 0,
            "queries_per_second": round(queries_executed / elapsed, 2) if elapsed > 0 else 0
        }
        
        # Cleanup
        if cleanup:
            try:
                cursor.execute("DROP TABLE IF EXISTS io_test_table")
                conn.commit()
            except:
                pass
        
        return result
    
    except Exception as e:
        return {
            "task_id": context.task_id,
            "worker_id": context.worker_id,
            "error": str(e),
            "queries_executed": queries_executed,
            "successful_queries": successful_queries,
            "failed_queries": failed_queries
        }
    
    finally:
        # Bağlantıyı kapat
        if conn:
            try:
                conn.close()
            except:
                pass
        
        # Geçici SQLite dosyasını sil
        if is_temp and db_path and os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except:
                pass


# Standalone test
if __name__ == "__main__":
    class MockContext:
        task_id = "db-test-task"
        worker_id = "local-worker"
    
    result = main(
        {
            "num_queries": 30,
            "query_type": "mixed",
            "rows_per_query": 50,
            "cleanup": True
        },
        MockContext()
    )
    
    print("Test sonucu:")
    for k, v in result.items():
        print(f"  {k}: {v}")


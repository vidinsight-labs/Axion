
import time
import math

def module():
    return TestTasks()

def main(params, context):
    """
    Main entry point for the task.
    Args:
        params: Task parameters
        context: Execution context (task_id, worker_id)
    """
    task_type = params.get("type", "light")
    
    # Daha hassas zaman ölçümü
    start_time = time.perf_counter()
    
    tasks = TestTasks()
    
    if task_type == "light":
        result = tasks._light_task()
    elif task_type == "medium":
        result = tasks._medium_task()
    elif task_type == "heavy":
        result = tasks._heavy_task()
    else:
        result = {"error": "Unknown task type"}
        
    duration = time.perf_counter() - start_time
    result["duration"] = duration
    result["worker_id"] = context.worker_id
    return result

class TestTasks:
    def _light_task(self):
        # Hafif: 10.000'e kadar toplama
        val = sum(range(10000))
        return {"result": val, "complexity": "light"}

    def _medium_task(self):
        # Orta: 20.000'e kadar asal sayılar
        # Bu işlem modern CPU'da hissedilir bir süre almalı
        count = 0
        for num in range(2, 20000):
            is_prime = True
            for i in range(2, int(num ** 0.5) + 1):
                if num % i == 0:
                    is_prime = False
                    break
            if is_prime:
                count += 1
        return {"count": count, "complexity": "medium"}

    def _heavy_task(self):
        # Ağır: 80.000'e kadar asal sayılar
        # Bu işlem kesinlikle zaman almalı
        count = 0
        for num in range(2, 80000):
            is_prime = True
            for i in range(2, int(num ** 0.5) + 1):
                if num % i == 0:
                    is_prime = False
                    break
            if is_prime:
                count += 1
        return {"count": count, "complexity": "heavy"}

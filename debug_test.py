
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from cpu_load_balancer import Engine

print("Starting engine...")
try:
    engine = Engine()
    engine.start()
    print("Engine started.")
    time.sleep(2)
    engine.shutdown()
    print("Engine stopped.")
except Exception as e:
    print(f"Error: {e}")

#!/usr/bin/env python3
"""
Axion - Advanced Task Execution Engine

Main entry point for the Axion CLI tool.

Usage:
    python -m axion.main
    python -m axion.main --config config.yaml
    python -m axion.main --enable-isolation --isolation-profile balanced
    python -m axion.main --interactive
"""

import argparse
import sys
import os
import signal
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from .engine import Engine
from .config import EngineConfig
from .task.task import Task
from .core.enums import TaskType
from .core.exceptions import EngineError, TaskError, ConfigError

# Import CPU isolation components
try:
    from .isolation.cpu import CpuIsolationManager
    from .isolation.cpu.exceptions import (
        IsolationBackendError,
        IsolationPermissionError,
        IsolationUnsupportedError
    )
    ISOLATION_AVAILABLE = True
except ImportError:
    ISOLATION_AVAILABLE = False
    CpuIsolationManager = None

logger = logging.getLogger(__name__)


class Axion:
    """Modern Axion CLI application with CPU isolation support"""

    def __init__(self, config: EngineConfig, enable_isolation: bool = False):
        """
        Initialize Axion application.

        Args:
            config: Engine configuration
            enable_isolation: Enable CPU isolation (overrides config setting)
        """
        self.config = config
        self.engine: Optional[Engine] = None
        self.isolation_manager: Optional[CpuIsolationManager] = None
        self.running = False
        self.start_time: Optional[float] = None

        # Create isolation manager if enabled
        if ISOLATION_AVAILABLE and (enable_isolation or config.cpu_isolation.enabled):
            self.isolation_manager = CpuIsolationManager(config.cpu_isolation)
            logger.info("CPU isolation manager created")
        elif enable_isolation and not ISOLATION_AVAILABLE:
            logger.warning("CPU isolation requested but not available (import error)")

    def start(self) -> bool:
        """Start Engine and CPU isolation"""
        print(">> Axion starting...")
        print(f"   CPU workers: {self.config.cpu_bound_count}")
        print(f"   IO workers: {self.config.io_bound_count}")

        try:
            # 1. Start CPU isolation (if enabled)
            if self.isolation_manager:
                print("   Initializing CPU isolation...")
                try:
                    partition = self.isolation_manager.start()
                    if partition.enabled:
                        print(f"   [OK] CPU isolation active")
                        print(f"     Profile: {partition.profile}")
                        print(f"     System CPUs: {partition.system_cpus} ({partition.system_cpu_count} cores)")
                        print(f"     Axion CPUs: {partition.axion_cpus} ({partition.axion_cpu_count} cores)")
                    else:
                        print(f"   [WARN] CPU isolation disabled: {partition.reason}")
                except (IsolationBackendError, IsolationPermissionError, IsolationUnsupportedError) as e:
                    print(f"   [WARN] CPU isolation failed: {e}")
                    logger.warning(f"CPU isolation failed: {e}")

            # 2. Start Engine (manager injection ile worker registration pool'da yapılır)
            self.engine = Engine(self.config, isolation_manager=self.isolation_manager)
            self.engine.start()

            # 3. Setup signal handlers
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)

            self.running = True
            self.start_time = time.time()

            print("[OK] Axion started successfully!")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to start Axion: {e}", file=sys.stderr)
            logger.error(f"Startup failed: {e}", exc_info=True)
            return False

    def shutdown(self):
        """Graceful shutdown with isolation cleanup"""
        if not self.running:
            return

        print("\n>> Shutting down Axion...")

        # Shutdown engine first
        if self.engine:
            print("   Stopping engine...")
            self.engine.shutdown()

        # Cleanup isolation (restores systemd settings if configured)
        if self.isolation_manager:
            print("   Cleaning up CPU isolation...")
            try:
                self.isolation_manager.stop()
                print("   [OK] CPU isolation cleaned up")
            except Exception as e:
                logger.warning(f"Isolation cleanup failed: {e}")

        self.running = False
        print("[OK] Axion stopped")

    def _signal_handler(self, signum, frame):
        """Signal handler for graceful shutdown"""
        print(f"\n[WARN] Signal received ({signum}), shutting down...")
        self.shutdown()
        sys.exit(0)

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status including isolation"""
        status = {
            "engine": {
                "is_running": self.running,
                "uptime_seconds": time.time() - self.start_time if self.start_time else 0
            }
        }

        # Add isolation status
        if self.isolation_manager:
            try:
                iso_status = self.isolation_manager.status()
                status["isolation"] = iso_status
            except Exception as e:
                logger.warning(f"Failed to get isolation status: {e}")
                status["isolation"] = {"error": str(e)}

        # Add engine component status
        if self.engine:
            try:
                engine_status = self.engine.get_status()
                status.update(engine_status)
            except Exception as e:
                logger.warning(f"Failed to get engine status: {e}")

        return status

    def show_status(self):
        """Display formatted status"""
        if not self.engine:
            print("[ERROR] Engine not started")
            return

        status = self.get_status()

        # Engine status
        print("\n" + "=" * 60)
        print("AXION ENGINE STATUS")
        print("=" * 60)

        engine_info = status.get("engine", {})
        is_running = engine_info.get("is_running", False)
        uptime = engine_info.get("uptime_seconds", 0)

        print(f"Running: {'Yes' if is_running else 'No'}")
        if uptime > 0:
            print(f"Uptime: {self._format_uptime(uptime)}")

        # CPU Isolation status
        if "isolation" in status:
            print("\n" + "-" * 60)
            print("CPU ISOLATION")
            print("-" * 60)
            self._show_isolation_status(status["isolation"])

        # Workers
        print("\n" + "-" * 60)
        print("WORKERS")
        print("-" * 60)

        components = status.get("components", {})
        if "process_pool" in components:
            pool_metrics = components["process_pool"].get("metrics", {})
            print(f"CPU-bound: {pool_metrics.get('cpu_workers', 0)} workers")
            print(f"IO-bound: {pool_metrics.get('io_workers', 0)} workers")
            print(f"Active threads: {pool_metrics.get('total_active_threads', 0)}")

        # Queues
        print("\n" + "-" * 60)
        print("QUEUES")
        print("-" * 60)

        if "input_queue" in components:
            input_metrics = components["input_queue"].get("metrics", {})
            print(f"Input: {input_metrics.get('size', 0)} / {input_metrics.get('maxsize', '?')}")

        if "output_queue" in components:
            output_metrics = components["output_queue"].get("metrics", {})
            print(f"Output: {output_metrics.get('size', 0)} / {output_metrics.get('maxsize', '?')}")

        # Components health
        print("\n" + "-" * 60)
        print("COMPONENTS")
        print("-" * 60)

        for name, comp in components.items():
            health = comp.get("health", "UNKNOWN")
            print(f"{name}: {health}")

        print("=" * 60)

    def _show_isolation_status(self, iso_status: Dict[str, Any]):
        """Display CPU isolation status"""
        if "error" in iso_status:
            print(f"Error: {iso_status['error']}")
            return

        enabled = iso_status.get("enabled", False)
        print(f"Enabled: {'Yes' if enabled else 'No'}")

        if enabled:
            print(f"Backend: {iso_status.get('backend_name', 'unknown')}")
            print(f"Active: {'Yes' if iso_status.get('active', False) else 'No'}")

            partition = iso_status.get("partition", {})
            if partition:
                print(f"Profile: {partition.get('profile', 'unknown')}")
                print(f"System CPUs: {partition.get('system_cpus', '?')} ({partition.get('system_cpu_count', '?')} cores)")
                print(f"Axion CPUs: {partition.get('axion_cpus', '?')} ({partition.get('axion_cpu_count', '?')} cores)")

    def show_worker_details(self):
        """Display detailed worker information"""
        if not self.engine or not self.engine._process_pool:
            print("[ERROR] Engine not started")
            return

        pool = self.engine._process_pool

        print("\n" + "=" * 60)
        print("WORKER DETAILS")
        print("=" * 60)

        # CPU workers
        print("\nCPU-bound Workers:")
        for worker in pool._cpu_workers:
            pid = worker._process.pid if worker._process else "N/A"
            print(f"  {worker._worker_id}: PID {pid}")

        # IO workers
        print("\nIO-bound Workers:")
        for worker in pool._io_workers:
            pid = worker._process.pid if worker._process else "N/A"
            print(f"  {worker._worker_id}: PID {pid}")

        print("=" * 60)

    def show_config(self):
        """Display current configuration"""
        print("\n" + "=" * 60)
        print("CONFIGURATION")
        print("=" * 60)

        print(f"\nEngine:")
        print(f"  CPU workers: {self.config.cpu_bound_count}")
        print(f"  IO workers: {self.config.io_bound_count}")
        print(f"  CPU task limit: {self.config.cpu_bound_task_limit}")
        print(f"  IO task limit: {self.config.io_bound_task_limit}")
        print(f"  Input queue size: {self.config.input_queue_size}")
        print(f"  Output queue size: {self.config.output_queue_size}")
        print(f"  Log level: {self.config.log_level}")

        if self.isolation_manager:
            iso_config = self.config.cpu_isolation
            print(f"\nCPU Isolation:")
            print(f"  Enabled: {iso_config.enabled}")
            print(f"  Backend: {iso_config.backend}")
            print(f"  Profile: {iso_config.profile}")
            print(f"  System CPUs: {iso_config.system_cpus}")
            print(f"  Axion CPUs: {iso_config.axion_cpus}")

        print("=" * 60)

    def _format_uptime(self, seconds: float) -> str:
        """Format uptime in human-readable format"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"

    def run_interactive(self):
        """Interactive mode - accept user commands"""
        if not self.engine:
            print("[ERROR] Engine not started")
            return

        print("\n>> Interactive Mode")
        print("   Type 'help' for available commands")

        while self.running:
            try:
                command = input("\n> ").strip()

                if not command:
                    continue

                self._handle_command(command)

            except KeyboardInterrupt:
                break
            except EOFError:
                break
            except Exception as e:
                print(f"[ERROR] {e}")
                logger.error(f"Command error: {e}", exc_info=True)

    def _handle_command(self, command: str):
        """Handle interactive command"""
        parts = command.split()
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        if cmd in ("quit", "exit"):
            print("Exiting...")
            self.shutdown()
            sys.exit(0)

        elif cmd == "status":
            self.show_status()

        elif cmd == "workers":
            self.show_worker_details()

        elif cmd == "isolation":
            if self.isolation_manager:
                status = self.get_status()
                print("\n" + "=" * 60)
                print("CPU ISOLATION STATUS")
                print("=" * 60)
                self._show_isolation_status(status.get("isolation", {}))
                print("=" * 60)
            else:
                print("[ERROR] CPU isolation not enabled")

        elif cmd == "config":
            self.show_config()

        elif cmd == "submit":
            if len(args) < 1:
                print("Usage: submit <script_path> [cpu|io]")
                return

            script_path = args[0]
            task_type_str = args[1].lower() if len(args) > 1 else "io"

            if task_type_str == "cpu":
                task_type = TaskType.CPU_BOUND
            else:
                task_type = TaskType.IO_BOUND

            self._submit_task(script_path, task_type)

        elif cmd == "result":
            if len(args) < 1:
                print("Usage: result <task_id>")
                return

            task_id = args[0]
            self._get_result(task_id)

        elif cmd == "help":
            self._show_help()

        else:
            print(f"[ERROR] Unknown command: {cmd}")
            print("   Type 'help' for available commands")

    def _submit_task(self, script_path: str, task_type: TaskType):
        """Submit a task"""
        if not Path(script_path).exists():
            print(f"[ERROR] Script not found: {script_path}")
            return

        try:
            task = Task.create(
                script_path=script_path,
                params={"submitted_from": "interactive"},
                task_type=task_type
            )

            task_id = self.engine.submit_task(task)
            type_str = "CPU" if task_type == TaskType.CPU_BOUND else "IO"
            print(f"[OK] Task submitted: {task_id[:8]}... (type: {type_str})")
            print(f"   Use 'result {task_id[:8]}' to get the result")

        except (TaskError, EngineError) as e:
            print(f"[ERROR] Failed to submit task: {e}")

    def _get_result(self, task_id: str):
        """Get task result"""
        print(f"[...] Waiting for result of {task_id}...")

        try:
            result = self.engine.get_result(task_id, timeout=30)

            if result:
                if result.is_success:
                    print(f"[OK] Task successful!")
                    print(f"   Result: {result.data}")
                    print(f"   Duration: {result.duration:.3f}s")
                else:
                    print(f"[ERROR] Task failed: {result.error}")
            else:
                print("[WARN] Timeout - result not available")

        except Exception as e:
            print(f"[ERROR] Error getting result: {e}")

    def _show_help(self):
        """Show help for interactive commands"""
        print("\n" + "=" * 60)
        print("AVAILABLE COMMANDS")
        print("=" * 60)
        print("\n  status              - Show engine status and metrics")
        print("  submit <script>     - Submit task (default: IO_BOUND)")
        print("  submit <script> cpu - Submit CPU-bound task")
        print("  submit <script> io  - Submit IO-bound task")
        print("  result <task_id>    - Get result for specific task")
        print("  workers             - Show worker details and PIDs")
        print("  isolation           - Show CPU isolation details (if enabled)")
        print("  config              - Display current configuration")
        print("  help                - Show this help")
        print("  quit, exit          - Shutdown and exit")
        print("\n" + "=" * 60)

    def run_demo(self):
        """Run demo with example tasks"""
        if not self.engine:
            print("[ERROR] Engine not started")
            return

        print("\n>> Demo Mode")
        print("   This would run example tasks")
        print("   Demo implementation can be added here")
        print("   For now, switching to interactive mode...")
        print()
        self.run_interactive()


def merge_config_from_cli(config: EngineConfig, args: argparse.Namespace) -> EngineConfig:
    """
    Merge CLI arguments into config.

    Priority: CLI args > config file > defaults
    """
    # Override engine settings
    if args.cpu_workers is not None:
        config.cpu_bound_count = args.cpu_workers

    if args.io_workers is not None:
        config.io_bound_count = args.io_workers

    if args.log_level is not None:
        config.log_level = args.log_level.upper()

    # Override isolation settings
    if args.enable_isolation:
        config.cpu_isolation.enabled = True

    if args.isolation_profile is not None:
        config.cpu_isolation.profile = args.isolation_profile

    if args.isolation_backend is not None:
        config.cpu_isolation.backend = args.isolation_backend

    if args.system_cpus is not None:
        config.cpu_isolation.system_cpus = args.system_cpus

    if args.axion_cpus is not None:
        config.cpu_isolation.axion_cpus = args.axion_cpus

    if args.affinity_mode is not None:
        config.cpu_isolation.affinity_mode = args.affinity_mode

    if args.affinity_cpus is not None:
        config.cpu_isolation.affinity_cpus = args.affinity_cpus

    return config


def create_default_yaml_config(path: Optional[str] = None):
    """Generate default config.yaml with cpu_isolation section"""
    if path is None:
        path = "config.yaml"

    config_path = Path(path)

    if config_path.exists():
        print(f"[WARN] Config file already exists: {path}")
        response = input("Overwrite? (y/N): ").strip().lower()
        if response != 'y':
            print("Cancelled")
            return

    # Read template from axion/config/config.yaml
    template_path = Path(__file__).parent / "config" / "config.yaml"

    if template_path.exists():
        content = template_path.read_text(encoding="utf-8")
    else:
        # Fallback to minimal config
        content = """# Axion Configuration

# Queue settings
input_queue_size: 1000
output_queue_size: 10000

# Worker settings
cpu_bound_count: 3
io_bound_count: null  # Auto-detect

cpu_bound_task_limit: 1
io_bound_task_limit: 20

# General settings
log_level: INFO
queue_poll_timeout: 1.0

# CPU isolation/affinity settings
cpu_isolation:
  enabled: false
  backend: auto  # auto | linux_systemd_cgroup | noop
  profile: balanced  # safe | balanced | performance | custom
  system_cpus: auto
  axion_cpus: auto
  restrict_system_slices: true
  restore_on_shutdown: true
  cgroup_root: /sys/fs/cgroup/axion-runtime
  min_cpus_required: 4
  fail_on_error: false
  affinity_mode: disabled  # disabled | auto | custom
  affinity_cpus: auto
"""

    config_path.write_text(content, encoding="utf-8")
    print(f"[OK] Default config created: {path}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        prog="python -m axion.main",
        description="Axion - Advanced Task Execution Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start with default config
  python -m axion.main

  # Use custom YAML config
  python -m axion.main --config my_config.yaml

  # Enable CPU isolation with balanced profile
  python -m axion.main --enable-isolation --isolation-profile balanced

  # Run demo with isolation
  python -m axion.main --demo --enable-isolation

  # Quick status check
  python -m axion.main --status

  # Generate default config file
  python -m axion.main --create-config

For more information, visit: https://github.com/vidinsight-labs/axion
        """
    )

    # General options
    general = parser.add_argument_group('General')
    general.add_argument(
        '--config', '-c',
        type=str,
        help='YAML config file path (default: auto-detect)'
    )
    general.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Log level'
    )
    general.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Interactive mode (default)'
    )
    general.add_argument(
        '--demo', '-d',
        action='store_true',
        help='Run demo with example tasks'
    )
    general.add_argument(
        '--status', '-s',
        action='store_true',
        help='Show status and exit'
    )
    general.add_argument(
        '--create-config',
        action='store_true',
        help='Generate default config.yaml and exit'
    )

    # Worker options
    workers = parser.add_argument_group('Workers')
    workers.add_argument(
        '--cpu-workers',
        type=int,
        help='CPU-bound worker count'
    )
    workers.add_argument(
        '--io-workers',
        type=int,
        help='IO-bound worker count'
    )

    # CPU Isolation options
    isolation = parser.add_argument_group('CPU Isolation (optional)')
    isolation.add_argument(
        '--enable-isolation',
        action='store_true',
        help='Enable CPU isolation'
    )
    isolation.add_argument(
        '--isolation-profile',
        type=str,
        choices=['safe', 'balanced', 'performance', 'custom'],
        help='CPU isolation profile'
    )
    isolation.add_argument(
        '--isolation-backend',
        type=str,
        choices=['auto', 'linux_systemd_cgroup', 'noop'],
        help='CPU isolation backend'
    )
    isolation.add_argument(
        '--system-cpus',
        type=str,
        help='System CPU range (e.g., "0-1")'
    )
    isolation.add_argument(
        '--axion-cpus',
        type=str,
        help='Axion CPU range (e.g., "2-7")'
    )
    isolation.add_argument(
        '--affinity-mode',
        type=str,
        choices=['disabled', 'auto', 'custom'],
        help='CPU affinity mode (when isolation disabled)'
    )
    isolation.add_argument(
        '--affinity-cpus',
        type=str,
        help='CPU affinity range (e.g., "2-3")'
    )

    args = parser.parse_args()

    # Handle --create-config
    if args.create_config:
        create_default_yaml_config()
        return 0

    # Load configuration
    config = None

    if args.config:
        # Load from specified file
        try:
            config = EngineConfig.from_yaml(args.config)
            print(f"[OK] Loaded config from: {args.config}")
        except Exception as e:
            print(f"[ERROR] Failed to load config from {args.config}: {e}", file=sys.stderr)
            return 1
    else:
        # Try auto-detect: config.yaml in current directory or package config
        candidates = [
            Path("config.yaml"),
            Path("axion/config/config.yaml"),
            Path(__file__).parent / "config" / "config.yaml"
        ]

        for candidate in candidates:
            if candidate.exists():
                try:
                    config = EngineConfig.from_yaml(str(candidate))
                    print(f"[OK] Loaded config from: {candidate}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to load {candidate}: {e}")

    # Use defaults if no config found
    if config is None:
        config = EngineConfig()
        print("[OK] Using default configuration")

    # Merge CLI overrides
    config = merge_config_from_cli(config, args)

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create Axion application
    app = Axion(config, enable_isolation=args.enable_isolation)

    # Start engine
    if not app.start():
        return 1

    try:
        # Mode selection
        if args.status:
            # Quick status and exit
            app.show_status()
        elif args.demo:
            # Demo mode
            app.run_demo()
        else:
            # Interactive mode (default)
            app.run_interactive()

    except Exception as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        logger.error(f"Runtime error: {e}", exc_info=True)
        return 1

    finally:
        app.shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())

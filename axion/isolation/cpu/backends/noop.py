"""İzolasyon ve affinity uygulamayan no-op backend."""

from typing import Any

from ..backend import BackendOutcome, CpuIsolationBackend
from ..partition_planner import CpuPartition


class NoopBackend(CpuIsolationBackend):
    """
    Hiçbir izolasyon uygulamayan backend.

    Kullanım:
        - config.enabled=False ve affinity_mode="disabled"
        - Platform desteklemiyorsa ve fail_on_error=False (auto fallback)
        - config.backend="noop" (test/development)
    """

    name = "noop"

    def __init__(self, reason: str | None = None) -> None:
        self._reason = reason or "isolation disabled"
        self._started = False

    def start(self, partition: CpuPartition) -> BackendOutcome:
        self._started = True
        return BackendOutcome(backend_name=self.name, active=False, reason=self._reason)

    def add_worker(self, pid: int) -> None:
        return None

    def stop(self) -> None:
        self._started = False

    def status(self) -> dict[str, Any]:
        return {
            "backend": self.name,
            "active": False,
            "reason": self._reason,
            "started": self._started,
        }

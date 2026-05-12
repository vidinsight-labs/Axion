"""psutil tabanlı cross-platform CPU affinity backend'i."""

import logging
import os
from typing import Any

import psutil

from ..backend import BackendOutcome, CpuIsolationBackend
from ..exceptions import IsolationBackendError, IsolationUnsupportedError
from ..partition_planner import CpuPartition
from ..utils import format_cpu_range, parse_cpu_range


logger = logging.getLogger(__name__)


class AffinityBackend(CpuIsolationBackend):
    """
    Worker processlerine psutil.Process.cpu_affinity ile CPU pinning uygular.

    Davranış:
        - affinity_mode="auto": partition.axion_cpus kullanılır; partition disabled
          ise tüm logical CPU'lar.
        - affinity_mode="custom": config.affinity_cpus kullanılır.

    Platform notları:
        - Linux: tam destek
        - Windows: tam destek
        - macOS: psutil cpu_affinity'i desteklemez (AttributeError).
          start() IsolationUnsupportedError fırlatır; manager fail_on_error=False
          ise NoopBackend'e düşer.
    """

    name = "affinity"

    def __init__(self, config) -> None:
        self.config = config
        self._cpus: list[int] = []
        self._applied_pids: set[int] = set()
        self._active = False

    def start(self, partition: CpuPartition) -> BackendOutcome:
        if not hasattr(psutil.Process(), "cpu_affinity"):
            raise IsolationUnsupportedError(
                "CPU affinity bu platformda desteklenmiyor (psutil.cpu_affinity yok)."
            )

        self._cpus = self._resolve_cpus(partition)

        if not self._cpus:
            raise IsolationBackendError(
                message="AffinityBackend için CPU listesi boş.",
                code="ISO020",
            )

        self._active = True

        logger.info(
            "CPU affinity backend aktif. mode=%s cpus=%s",
            self.config.affinity_mode,
            format_cpu_range(set(self._cpus)),
        )

        return BackendOutcome(
            backend_name=self.name,
            active=True,
            reason=f"affinity_mode={self.config.affinity_mode}",
        )

    def add_worker(self, pid: int) -> None:
        if not self._active:
            return

        if pid <= 0:
            raise IsolationBackendError(
                message=f"Geçersiz PID: {pid}",
                code="ISO021",
            )

        try:
            psutil.Process(pid).cpu_affinity(self._cpus)
        except psutil.NoSuchProcess as exc:
            raise IsolationBackendError(
                message=f"PID bulunamadı: {pid}",
                code="ISO022",
            ) from exc
        except (AttributeError, NotImplementedError) as exc:
            raise IsolationUnsupportedError(
                f"CPU affinity bu platformda desteklenmiyor: {exc}"
            ) from exc
        except OSError as exc:
            raise IsolationBackendError(
                message=f"PID={pid} için affinity uygulanamadı: {exc}",
                code="ISO023",
            ) from exc

        self._applied_pids.add(pid)

        logger.debug("PID %s için affinity uygulandı: %s", pid, self._cpus)

    def stop(self) -> None:
        # Affinity için "geri al" anlamlı değil — child process'ler zaten çıkıyor.
        if self._active:
            logger.info(
                "CPU affinity backend durduruluyor. applied_pids=%d",
                len(self._applied_pids),
            )

        self._applied_pids.clear()
        self._active = False

    def status(self) -> dict[str, Any]:
        return {
            "backend": self.name,
            "active": self._active,
            "mode": self.config.affinity_mode,
            "cpus": format_cpu_range(set(self._cpus)),
            "applied_pids": sorted(self._applied_pids),
        }

    def _resolve_cpus(self, partition: CpuPartition) -> list[int]:
        mode = self.config.affinity_mode

        if mode == "custom":
            try:
                cpus = parse_cpu_range(self.config.affinity_cpus)
            except ValueError as exc:
                raise IsolationBackendError(
                    message=f"Geçersiz affinity_cpus: {self.config.affinity_cpus!r} ({exc})",
                    code="ISO024",
                ) from exc

            if not cpus:
                raise IsolationBackendError(
                    message="affinity_cpus en az 1 CPU içermeli.",
                    code="ISO024",
                )

            return sorted(cpus)

        # mode == "auto" (veya disabled durumunda bu backend zaten seçilmemeli)
        if partition.enabled and partition.axion_cpus:
            return sorted(parse_cpu_range(partition.axion_cpus))

        # Plan yoksa makinedeki tüm CPU'ları kullan.
        cpu_count = os.cpu_count() or 1
        return list(range(cpu_count))

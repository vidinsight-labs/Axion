"""CPU izolasyon backend'leri için ortak interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .partition_planner import CpuPartition


@dataclass(frozen=True)
class BackendOutcome:
    """
    Backend.start() sonucu.

    Attributes:
        backend_name: Backend tipi ("linux_systemd_cgroup", "affinity", "noop").
        active: Backend gerçekten aktive edildi mi?
        reason: active=False ise sebep veya bilgilendirici not.
    """

    backend_name: str
    active: bool
    reason: str | None = None


class CpuIsolationBackend(ABC):
    """
    CPU izolasyon backend'i için soyut interface.

    Implementasyonlar:
        - LinuxSystemdCgroupBackend: cgroup v2 + systemd
        - AffinityBackend: psutil ile cross-platform CPU affinity
        - NoopBackend: hiçbir şey yapmaz
    """

    name: str = "abstract"

    @abstractmethod
    def start(self, partition: CpuPartition) -> BackendOutcome:
        """Backend'i aktive eder. Başarılı ise active=True döner."""

    @abstractmethod
    def add_worker(self, pid: int) -> None:
        """Verilen PID'yi backend kontrolüne alır."""

    @abstractmethod
    def stop(self) -> None:
        """Backend'i durdurur ve dışsal state'i geri yükler."""

    @abstractmethod
    def status(self) -> dict[str, Any]:
        """Tanı/debug için backend durumu."""

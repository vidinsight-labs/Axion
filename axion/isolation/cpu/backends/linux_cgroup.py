"""Linux systemd + cgroup v2 izolasyon backend'i."""

import logging
from typing import Any

from ..backend import BackendOutcome, CpuIsolationBackend
from ..exceptions import IsolationPermissionError
from ..partition_planner import CpuPartition
from ..linux.cgroup_v2 import CgroupV2Manager
from ..linux.detection import (
    assert_linux_systemd_cgroup_supported,
    is_root,
)
from ..linux.systemd import SystemdCpuSnapshot, SystemdManager


logger = logging.getLogger(__name__)


class LinuxSystemdCgroupBackend(CpuIsolationBackend):
    """
    Linux'ta systemd slice'larını system_cpus'a, Axion worker'larını cgroup v2
    cpuset'i üzerinden axion_cpus'a kısıtlar.

    Lifecycle:
        start():
            - Sistem yetkinliklerini doğrula (Linux, systemd, cgroup v2, cpuset, root)
            - systemd snapshot al
            - systemd slice'larını system_cpus'a kısıtla
            - Axion cgroup oluştur, cpuset.cpus=axion_cpus yaz
        add_worker(pid):
            - PID'yi Axion cgroup'una taşı
        stop():
            - systemd snapshot restore
            - Axion cgroup'u sil
    """

    name = "linux_systemd_cgroup"

    def __init__(self, config) -> None:
        self.config = config
        self.systemd = SystemdManager()
        self.cgroup = CgroupV2Manager(config.cgroup_root)
        self.snapshot: SystemdCpuSnapshot | None = None
        self._partition: CpuPartition | None = None
        self._active = False

    def start(self, partition: CpuPartition) -> BackendOutcome:
        assert_linux_systemd_cgroup_supported()

        if not is_root():
            raise IsolationPermissionError(
                "CPU isolation için root yetkisi gerekir. "
                "Engine'i sudo ile çalıştırın veya ileride cgroup delegation ekleyin."
            )

        if self.config.restore_on_shutdown:
            self.snapshot = self.systemd.snapshot()

        if self.config.restrict_system_slices:
            self.systemd.restrict_system(partition.system_cpus)

        self.cgroup.initialize(cpus=partition.axion_cpus)

        self._partition = partition
        self._active = True

        logger.info(
            "Linux cgroup izolasyonu aktif. system_cpus=%s axion_cpus=%s",
            partition.system_cpus,
            partition.axion_cpus,
        )

        return BackendOutcome(
            backend_name=self.name,
            active=True,
            reason=f"profile={partition.profile}",
        )

    def add_worker(self, pid: int) -> None:
        if not self._active:
            return

        self.cgroup.add_process(pid)
        logger.debug("Worker Axion cgroup'una taşındı. pid=%s", pid)

    def stop(self) -> None:
        if not self._active:
            return

        try:
            if self.config.restore_on_shutdown and self.snapshot:
                self.systemd.restore(self.snapshot)

            self.cgroup.destroy()

            logger.info("Linux cgroup izolasyonu durduruldu, systemd ayarları restore edildi.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Linux cgroup izolasyonu cleanup başarısız: %s", exc)
        finally:
            self._active = False

    def status(self) -> dict[str, Any]:
        return {
            "backend": self.name,
            "active": self._active,
            "cgroup_root": str(self.cgroup.root),
            "axion_cpuset": self.cgroup.read_cpuset_cpus() if self._active else "",
            "axion_cpuset_effective": (
                self.cgroup.read_cpuset_cpus_effective() if self._active else ""
            ),
            "worker_pids": self.cgroup.read_processes() if self._active else [],
            "partition": self._partition,
        }

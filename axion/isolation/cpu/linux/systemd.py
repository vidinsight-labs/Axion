import logging
import subprocess
from dataclasses import dataclass, field

from ..exceptions import IsolationBackendError


logger = logging.getLogger(__name__)


@dataclass
class SystemdCpuSnapshot:
    allowed_cpus: dict[str, str] = field(default_factory=dict)


class SystemdManager:
    """
    system.slice / user.slice / init.scope AllowedCPUs yönetimi.

    Not:
        --runtime kullanılır.
        Yani kalıcı systemd unit dosyası değiştirilmez.
    """

    DEFAULT_SYSTEM_UNITS = [
        "system.slice",
        "user.slice",
        "init.scope",
    ]

    def __init__(self, units: list[str] | None = None):
        self.units = units or self.DEFAULT_SYSTEM_UNITS

    def get_allowed_cpus(self, unit: str) -> str:
        result = subprocess.run(
            [
                "systemctl",
                "show",
                unit,
                "-p",
                "AllowedCPUs",
                "--value",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise IsolationBackendError(
                message=f"{unit} AllowedCPUs okunamadı: {result.stderr.strip()}",
                code="ISO001",
            )

        return result.stdout.strip()

    def set_allowed_cpus(self, unit: str, cpus: str) -> None:
        """
        Örnek:
            cpus="0-1"
            cpus="2-7"
            cpus=""  -> runtime property reset
        """

        result = subprocess.run(
            [
                "systemctl",
                "set-property",
                "--runtime",
                unit,
                f"AllowedCPUs={cpus}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise IsolationBackendError(
                message=f"{unit} AllowedCPUs ayarlanamadı: {result.stderr.strip()}",
                code="ISO013",
            )

        logger.debug("systemd %s AllowedCPUs=%r ayarlandı.", unit, cpus)

    def snapshot(self) -> SystemdCpuSnapshot:
        snapshot = SystemdCpuSnapshot()

        for unit in self.units:
            snapshot.allowed_cpus[unit] = self.get_allowed_cpus(unit)

        logger.debug("systemd snapshot alındı: %s", snapshot.allowed_cpus)

        return snapshot

    def restrict_system(self, system_cpus: str) -> None:
        for unit in self.units:
            self.set_allowed_cpus(unit, system_cpus)

    def restore(self, snapshot: SystemdCpuSnapshot) -> None:
        """
        Snapshot'taki AllowedCPUs değerlerini per-unit restore eder.

        Bir unit fail ederse kalanlar yine denenir; sonunda toplu hata raise edilir.
        """
        failures: list[str] = []

        for unit, cpus in snapshot.allowed_cpus.items():
            try:
                self.set_allowed_cpus(unit, cpus)
            except IsolationBackendError as exc:
                logger.warning("systemd %s restore başarısız: %s", unit, exc)
                failures.append(f"{unit}: {exc}")

        if failures:
            raise IsolationBackendError(
                message="systemd restore kısmen başarısız: " + " | ".join(failures),
                code="ISO014",
            )

    def reset_runtime(self) -> None:
        for unit in self.units:
            self.set_allowed_cpus(unit, "")

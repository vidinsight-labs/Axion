import os
from dataclasses import dataclass

from ...config.cpu_isolation_config import CpuIsolationConfig
from .utils import (
    count_cpus,
    format_cpu_range,
    parse_cpu_range,
    validate_disjoint,
)


# (max_cpu_count_inclusive, system_cpu_count). Sıralı ilk eşleşme kazanır.
# max_cpu_count_inclusive=None → "üst sınır yok" anlamına gelir.
PROFILE_SYSTEM_CPU_TABLE: dict[str, list[tuple[int | None, int]]] = {
    "safe": [
        (8, 2),
        (16, 4),
        (None, 4),  # cpu_count // 4 ile override edilir (aşağıda).
    ],
    "balanced": [
        (8, 2),
        (16, 3),
        (None, 4),
    ],
    "performance": [
        (4, 1),
        (16, 2),
        (None, 3),
    ],
}


@dataclass(frozen=True)
class CpuPartition:
    enabled: bool
    cpu_count: int
    profile: str

    system_cpus: str
    axion_cpus: str

    reason: str | None = None

    @property
    def system_cpu_count(self) -> int:
        return count_cpus(self.system_cpus)

    @property
    def axion_cpu_count(self) -> int:
        return count_cpus(self.axion_cpus)


class CpuPartitionPlanner:
    """
    CPU isolation için system_cpus / axion_cpus planı üretir.

    Örnek:
        4 CPU balanced:
            system_cpus = "0-1"
            axion_cpus  = "2-3"

        8 CPU balanced:
            system_cpus = "0-1"
            axion_cpus  = "2-7"

        16 CPU balanced:
            system_cpus = "0-2"
            axion_cpus  = "3-15"
    """

    def __init__(self, config: CpuIsolationConfig) -> None:
        self.config = config

    def plan(self) -> CpuPartition:
        cpu_count = os.cpu_count() or 1

        if not self.config.enabled:
            return CpuPartition(
                enabled=False,
                cpu_count=cpu_count,
                profile=self.config.profile,
                system_cpus="",
                axion_cpus="",
                reason="CPU isolation disabled by config.",
            )

        if cpu_count < self.config.min_cpus_required:
            return CpuPartition(
                enabled=False,
                cpu_count=cpu_count,
                profile=self.config.profile,
                system_cpus="",
                axion_cpus="",
                reason=(
                    f"CPU isolation requires at least "
                    f"{self.config.min_cpus_required} logical CPUs. "
                    f"Current CPU count: {cpu_count}."
                ),
            )

        if self.config.profile == "custom":
            return self._plan_custom(cpu_count)

        return self._plan_auto(cpu_count)

    def _plan_custom(self, cpu_count: int) -> CpuPartition:
        system_cpus = self.config.system_cpus
        axion_cpus = self.config.axion_cpus

        if system_cpus == "auto" or axion_cpus == "auto":
            raise ValueError(
                "profile='custom' için system_cpus ve axion_cpus manuel verilmelidir."
            )

        validate_disjoint(system_cpus, axion_cpus)
        self._validate_cpu_bounds(system_cpus, axion_cpus, cpu_count)

        if count_cpus(system_cpus) < 1:
            raise ValueError("system_cpus en az 1 CPU içermeli")

        if count_cpus(axion_cpus) < 1:
            raise ValueError("axion_cpus en az 1 CPU içermeli")

        return CpuPartition(
            enabled=True,
            cpu_count=cpu_count,
            profile="custom",
            system_cpus=system_cpus,
            axion_cpus=axion_cpus,
        )

    def _plan_auto(self, cpu_count: int) -> CpuPartition:
        system_count = self._calculate_system_cpu_count(
            cpu_count=cpu_count,
            profile=self.config.profile,
        )

        if system_count >= cpu_count:
            raise ValueError(
                f"system_count CPU sayısından küçük olmalı. "
                f"system_count={system_count}, cpu_count={cpu_count}"
            )

        system_cpus = set(range(0, system_count))
        axion_cpus = set(range(system_count, cpu_count))

        return CpuPartition(
            enabled=True,
            cpu_count=cpu_count,
            profile=self.config.profile,
            system_cpus=format_cpu_range(system_cpus),
            axion_cpus=format_cpu_range(axion_cpus),
        )

    def _calculate_system_cpu_count(self, cpu_count: int, profile: str) -> int:
        """
        Profile + cpu_count → sisteme bırakılacak logical CPU sayısı.

        safe:
            Sisteme daha fazla CPU bırakır. Çok-çekirdekli sistemlerde cpu_count // 4.

        balanced:
            Varsayılan. Küçük makinelerde 2, büyük makinelerde 3-4 CPU.

        performance:
            Axion'a maksimum CPU verir.
        """
        if profile not in PROFILE_SYSTEM_CPU_TABLE:
            raise ValueError(f"Geçersiz CPU isolation profile: {profile}")

        for max_cpu, system_count in PROFILE_SYSTEM_CPU_TABLE[profile]:
            if max_cpu is None or cpu_count <= max_cpu:
                if profile == "safe" and max_cpu is None:
                    return max(system_count, cpu_count // 4)
                return system_count

        # Tablo tasarımı gereği ulaşılmaz.
        raise ValueError(f"Profile için system CPU sayısı hesaplanamadı: {profile}")

    def _validate_cpu_bounds(
        self,
        system_cpus: str,
        axion_cpus: str,
        cpu_count: int,
    ) -> None:
        all_cpus = parse_cpu_range(system_cpus) | parse_cpu_range(axion_cpus)

        invalid_cpus = [cpu for cpu in all_cpus if cpu < 0 or cpu >= cpu_count]

        if invalid_cpus:
            raise ValueError(
                f"Geçersiz CPU indexleri: {invalid_cpus}. "
                f"Bu sistemde geçerli CPU aralığı: 0-{cpu_count - 1}"
            )

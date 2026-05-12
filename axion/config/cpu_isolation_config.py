from dataclasses import dataclass
from typing import Literal


CpuIsolationBackend = Literal[
    "auto",
    "linux_systemd_cgroup",
    "noop",
]

CpuIsolationProfile = Literal[
    "safe",
    "balanced",
    "performance",
    "custom",
]

CpuAffinityMode = Literal[
    "disabled",
    "auto",
    "custom",
]


@dataclass
class CpuIsolationConfig:
    """
    CPU izolasyon ve fallback affinity yapılandırması.

    Davranış:
        - isolation enabled=True ise Linux systemd + cgroup v2 izolasyonu uygulanır.
        - isolation enabled=False ise, istenirse worker processlere CPU affinity uygulanabilir.
        - Cgroup isolation ve CPU affinity aynı anda uygulanmaz.
    """

    # Cgroup/systemd tabanlı izolasyon aktif mi?
    enabled: bool = False

    # Backend seçimi:
    # auto: platforma göre uygun backend seçilir
    # linux_systemd_cgroup: Linux systemd + cgroup v2 backend
    # noop: hiçbir izolasyon uygulanmaz
    backend: CpuIsolationBackend = "auto"

    # CPU dağıtım profili:
    # safe: sisteme daha fazla CPU bırakır
    # balanced: varsayılan dengeli mod
    # performance: Axion'a daha fazla CPU verir
    # custom: system_cpus ve axion_cpus manuel verilmelidir
    profile: CpuIsolationProfile = "balanced"

    # Cgroup isolation için CPU aralıkları:
    # "auto" verilirse profile'a göre otomatik hesaplanır.
    # Örnek: "0-1", "2-7"
    system_cpus: str = "auto"
    axion_cpus: str = "auto"

    # system.slice / user.slice / init.scope sınırlandırılsın mı?
    restrict_system_slices: bool = True

    # Engine kapanırken eski systemd CPU ayarları geri yüklensin mi?
    restore_on_shutdown: bool = True

    # Axion worker processlerinin taşınacağı cgroup path'i
    cgroup_root: str = "/sys/fs/cgroup/axion-runtime"

    # İzolasyonu açmak için gereken minimum logical CPU sayısı
    min_cpus_required: int = 4

    # True ise izolasyon hatasında engine fail eder.
    # False ise warning verip izolasyonsuz devam edebilir.
    fail_on_error: bool = False

    # ------------------------------------------------------------------
    # Affinity fallback
    # ------------------------------------------------------------------
    # Sadece enabled=False iken uygulanır.
    # enabled=True ise affinity uygulanmaz.
    #
    # disabled: affinity kapalı
    # auto: worker processler otomatik hesaplanan axion CPU alanına pinlenir
    # custom: affinity_cpus manuel verilmelidir
    affinity_mode: CpuAffinityMode = "disabled"

    # Affinity için CPU aralığı.
    # affinity_mode=custom ise zorunlu.
    # affinity_mode=auto ise profile'a göre hesaplanabilir.
    affinity_cpus: str = "auto"

    def __post_init__(self):
        valid_backends = {"auto", "linux_systemd_cgroup", "noop"}
        if self.backend not in valid_backends:
            raise ValueError(f"Geçersiz cpu_isolation.backend: {self.backend}")

        valid_profiles = {"safe", "balanced", "performance", "custom"}
        if self.profile not in valid_profiles:
            raise ValueError(f"Geçersiz cpu_isolation.profile: {self.profile}")

        valid_affinity_modes = {"disabled", "auto", "custom"}
        if self.affinity_mode not in valid_affinity_modes:
            raise ValueError(
                f"Geçersiz cpu_isolation.affinity_mode: {self.affinity_mode}"
            )

        if self.min_cpus_required < 1:
            raise ValueError("cpu_isolation.min_cpus_required en az 1 olmalı")

        if self.profile == "custom":
            if self.system_cpus == "auto" or self.axion_cpus == "auto":
                raise ValueError(
                    "cpu_isolation.profile='custom' için "
                    "system_cpus ve axion_cpus manuel verilmelidir"
                )

        if self.affinity_mode == "custom" and self.affinity_cpus == "auto":
            raise ValueError(
                "cpu_isolation.affinity_mode='custom' için "
                "affinity_cpus manuel verilmelidir"
            )

        if self.enabled and self.affinity_mode != "disabled":
            raise ValueError(
                "Cgroup isolation aktifken CPU affinity uygulanmaz. "
                "cpu_isolation.enabled=True ise affinity_mode='disabled' olmalıdır."
            )
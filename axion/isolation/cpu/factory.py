"""Config + platforma göre uygun CPU izolasyon backend'ini seçer."""

import logging

from ...config.cpu_isolation_config import CpuIsolationConfig
from .backend import CpuIsolationBackend
from .backends.affinity import AffinityBackend
from .backends.linux_cgroup import LinuxSystemdCgroupBackend
from .backends.noop import NoopBackend
from .linux.detection import is_linux


logger = logging.getLogger(__name__)


def build_backend(config: CpuIsolationConfig) -> CpuIsolationBackend:
    """
    Seçim tablosu:
        - config.enabled=True + backend in {"auto","linux_systemd_cgroup"} + Linux
            → LinuxSystemdCgroupBackend
        - config.enabled=True + Linux dışı veya backend="noop"
            → NoopBackend (izolasyon imkansız)
        - config.enabled=False + affinity_mode != "disabled"
            → AffinityBackend
        - config.enabled=False + affinity_mode="disabled"
            → NoopBackend

    Not:
        config.__post_init__ izolasyon + affinity'nin birlikte aktif olmasını
        zaten engelliyor.
    """
    if config.enabled:
        if config.backend == "noop":
            return NoopBackend(reason="config.backend='noop'")

        if is_linux() and config.backend in ("auto", "linux_systemd_cgroup"):
            return LinuxSystemdCgroupBackend(config)

        reason = (
            "Linux dışı platformda cgroup izolasyonu yapılamaz; noop'a düşülüyor."
            if not is_linux()
            else f"Bilinmeyen backend: {config.backend!r}"
        )
        logger.warning(reason)
        return NoopBackend(reason=reason)

    # enabled=False → opsiyonel affinity fallback
    if config.affinity_mode in ("auto", "custom"):
        return AffinityBackend(config)

    return NoopBackend(reason="isolation disabled, affinity_mode='disabled'")

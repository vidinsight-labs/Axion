"""Engine yaşam döngüsüne bağlı CPU izolasyon orchestrator'ı."""

import atexit
import logging
import signal

from ...config.cpu_isolation_config import CpuIsolationConfig
from .backend import BackendOutcome, CpuIsolationBackend
from .backends.noop import NoopBackend
from .factory import build_backend
from .partition_planner import CpuPartition, CpuPartitionPlanner


logger = logging.getLogger(__name__)


class CpuIsolationManager:
    """
    Backend-agnostic CPU izolasyon yöneticisi.

    Sorumluluklar:
        - CpuPartition planla
        - Config'e göre uygun backend'i seç (factory.build_backend)
        - Backend lifecycle: start / add_worker / stop
        - Signal & atexit hook'ları
        - fail_on_error=False ise backend start hatası → NoopBackend fallback

    Public API:
        start() -> CpuPartition
        add_worker(pid)
        stop()
        status() -> dict
    """

    def __init__(self, config: CpuIsolationConfig) -> None:
        self.config = config
        self.planner = CpuPartitionPlanner(config)

        self.partition: CpuPartition | None = None
        self.backend: CpuIsolationBackend = NoopBackend(reason="not started")
        self.outcome: BackendOutcome | None = None

        self._cleanup_registered = False
        self._previous_sigint_handler = None
        self._previous_sigterm_handler = None

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    def start(self) -> CpuPartition:
        partition = self.planner.plan()
        self.partition = partition

        self.backend = build_backend(self.config)

        try:
            self.outcome = self.backend.start(partition)
        except Exception as exc:
            if self.config.fail_on_error:
                raise

            logger.warning(
                "Backend '%s' başlatılamadı; NoopBackend'e düşülüyor. Hata: %s",
                self.backend.name,
                exc,
            )

            self.backend = NoopBackend(reason=f"start failed: {exc}")
            self.outcome = self.backend.start(partition)

            disabled = CpuPartition(
                enabled=False,
                cpu_count=partition.cpu_count,
                profile=partition.profile,
                system_cpus="",
                axion_cpus="",
                reason=str(exc),
            )
            self.partition = disabled
            return disabled

        if self.outcome.active:
            self._register_cleanup_hooks()

        return partition

    def add_worker(self, pid: int) -> None:
        try:
            self.backend.add_worker(pid)
        except Exception as exc:
            if self.config.fail_on_error:
                raise

            logger.warning(
                "Worker backend '%s'e eklenemedi. pid=%s error=%s",
                self.backend.name,
                pid,
                exc,
            )

    def stop(self) -> None:
        try:
            self.backend.stop()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Backend '%s' stop başarısız: %s", self.backend.name, exc)
        finally:
            self._unregister_cleanup_hooks()
            self.outcome = None

    def status(self) -> dict:
        return {
            "config_enabled": self.config.enabled,
            "config_backend": self.config.backend,
            "affinity_mode": self.config.affinity_mode,
            "partition": self.partition,
            "outcome": self.outcome,
            "backend": self.backend.status(),
        }

    # ------------------------------------------------------------------
    # Signal hooks
    # ------------------------------------------------------------------

    def _register_cleanup_hooks(self) -> None:
        if self._cleanup_registered:
            return

        atexit.register(self.stop)

        # signal.signal sadece ana thread'de kullanılabilir; thread'lerden
        # çağrılırsa ValueError fırlatır. Manager genelde main thread'den
        # çağrıldığı için güvenli, ama belirsizlik için yine de try.
        try:
            self._previous_sigint_handler = signal.getsignal(signal.SIGINT)
            self._previous_sigterm_handler = signal.getsignal(signal.SIGTERM)
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except (ValueError, OSError) as exc:
            logger.debug("Signal handler kurulamadı: %s", exc)
            self._previous_sigint_handler = None
            self._previous_sigterm_handler = None

        self._cleanup_registered = True

    def _unregister_cleanup_hooks(self) -> None:
        if not self._cleanup_registered:
            return

        try:
            if self._previous_sigint_handler is not None:
                signal.signal(signal.SIGINT, self._previous_sigint_handler)
            if self._previous_sigterm_handler is not None:
                signal.signal(signal.SIGTERM, self._previous_sigterm_handler)
        except (ValueError, OSError) as exc:
            logger.debug("Signal handler restore başarısız: %s", exc)

        # atexit'i tek tek silemiyoruz ama stop() idempotent.
        self._cleanup_registered = False

    def _handle_signal(self, signum, frame):
        self.stop()

        previous_handler = (
            self._previous_sigint_handler
            if signum == signal.SIGINT
            else self._previous_sigterm_handler
        )

        if callable(previous_handler):
            previous_handler(signum, frame)
            return

        raise SystemExit(128 + signum)

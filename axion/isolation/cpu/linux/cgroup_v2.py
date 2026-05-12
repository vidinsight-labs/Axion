"""
Linux cgroup v2 cpuset yönetimi.

Bu modül, Axion worker processlerini Linux cgroup v2 sistemine yerleştirmek için
kullanılan CgroupV2Manager sınıfını içerir.

Sorumluluklar:
    - cgroup v2 cpuset boundary uygulama
    - Worker processleri Axion cgroup'una taşıma
    - Parent cgroup controller'ları aktive etme
    - CPU affinity uygulanmaz (bu modülün sorumluluğu değil)

Kullanım:
    manager = CgroupV2Manager(root="/sys/fs/cgroup/axion-runtime")
    manager.initialize(cpus="2-7")
    manager.add_process(worker_pid)
    manager.destroy()

Dependencies:
    - Linux kernel 4.5+ (cgroup v2 support)
    - systemd 232+ (recommended)
    - Root veya CAP_SYS_ADMIN capability
"""

import logging
from pathlib import Path

from ..exceptions import IsolationBackendError
from ..utils import validate_cpus_string
from .detection import CGROUP_ROOT, DEFAULT_AXION_CGROUP


logger = logging.getLogger(__name__)


class CgroupV2Manager:
    """
    Axion worker processlerini cgroup v2 cpuset içine taşır.

    Bu sınıf CPU affinity uygulamaz.
    Sadece cgroup cpuset boundary uygular.
    """

    # Cgroup file names
    FILE_CGROUP_PROCS = "cgroup.procs"
    FILE_CGROUP_CONTROLLERS = "cgroup.controllers"
    FILE_CGROUP_SUBTREE_CONTROL = "cgroup.subtree_control"
    FILE_CPUSET_CPUS = "cpuset.cpus"
    FILE_CPUSET_CPUS_EFFECTIVE = "cpuset.cpus.effective"
    FILE_CPUSET_MEMS = "cpuset.mems"
    FILE_CPUSET_MEMS_EFFECTIVE = "cpuset.mems.effective"

    REQUIRED_CONTROLLERS = ["cpuset"]

    def __init__(self, root: str | Path = DEFAULT_AXION_CGROUP):
        self.root = Path(root)

    def initialize(self, cpus: str) -> None:
        """
        Cgroup oluşturur, parent controller'ları açmaya çalışır
        ve cpuset ayarlarını yazar.

        Args:
            cpus: CPU set string (örn: "0-3", "2-7", "0,2,4")

        Raises:
            IsolationBackendError: Validation veya cgroup işlem hatası
        """
        self._validate_cpus(cpus)
        self._ensure_cgroup_v2_root_exists()

        self.root.mkdir(parents=True, exist_ok=True)
        logger.debug("Axion cgroup hazırlandı: %s", self.root)

        self._enable_parent_controllers()
        self._ensure_required_files()

        mems = self._detect_mems()

        # cpuset.mems önce yazılmalı.
        self._write(self.FILE_CPUSET_MEMS, mems)
        self._write(self.FILE_CPUSET_CPUS, cpus)

        logger.info(
            "Axion cgroup initialize tamamlandı. cpus=%s mems=%s root=%s",
            cpus,
            mems,
            self.root,
        )

    def add_process(self, pid: int) -> None:
        """
        PID'yi Axion cgroup'una taşır.

        Raises:
            IsolationBackendError: Geçersiz PID (ISO002) veya yazma hatası
        """
        if pid <= 0:
            raise IsolationBackendError(
                message=f"Geçersiz PID: {pid}",
                code="ISO002",
            )

        self._write(self.FILE_CGROUP_PROCS, str(pid))
        logger.debug("PID %s Axion cgroup'una taşındı.", pid)

    def read_processes(self) -> list[int]:
        """Cgroup içindeki process ID'lerini döner."""
        path = self.root / self.FILE_CGROUP_PROCS

        if not path.exists():
            return []

        pids: list[int] = []

        for line in path.read_text().splitlines():
            line = line.strip()

            if not line:
                continue

            try:
                pids.append(int(line))
            except ValueError:
                continue

        return pids

    def read_cpuset_cpus(self) -> str:
        return self._read_if_exists(self.FILE_CPUSET_CPUS)

    def read_cpuset_cpus_effective(self) -> str:
        return self._read_if_exists(self.FILE_CPUSET_CPUS_EFFECTIVE)

    def read_cpuset_mems(self) -> str:
        return self._read_if_exists(self.FILE_CPUSET_MEMS)

    def read_cpuset_mems_effective(self) -> str:
        return self._read_if_exists(self.FILE_CPUSET_MEMS_EFFECTIVE)

    def destroy(self) -> None:
        """
        Cgroup boşsa siler.

        İçinde process varsa veya kernel/systemd izin vermezse sessiz geçer.
        """
        try:
            self.root.rmdir()
            logger.debug("Axion cgroup silindi: %s", self.root)
        except FileNotFoundError:
            return
        except OSError as exc:
            logger.debug("Axion cgroup silinemedi (%s): %s", self.root, exc)
            return

    def _validate_cpus(self, cpus: str) -> None:
        """utils.validate_cpus_string'i IsolationBackendError'a wrap eder."""
        try:
            validate_cpus_string(cpus)
        except ValueError as exc:
            raise IsolationBackendError(
                message=str(exc),
                code="ISO012",
            ) from exc

    def _ensure_cgroup_v2_root_exists(self) -> None:
        """
        Sistemde cgroup v2'nin mevcut olduğunu doğrular.

        /sys/fs/cgroup/cgroup.controllers dosyasının varlığını kontrol eder.

        Raises:
            IsolationBackendError: cgroup v2 bulunamadı (ISO003)
        """
        controllers_path = CGROUP_ROOT / self.FILE_CGROUP_CONTROLLERS

        if not controllers_path.exists():
            raise IsolationBackendError(
                message=f"cgroup v2 bulunamadı: {controllers_path} yok.",
                code="ISO003",
            )

    def _enable_parent_controllers(self) -> None:
        """
        Child cgroup içinde cpuset dosyalarının oluşması için parent cgroup üzerinde
        +cpuset açar.

        Raises:
            IsolationBackendError:
                - ISO004: Parent controller dosyaları bulunamadı
                - ISO005: Gerekli controller sistemde yok
                - ISO006: İzin hatası
                - ISO007: Diğer OS hataları
        """
        parent = self.root.parent

        controllers_path = parent / self.FILE_CGROUP_CONTROLLERS
        subtree_control_path = parent / self.FILE_CGROUP_SUBTREE_CONTROL

        if not controllers_path.exists():
            raise IsolationBackendError(
                message=(
                    f"Parent cgroup controller dosyası bulunamadı: {controllers_path}. "
                    f"cgroup v2 hiyerarşisi düzgün yapılandırılmamış olabilir."
                ),
                code="ISO004",
            )

        if not subtree_control_path.exists():
            raise IsolationBackendError(
                message=(
                    f"Parent cgroup subtree control dosyası bulunamadı: "
                    f"{subtree_control_path}"
                ),
                code="ISO004",
            )

        available = set(controllers_path.read_text().split())

        missing = [
            controller
            for controller in self.REQUIRED_CONTROLLERS
            if controller not in available
        ]

        if missing:
            raise IsolationBackendError(
                message=(
                    f"Bu sistemde gerekli cgroup controller yok: {missing}. "
                    f"Kernel config'de CONFIG_CGROUP_CPUSET=y olmalıdır."
                ),
                code="ISO005",
            )

        value = " ".join(f"+{controller}" for controller in self.REQUIRED_CONTROLLERS)

        try:
            subtree_control_path.write_text(value)
            logger.debug("Parent subtree_control yazıldı: %s <- %s", subtree_control_path, value)
        except PermissionError as exc:
            raise IsolationBackendError(
                message=(
                    f"Parent cgroup controller enable için izin yok: "
                    f"{subtree_control_path}. Root veya CAP_SYS_ADMIN gerektirir."
                ),
                code="ISO006",
            ) from exc
        except OSError as exc:
            raise IsolationBackendError(
                message=f"Parent cgroup controller enable edilemedi: {exc}",
                code="ISO007",
            ) from exc

    def _ensure_required_files(self) -> None:
        """
        Cgroup içinde gerekli cpuset dosyalarının varlığını kontrol eder.

        Raises:
            IsolationBackendError: Gerekli dosyalar bulunamadı (ISO008)
        """
        required_files = [
            self.root / self.FILE_CGROUP_PROCS,
            self.root / self.FILE_CPUSET_CPUS,
            self.root / self.FILE_CPUSET_MEMS,
        ]

        missing = [str(path) for path in required_files if not path.exists()]

        if missing:
            raise IsolationBackendError(
                message=(
                    "Cgroup cpuset dosyaları bulunamadı. "
                    "Muhtemelen parent cgroup üzerinde cpuset controller aktif değil. "
                    f"Eksik dosyalar: {missing}. "
                    f"Çözüm: echo +cpuset > "
                    f"{self.root.parent}/{self.FILE_CGROUP_SUBTREE_CONTROL}"
                ),
                code="ISO008",
            )

    def _detect_mems(self) -> str:
        """
        NUMA memory node değerini bulur.

        Öncelik sırası:
            1. parent cpuset.mems.effective
            2. root cpuset.mems.effective
            3. fallback "0"
        """
        candidates = [
            self.root.parent / self.FILE_CPUSET_MEMS_EFFECTIVE,
            CGROUP_ROOT / self.FILE_CPUSET_MEMS_EFFECTIVE,
        ]

        for path in candidates:
            if path.exists():
                value = path.read_text().strip()

                if value:
                    return value

        return "0"

    def _write(self, filename: str, value: str) -> None:
        """
        Cgroup dosyasına değer yazar.

        Raises:
            IsolationBackendError:
                - ISO009: Dosya bulunamadı
                - ISO010: İzin hatası
                - ISO011: Diğer OS hataları
        """
        path = self.root / filename

        if not path.exists():
            raise IsolationBackendError(
                message=(
                    f"Cgroup dosyası bulunamadı: {path}. "
                    f"Cgroup henüz oluşturulmamış olabilir."
                ),
                code="ISO009",
            )

        try:
            path.write_text(value)
            logger.debug("cgroup write %s <- %r", path, value)
        except PermissionError as exc:
            raise IsolationBackendError(
                message=(
                    f"Cgroup dosyasına yazma izni yok: {path}. "
                    f"Root veya CAP_SYS_ADMIN gerektirir."
                ),
                code="ISO010",
            ) from exc
        except OSError as exc:
            raise IsolationBackendError(
                message=(
                    f"Cgroup dosyasına yazılamadı: {path} value={value!r} error={exc}"
                ),
                code="ISO011",
            ) from exc

    def _read_if_exists(self, filename: str) -> str:
        """Cgroup dosyasını okur, yoksa boş string döner."""
        path = self.root / filename

        if not path.exists():
            return ""

        return path.read_text().strip()

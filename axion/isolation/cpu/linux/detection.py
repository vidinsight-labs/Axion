import os
import platform
import shutil
from pathlib import Path

from ..exceptions import IsolationUnsupportedError, IsolationPermissionError


CGROUP_ROOT = Path("/sys/fs/cgroup")
DEFAULT_AXION_CGROUP = CGROUP_ROOT / "axion-runtime"


def is_linux() -> bool:
    """
    Çalışan sistem Linux mu?
    """
    return platform.system().lower() == "linux"


def is_root() -> bool:
    """
    Process root yetkisiyle mi çalışıyor?
    """
    return os.geteuid() == 0


def has_systemd() -> bool:
    """
    Sistem systemd kullanıyor mu?

    /run/systemd/system dizini genelde systemd çalışan sistemlerde bulunur.
    """
    return Path("/run/systemd/system").exists()


def systemctl_available() -> bool:
    """
    systemctl komutu erişilebilir mi?
    """
    return shutil.which("systemctl") is not None


def has_cgroup_v2() -> bool:
    """
    cgroup v2 aktif mi?

    cgroup v2 sistemlerde /sys/fs/cgroup/cgroup.controllers bulunur.
    """
    return (CGROUP_ROOT / "cgroup.controllers").exists()


def get_available_controllers() -> set[str]:
    """
    Root cgroup üzerinde mevcut controller listesini döndürür.

    Örnek çıktı:
        {"cpuset", "cpu", "io", "memory", "pids"}
    """
    path = CGROUP_ROOT / "cgroup.controllers"

    if not path.exists():
        return set()

    content = path.read_text().strip()

    if not content:
        return set()

    return set(content.split())


def has_controller(controller: str) -> bool:
    """
    Belirli bir cgroup controller mevcut mu?
    """
    return controller in get_available_controllers()


def has_required_controllers(required: set[str] | None = None) -> bool:
    """
    Gerekli controller'lar sistemde var mı?

    CPU izolasyonu için minimum gerekli controller:
        cpuset

    İleride cpu, memory, io da eklenebilir.
    """
    required = required or {"cpuset"}
    available = get_available_controllers()

    return required.issubset(available)


def get_missing_controllers(required: set[str] | None = None) -> set[str]:
    """
    Eksik controller listesini döndürür.
    """
    required = required or {"cpuset"}
    available = get_available_controllers()

    return required - available


def is_cgroup_subtree_control_available(path: str | Path = CGROUP_ROOT) -> bool:
    """
    Verilen cgroup path altında cgroup.subtree_control var mı?
    """
    path = Path(path)
    return (path / "cgroup.subtree_control").exists()


def can_write_cgroup_subtree_control(path: str | Path = CGROUP_ROOT) -> bool:
    """
    cgroup.subtree_control dosyasına yazılabilir mi?

    Bu, parent cgroup üzerinde controller enable edebilmek için gerekir.
    """
    path = Path(path)
    subtree_control = path / "cgroup.subtree_control"

    return subtree_control.exists() and os.access(subtree_control, os.W_OK)


def can_create_cgroup(path: str | Path) -> bool:
    """
    Verilen parent path altında yeni cgroup oluşturulabilir mi?
    """
    path = Path(path)

    if not path.exists():
        return False

    return os.access(path, os.W_OK)


def get_cgroup_mount_info() -> str:
    """
    /proc/self/mountinfo içinden cgroup2 satırlarını döndürür.
    Debug/status çıktısı için kullanışlıdır.
    """
    mountinfo = Path("/proc/self/mountinfo")

    if not mountinfo.exists():
        return ""

    lines = []

    for line in mountinfo.read_text().splitlines():
        if " - cgroup2 " in line:
            lines.append(line)

    return "\n".join(lines)


def get_current_process_cgroup() -> str:
    """
    Mevcut process'in cgroup bilgisini döndürür.

    cgroup v2 için genelde şöyle görünür:
        0::/user.slice/user-1000.slice/session-2.scope
    """
    path = Path("/proc/self/cgroup")

    if not path.exists():
        return ""

    return path.read_text().strip()


def assert_linux() -> None:
    if not is_linux():
        raise IsolationUnsupportedError(
            "CPU isolation backend sadece Linux üzerinde desteklenir."
        )


def assert_root() -> None:
    if not is_root():
        raise IsolationPermissionError(
            "CPU isolation için root yetkisi gerekir. "
            "Engine'i sudo ile çalıştırın veya cgroup delegation kullanın."
        )


def assert_systemd() -> None:
    if not has_systemd():
        raise IsolationUnsupportedError(
            "systemd bulunamadı. Bu backend systemd gerektirir."
        )

    if not systemctl_available():
        raise IsolationUnsupportedError(
            "systemctl komutu bulunamadı. Bu backend systemd/systemctl gerektirir."
        )


def assert_cgroup_v2() -> None:
    if not has_cgroup_v2():
        raise IsolationUnsupportedError(
            "cgroup v2 bulunamadı. "
            "/sys/fs/cgroup/cgroup.controllers mevcut değil."
        )


def assert_required_controllers(required: set[str] | None = None) -> None:
    required = required or {"cpuset"}

    missing = get_missing_controllers(required)

    if missing:
        raise IsolationUnsupportedError(
            f"Gerekli cgroup controller'lar eksik: {sorted(missing)}"
        )


def assert_linux_systemd_cgroup_supported(
    required_controllers: set[str] | None = None,
) -> None:
    """
    Linux systemd + cgroup v2 backend için temel sistem kontrolleri.

    Kontrol edilenler:
        - Linux
        - systemd
        - systemctl
        - cgroup v2
        - gerekli cgroup controller'lar
    """
    assert_linux()
    assert_systemd()
    assert_cgroup_v2()
    assert_required_controllers(required_controllers or {"cpuset"})


def get_detection_report(
    required_controllers: set[str] | None = None,
    cgroup_parent: str | Path = CGROUP_ROOT,
) -> dict:
    """
    CLI/status/debug için sistem uygunluk raporu döndürür.
    """
    required_controllers = required_controllers or {"cpuset"}
    cgroup_parent = Path(cgroup_parent)

    available_controllers = get_available_controllers()
    missing_controllers = required_controllers - available_controllers

    return {
        "is_linux": is_linux(),
        "is_root": is_root(),
        "has_systemd": has_systemd(),
        "systemctl_available": systemctl_available(),
        "has_cgroup_v2": has_cgroup_v2(),
        "available_controllers": sorted(available_controllers),
        "required_controllers": sorted(required_controllers),
        "missing_controllers": sorted(missing_controllers),
        "cgroup_parent": str(cgroup_parent),
        "can_create_cgroup": can_create_cgroup(cgroup_parent),
        "subtree_control_available": is_cgroup_subtree_control_available(cgroup_parent),
        "subtree_control_writable": can_write_cgroup_subtree_control(cgroup_parent),
        "current_process_cgroup": get_current_process_cgroup(),
        "cgroup_mount_info": get_cgroup_mount_info(),
    }
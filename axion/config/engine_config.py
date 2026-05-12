from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any
import multiprocessing
import yaml

from .cpu_isolation_config import CpuIsolationConfig


@dataclass
class EngineConfig:
    input_queue_size: int = 1000
    output_queue_size: int = 10000

    cpu_bound_count: int = 1
    io_bound_count: Optional[int] = None

    cpu_bound_task_limit: int = 1
    io_bound_task_limit: int = 20

    log_level: str = "INFO"
    queue_poll_timeout: float = 1.0

    cpu_isolation: CpuIsolationConfig = field(default_factory=CpuIsolationConfig)

    @classmethod
    def load(cls, path: str | Path = "config.yaml") -> "EngineConfig":
        """
        Varsayılan olarak engine.yaml dosyasından config okur.
        Dosya yoksa default EngineConfig döner.
        """
        config_path = Path(path)

        if not config_path.exists():
            return cls()

        return cls.from_yaml(config_path)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "EngineConfig":
        """
        YAML dosyasından EngineConfig oluşturur.
        Kullanım:
            config = EngineConfig.from_yaml("engine.yaml")
        """
        config_path = Path(path)

        with config_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

        if data is None:
            data = {}

        if not isinstance(data, dict):
            raise ValueError("YAML config dosyası dictionary/object formatında olmalı")

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EngineConfig":
        """
        Dictionary veriden EngineConfig oluşturur.
        YAML/JSON loader sonrası ortak dönüşüm noktasıdır.
        """
        return cls(**data)

    def __post_init__(self):
        if isinstance(self.cpu_isolation, dict):
            self.cpu_isolation = CpuIsolationConfig(**self.cpu_isolation)

        if self.io_bound_count is None:
            cpu_count = multiprocessing.cpu_count()
            self.io_bound_count = max(1, cpu_count - 1)

        if self.input_queue_size < 1:
            raise ValueError("input_queue_size en az 1 olmalı")

        if self.output_queue_size < 1:
            raise ValueError("output_queue_size en az 1 olmalı")

        if self.cpu_bound_count < 1:
            raise ValueError("cpu_bound_count en az 1 olmalı")

        if self.io_bound_count < 1:
            raise ValueError("io_bound_count en az 1 olmalı")

        if self.cpu_bound_task_limit < 1:
            raise ValueError("cpu_bound_task_limit en az 1 olmalı")

        if self.io_bound_task_limit < 1:
            raise ValueError("io_bound_task_limit en az 1 olmalı")

        if self.queue_poll_timeout <= 0:
            raise ValueError("queue_poll_timeout 0'dan büyük olmalı")

        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid_levels:
            raise ValueError(f"Geçersiz log_level: {self.log_level}")

        self.log_level = self.log_level.upper()
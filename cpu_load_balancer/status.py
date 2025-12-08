"""Basit status takibi"""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ComponentStatus:
    """
    Component durumu - basit
    
    Her component'in get_status() metodu bu sınıfı döndürür.
    """
    name: str
    health: str  # "healthy" veya "unhealthy"
    metrics: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Dict'e dönüştür"""
        return {
            "name": self.name,
            "health": self.health,
            "metrics": self.metrics,
        }
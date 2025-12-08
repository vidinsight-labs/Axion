"""
Core Sınıflar Testleri

Task, Result, Config ve Status sınıflarını test eder.
"""

import pytest
from datetime import datetime

import sys
import os

# Paket import'u (setup.py ile kurulmuş olmalı)
from cpu_load_balancer import Task, Result, TaskType, TaskStatus, ExecutorType
from cpu_load_balancer import EngineConfig
from cpu_load_balancer import ComponentStatus, HealthStatus


class TestTask:
    """Task sınıfı testleri"""
    
    def test_task_creation(self):
        """Task oluşturma testi"""
        task = Task(
            script_path="test.py",
            params={"key": "value"},
            task_type=TaskType.IO_BOUND
        )
        
        assert task.script_path == "test.py"
        assert task.params == {"key": "value"}
        assert task.task_type == TaskType.IO_BOUND
        assert task.id is not None
        assert task.status == TaskStatus.PENDING
    
    def test_task_to_dict(self):
        """Task'ı dict'e dönüştürme testi"""
        task = Task(
            script_path="test.py",
            params={"key": "value"},
            task_type=TaskType.CPU_BOUND
        )
        
        task_dict = task.to_dict()
        
        assert task_dict["script_path"] == "test.py"
        assert task_dict["params"] == {"key": "value"}
        assert task_dict["task_type"] == "cpu_bound"
        assert task_dict["id"] == task.id
    
    def test_task_validation(self):
        """Task validasyon testi"""
        with pytest.raises(ValueError):
            Task(script_path="")  # Boş script_path
        
        with pytest.raises(ValueError):
            Task(script_path="test.py", max_retries=-1)  # Negatif retry


class TestResult:
    """Result sınıfı testleri"""
    
    def test_result_success(self):
        """Başarılı sonuç testi"""
        result = Result.success(
            task_id="test-123",
            data={"result": "ok"}
        )
        
        assert result.task_id == "test-123"
        assert result.status == TaskStatus.COMPLETED
        assert result.data == {"result": "ok"}
        assert result.is_success is True
        assert result.is_failed is False
    
    def test_result_failure(self):
        """Başarısız sonuç testi"""
        result = Result.failure(
            task_id="test-123",
            error="Test error"
        )
        
        assert result.task_id == "test-123"
        assert result.status == TaskStatus.FAILED
        assert result.error == "Test error"
        assert result.is_success is False
        assert result.is_failed is True
    
    def test_result_duration(self):
        """Sonuç süresi testi"""
        started_at = datetime.now()
        result = Result.success(
            task_id="test-123",
            data={"result": "ok"},
            started_at=started_at
        )
        
        assert result.duration is not None
        assert result.duration >= 0


class TestEngineConfig:
    """EngineConfig testleri"""
    
    def test_config_creation(self):
        """Config oluşturma testi"""
        config = EngineConfig()
        
        assert config.input_queue_size > 0
        assert config.output_queue_size > 0
        assert config.cpu_bound_count is not None
        assert config.io_bound_count is not None
    
    def test_config_validation(self):
        """Config validasyon testi"""
        with pytest.raises(ValueError):
            EngineConfig(input_queue_size=0)  # Geçersiz queue size
        
        with pytest.raises(ValueError):
            EngineConfig(cpu_bound_task_limit=0)  # Geçersiz task limit
    
    def test_config_to_dict(self):
        """Config'ı dict'e dönüştürme testi"""
        config = EngineConfig()
        config_dict = config.to_dict()
        
        assert "input_queue_size" in config_dict
        assert "cpu_bound_count" in config_dict
        assert "io_bound_count" in config_dict


class TestComponentStatus:
    """ComponentStatus testleri"""
    
    def test_status_creation(self):
        """Status oluşturma testi"""
        status = ComponentStatus(
            name="test_component",
            is_running=True,
            health=HealthStatus.HEALTHY
        )
        
        assert status.name == "test_component"
        assert status.is_running is True
        assert status.health == HealthStatus.HEALTHY
        assert status.is_healthy is True
    
    def test_status_to_dict(self):
        """Status'u dict'e dönüştürme testi"""
        status = ComponentStatus(
            name="test_component",
            is_running=True,
            health=HealthStatus.HEALTHY,
            metrics={"count": 10}
        )
        
        status_dict = status.to_dict()
        
        assert status_dict["name"] == "test_component"
        assert status_dict["is_running"] is True
        assert status_dict["health"] == "healthy"
        assert status_dict["metrics"]["count"] == 10


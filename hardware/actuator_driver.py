# hardware/actuator_driver.py
# 统一的执行器驱动抽象与工厂
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

class ActuatorDriver(ABC):
    """执行器驱动抽象：控制单腿/批量移动、急停、连接管理"""

    @abstractmethod
    def connect(self) -> bool: ...
    @abstractmethod
    def disconnect(self) -> None: ...
    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def apply_batch(self, cmds: List[Dict]) -> bool:
        """批量下发：cmd = {id, dz, dx, dy}，单位mm，正dz表示下降该增量"""
        ...

    @abstractmethod
    def move_leg_delta(self, leg_id: int, dz: float, dx: float, dy: float) -> bool: ...

    @abstractmethod
    def stop_all(self) -> None: ...

def build_driver(mode: str, **kwargs) -> ActuatorDriver:
    """
    mode: "serial" -> driver_serial.DriverSerial
          "mock"   -> driver_mock.DriverMock
    kwargs 透传给对应驱动（如 port, baudrate, legs 引用 等）
    """
    if mode == "serial":
        from .driver_serial import DriverSerial
        return DriverSerial(**kwargs)
    elif mode == "mock":
        from .driver_mock import DriverMock
        return DriverMock(**kwargs)
    else:
        raise ValueError(f"Unknown driver mode: {mode}")

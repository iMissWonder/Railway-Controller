# hardware/driver_mock.py
# 仿真驱动：接口与串口驱动一致，不实际发串口；用于联调/演示
from typing import List, Dict, Optional
import threading
import time
from .actuator_driver import ActuatorDriver

class DriverMock(ActuatorDriver):
    def __init__(self, legs=None, latency_s: float = 0.0, logger=None, **_):
        """
        legs: 可选，传入 legs 引用（多数情况下不依赖）
        latency_s: 模拟通信/动作延迟
        logger: 统一透传的日志对象（可为空）
        **_: 兼容将来可能透传的其它无关参数，避免再次因未知参数报错
        """
        self.logger = logger
        self._connected = True
        self._lock = threading.Lock()
        self._latency_s = latency_s

    def connect(self) -> bool:
        with self._lock:
            self._connected = True
        return True

    def disconnect(self) -> None:
        with self._lock:
            self._connected = False

    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    def apply_batch(self, cmds: List[Dict]) -> bool:
        with self._lock:
            if not self._connected:
                raise RuntimeError("DriverMock 未连接")
        # 模拟执行耗时
        if self._latency_s > 0:
            time.sleep(self._latency_s)
        # 可选：在这里直接回写 legs（大多数情况下 control_system 已经回写了）
        return True

    def move_leg_delta(self, leg_id: int, dz: float, dx: float, dy: float) -> bool:
        with self._lock:
            if not self._connected:
                raise RuntimeError("DriverMock 未连接")
        if self._latency_s > 0:
            time.sleep(self._latency_s)
        return True

    def stop_all(self) -> None:
        # 无需实际操作
        pass

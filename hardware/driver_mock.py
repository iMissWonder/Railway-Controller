# hardware/driver_mock.py
# 仿真驱动：接口与串口驱动一致，不实际发串口；用于联调/演示
from typing import List, Dict, Optional, Any
import threading

from .actuator_driver import ActuatorDriver

class DriverMock(ActuatorDriver):
    """
    简单的 mock 驱动：把下发的位移直接应用到传入的 legs 引用上（写回 LegUnit），
    以便 GUI 能即时看到位置变化（用于本地仿真）。单位按 ActuatorDriver 说明为 mm。
    """

    def __init__(self, legs: Optional[List[Any]] = None, logger=None):
        self._legs = legs or []
        self._logger = logger
        self._connected = True
        self._lock = threading.Lock()

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return bool(self._connected)

    def apply_batch(self, cmds: List[Dict]) -> bool:
        """
        cmds: List[{"id": int, "dz": float, "dx": float, "dy": float}]
        单位：mm。正 dz 表示下降（增大 z 值）。
        """
        with self._lock:
            try:
                for c in cmds:
                    leg_id = int(c.get("id", -1))
                    dz = float(c.get("dz", 0.0))
                    dx = float(c.get("dx", 0.0))
                    dy = float(c.get("dy", 0.0))
                    self._apply_to_leg(leg_id, dz, dx, dy)
                return True
            except Exception as e:
                if self._logger:
                    try: self._logger.exception(e, "DriverMock apply_batch 错误")
                    except Exception: pass
                return False

    def move_leg_delta(self, leg_id: int, dz: float, dx: float, dy: float) -> bool:
        with self._lock:
            try:
                self._apply_to_leg(leg_id, dz, dx, dy)
                return True
            except Exception as e:
                if self._logger:
                    try: self._logger.exception(e, "DriverMock move_leg_delta 错误")
                    except Exception: pass
                return False

    def stop_all(self) -> None:
        # 简单标记各腿状态为 stopped / estop（不改变坐标）
        with self._lock:
            for leg in self._legs:
                try:
                    setattr(leg, "status", "STOPPED")
                except Exception:
                    pass

    # 内部：把增量应用到指定 leg（id 从 1 开始）
    def _apply_to_leg(self, leg_id: int, dz_mm: float, dx_mm: float, dy_mm: float):
        idx = int(leg_id) - 1
        if idx < 0 or idx >= len(self._legs):
            return
        leg = self._legs[idx]
        # 保护性读取/写入，若属性不存在则跳过
        try:
            # z 单位为 mm，正 dz 表示下降（增加 z 值）
            current_z = float(getattr(leg, "z", 0.0))
            new_z = max(0.0, current_z + dz_mm)
            setattr(leg, "z", new_z)
        except Exception:
            pass
        try:
            current_x = float(getattr(leg, "x", 0.0))
            setattr(leg, "x", current_x + dx_mm)
        except Exception:
            pass
        try:
            current_y = float(getattr(leg, "y", 0.0))
            setattr(leg, "y", current_y + dy_mm)
        except Exception:
            pass
        try:
            setattr(leg, "status", "MOVING")
        except Exception:
            pass

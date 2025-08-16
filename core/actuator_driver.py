# hardware/actuator_driver.py
# 执行器驱动抽象、Mock实现与工厂方法；与 driver_serial 协作
from typing import List, Dict, Optional

class ActuatorDriver:
    """
    执行器驱动抽象：
      - connect()/disconnect()/is_connected()
      - apply_batch(cmds): cmds=[{"id":int,"dz":float,"dx":float,"dy":float}]
      - move_leg_delta(leg_id, dz, dx, dy)
      - stop_all()
    说明：
      - 上层 ControlSystem 已经会 logger.command(...)，此处可选打印。
      - 真串口实现请见 hardware/driver_serial.py 的 DriverSerial。
    """
    def connect(self) -> bool: raise NotImplementedError
    def disconnect(self) -> None: raise NotImplementedError
    def is_connected(self) -> bool: raise NotImplementedError

    def apply_batch(self, cmds: List[Dict]) -> bool: raise NotImplementedError
    def move_leg_delta(self, leg_id: int, dz: float, dx: float, dy: float) -> bool: raise NotImplementedError
    def stop_all(self) -> None: raise NotImplementedError


class DriverMock(ActuatorDriver):
    """
    Mock 驱动：不与真实硬件通信，仅用于开发/演示。
    - connect()/disconnect()：打印日志
    - apply_batch()/move_leg_delta()：直接返回 True
    - stop_all()：打印日志
    """
    def __init__(self, legs=None, logger=None):
        self.legs = legs or []
        self.logger = logger
        self._connected = False

    def connect(self) -> bool:
        self._connected = True
        if self.logger: self.logger.info("Mock 驱动已连接")
        return True

    def disconnect(self) -> None:
        self._connected = False
        if self.logger: self.logger.info("Mock 驱动已断开")

    def is_connected(self) -> bool:
        return self._connected

    def apply_batch(self, cmds: List[Dict]) -> bool:
        # 可选：这里也打印一条汇总日志
        if self.logger:
            self.logger.debug(f"Mock 批量命令 {len(cmds)} 条（未下发硬件）")
        return True

    def move_leg_delta(self, leg_id: int, dz: float, dx: float, dy: float) -> bool:
        if self.logger:
            self.logger.debug(f"Mock 单腿命令 leg#{leg_id}: Δz={dz:.2f}, Δx={dx:.2f}, Δy={dy:.2f}")
        return True

    def stop_all(self) -> None:
        if self.logger: self.logger.warn("Mock 停止所有通道（演示）")


def build_driver(mode: str = "mock",
                 legs=None,
                 port: Optional[str] = None,
                 baudrate: int = 115200,
                 logger=None) -> ActuatorDriver:
    """
    工厂方法：
      - mode="mock"：返回 DriverMock
      - mode="serial"：返回 DriverSerial（需要 pyserial 且指定 port）
    """
    mode = (mode or "mock").lower()
    if mode == "serial":
        try:
            from .driver_serial import DriverSerial
        except Exception as e:
            if logger: logger.warn(f"加载 DriverSerial 失败，回退 Mock：{e}")
            return DriverMock(legs=legs, logger=logger)
        if not port:
            if logger: logger.warn("未提供串口端口，回退 Mock 驱动")
            return DriverMock(legs=legs, logger=logger)
        return DriverSerial(port=port, baudrate=baudrate, logger=logger)
    else:
        return DriverMock(legs=legs, logger=logger)

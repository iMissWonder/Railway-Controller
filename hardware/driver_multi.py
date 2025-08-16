# hardware/driver_multi.py 
from typing import List, Dict
from .actuator_driver import ActuatorDriver
from .driver_serial import DriverSerial

class MultiPortDriver(ActuatorDriver):
    """
    leg_id -> COM口 的映射（例如 {1:"COM11", 2:"COM12", ...}）
    apply_batch 会把cmd按腿路由到不同的 DriverSerial
    """
    def __init__(self, mapping: Dict[int, str], baudrate: int = 115200, logger=None):
        self.logger = logger
        self.drivers: Dict[int, DriverSerial] = {}
        for leg_id, port in mapping.items():
            self.drivers[leg_id] = DriverSerial(port=port, baudrate=baudrate, logger=logger)

    def connect(self) -> bool:
        ok = True
        for d in self.drivers.values():
            ok = d.connect() and ok
        return ok

    def disconnect(self) -> None:
        for d in self.drivers.values(): d.disconnect()

    def is_connected(self) -> bool: 
        return all(d.is_connected() for d in self.drivers.values())

    def apply_batch(self, cmds: List[Dict]) -> bool:
        for c in cmds:
            leg = int(c["id"])
            d = self.drivers.get(leg)
            if d: d.move_leg_delta(leg, c["dz"], c["dx"], c["dy"])
        return True

    def move_leg_delta(self, leg_id: int, dz: float, dx: float, dy: float) -> bool:
        d = self.drivers.get(int(leg_id))
        return d.move_leg_delta(leg_id, dz, dx, dy) if d else False

    def stop_all(self) -> None:
        for d in self.drivers.values(): d.stop_all()

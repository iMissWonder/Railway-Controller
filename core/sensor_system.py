# core/sensor_system.py
import threading, time
from typing import Dict, Any, Optional, Tuple, List
from core.logger import Logger

try:
    from hardware.serial_interface import SerialInterface
except Exception:
    SerialInterface = None

class SensorSystem:
    def __init__(self, logger: Logger, mode: str = "mock",
                 port: Optional[str] = None, baud: int = 115200,
                 fusion_rate_hz: float = 20.0, legs: Optional[list] = None):
        self.logger = logger
        self.mode = mode
        self.port = port
        self.baud = baud
        self.dt = 1.0 / max(1.0, fusion_rate_hz)

        self._center: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._att: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._forces: List[float] = [0.0]*12
        self._legs_z: List[float] = [600.0]*12
        self._legs_xy: List[Tuple[float, float]] = [(0.0, 0.0)]*12

        self._ser: Optional[SerialInterface] = None
        self._buf = bytearray()

        # 可选：传入 LegUnit 列表引用，解析到的 z/xy 会写回到这些对象
        self._legs = legs
        self._lock = threading.Lock()

        if self.mode == "serial":
            if SerialInterface is None:
                self.logger.warn("未找到 hardware.serial_interface，切回 mock")
                self.mode = "mock"
            else:
                try:
                    self._ser = SerialInterface(self.port, self.baud, timeout=0.05, logger=self.logger)
                    self._ser.open()
                    self.logger.info(f"传感器串口打开：{self.port}@{self.baud}")
                    self._ser.start_reader(self._on_rx_bytes)
                except Exception as e:
                    self.logger.exception(e, "传感器串口打开失败，切回 mock")
                    self.mode = "mock"

    # 查询
    def estimate_center(self) -> Tuple[float, float, float]: return self._center
    def estimate_attitude(self) -> Tuple[float, float, float]: return self._att
    def latest_forces(self) -> List[float]: return self._forces[:]
    def legs_state(self) -> Dict[str, Any]: return {"z": self._legs_z[:], "xy": self._legs_xy[:]}

    def refresh_once(self):
        raw = self._snapshot_raw() if self.mode == "serial" else self._mock_pull()
        self._fuse(raw)
        cx, cy, cz = self._center; r, p, y = self._att
        self.logger.telemetry(center_z=round(cz,1), roll=round(r,4), pitch=round(p,4),
                              forces=[round(f,1) for f in self._forces])
        time.sleep(self.dt)

    def shutdown(self):
        if self._ser:
            try:
                self._ser.stop_reader(); self._ser.close()
                self.logger.info("传感器串口关闭")
            except Exception:
                pass

    # 串口回调解析（文本协议）
    def _on_rx_bytes(self, chunk: bytes):
        if not chunk: return
        self._buf.extend(chunk)
        while True:
            pos = self._buf.find(b'\n')
            if pos == -1: break
            line = self._buf[:pos].decode(errors="ignore").strip()
            del self._buf[:pos+1]
            if line:
                self.logger.serial(line, direction="RX")
                self._parse_line(line)

    def _parse_line(self, line: str):
        try:
            parts = line.split(",")
            tag = parts[0].upper()
            if tag == "IMU" and len(parts) >= 4:
                self._att = (float(parts[1]), float(parts[2]), float(parts[3]))
            elif tag == "FOR" and len(parts) >= 3:
                i = int(parts[1])-1; val = float(parts[2])
                if 0 <= i < 12: self._forces[i] = val
            elif tag == "Z" and len(parts) >= 3:
                i = int(parts[1])-1; val = float(parts[2])
                if 0 <= i < 12: self._legs_z[i] = val
            elif tag == "XY" and len(parts) >= 4:
                i = int(parts[1])-1; x = float(parts[2]); y = float(parts[3])
                if 0 <= i < 12: self._legs_xy[i] = (x, y)
        except Exception:
            pass

    def _snapshot_raw(self) -> Dict[str, Any]:
        return {"att": self._att, "forces": self._forces[:],
                "z": self._legs_z[:], "xy": self._legs_xy[:]}

    # —— mock 不再“自动下降”，只加微小噪声 ——
    def _mock_pull(self) -> Dict[str, Any]:
        import random
        self._att = (self._att[0]*0.9 + random.uniform(-0.002,0.002),
                     self._att[1]*0.9 + random.uniform(-0.002,0.002), 0.0)
        # 轻微噪声，不改变趋势
        self._forces = [max(0.0, f + random.uniform(-1.0, 1.0)) for f in self._forces]
        self._legs_z = [z + random.uniform(-0.3, 0.3) for z in self._legs_z]
        self._legs_xy = [(xy[0]+random.uniform(-0.1,0.1), xy[1]+random.uniform(-0.1,0.1)) for xy in self._legs_xy]
        return self._snapshot_raw()

    # 融合（中心Z取 5..8 平均）
    def _fuse(self, raw: Dict[str, Any]):
        z = raw.get("z", self._legs_z)
        cz = (z[4] + z[5] + z[6] + z[7]) / 4.0 if len(z) >= 8 else 0.0
        cx, cy = 0.0, 0.0
        self._center = (cx, cy, cz)
        self._att = raw.get("att", self._att)
        self._forces = raw.get("forces", self._forces)
        self._legs_z = raw.get("z", self._legs_z)
        self._legs_xy = raw.get("xy", self._legs_xy)

        # 将解析到的传感器值写回 LegUnit（如果传入了 legs 引用）
        if self._legs:
            try:
                with self._lock:
                    n = min(len(self._legs), len(self._legs_z), len(self._legs_xy))
                    for i in range(n):
                        try:
                            leg = self._legs[i]
                            # 将 Z/XY 直接写回 leg（单位：mm），保持防护性赋值
                            setattr(leg, "z", float(self._legs_z[i]))
                            x, y = self._legs_xy[i]
                            setattr(leg, "x", float(x))
                            setattr(leg, "y", float(y))
                        except Exception:
                            pass
            except Exception:
                pass

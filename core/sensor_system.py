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

        # 批量日志控制
        self._batch_data = {"imu": None, "legs": [None]*12}
        self._legs_received_count = 0
        
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
                # 不再输出原始行，只输出解析后的合并信息
                self._parse_line(line)

    def _parse_line(self, line: str):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3: return

        cmd = parts[0].upper()
        try:
            if cmd == "IMU":
                roll, pitch, yaw = float(parts[1]), float(parts[2]), float(parts[3])
                self._att = (roll, pitch, yaw)
                # 立即输出IMU信息
                if self.logger:
                    self.logger.serial(f"RX IMU: roll={roll:.4f}, pitch={pitch:.4f}, yaw={yaw:.4f}", direction="RX")

            elif cmd in ("FOR", "Z", "XY"):
                idx = int(parts[1]) - 1
                if 0 <= idx < 12:
                    if cmd == "FOR":
                        force = float(parts[2])
                        self._forces[idx] = force
                        # 更新批量数据
                        if self._batch_data["legs"][idx] is None:
                            self._batch_data["legs"][idx] = {}
                        self._batch_data["legs"][idx]["F"] = force
                        
                    elif cmd == "Z":
                        z_mm = float(parts[2])
                        self._legs_z[idx] = z_mm
                        # 更新批量数据
                        if self._batch_data["legs"][idx] is None:
                            self._batch_data["legs"][idx] = {}
                        self._batch_data["legs"][idx]["Z"] = z_mm
                        
                    elif cmd == "XY":
                        x_mm, y_mm = float(parts[2]), float(parts[3])
                        self._legs_xy[idx] = (x_mm, y_mm)
                        # 更新批量数据
                        if self._batch_data["legs"][idx] is None:
                            self._batch_data["legs"][idx] = {}
                        self._batch_data["legs"][idx]["X"] = x_mm
                        self._batch_data["legs"][idx]["Y"] = y_mm
                        
                        # 当收到XY时，检查该腿是否收齐了XYZF数据，如果是则累计
                        leg_data = self._batch_data["legs"][idx]
                        if all(k in leg_data for k in ["X", "Y", "Z", "F"]):
                            self._legs_received_count += 1
                            
                        # 如果所有12个腿子都收齐了，输出批量信息
                        if self._legs_received_count >= 12:
                            self._output_batch_legs()
                            self._reset_batch_data()
                            
        except (ValueError, IndexError):
            pass

    def _output_batch_legs(self):
        """输出所有腿子的批量信息到一行"""
        if not self.logger:
            return
            
        leg_parts = []
        for i in range(12):
            leg_data = self._batch_data["legs"][i]
            if leg_data and all(k in leg_data for k in ["X", "Y", "Z", "F"]):
                x, y, z, f = leg_data["X"], leg_data["Y"], leg_data["Z"], leg_data["F"]
                leg_parts.append(f"L{i+1:02d}({x:.0f},{y:.0f},{z:.0f},{f:.0f})")
            else:
                leg_parts.append(f"L{i+1:02d}(---)")
        
        # 分成两行，每行6个腿子，避免过长
        line1 = " ".join(leg_parts[:6])
        line2 = " ".join(leg_parts[6:])
        self.logger.serial(f"RX LEGS1-6:  {line1}", direction="RX")
        self.logger.serial(f"RX LEGS7-12: {line2}", direction="RX")

    def _reset_batch_data(self):
        """重置批量数据"""
        self._batch_data = {"imu": None, "legs": [None]*12}
        self._legs_received_count = 0

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

# hardware/mock_serial_device.py
import struct
import time
import threading
import random
import argparse
from typing import Optional

from .serial_interface import SerialInterface

def crc16_le(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc >> 1) ^ 0xA001) if (crc & 1) else (crc >> 1)
    return crc & 0xFFFF

def pack_frame(cmd: int, payload: bytes) -> bytes:
    # STX(0xAA55,2) + LEN(1) + CMD(1) + PAYLOAD + CRC(2)
    stx = 0xAA55
    length = 1 + len(payload)
    head = struct.pack("<HB", stx, length) + struct.pack("<B", cmd)
    crc = crc16_le(head[2:] + payload)
    return head + payload + struct.pack("<H", crc)

class MockSerialDevice:
    """
    双口模拟器：
      - 控制口(ctrl): 接收 0x01(批量)/0x02(单腿)/0x03(急停)，回 0x81 ACK
      - 遥测口(telem): 每100ms发送文本遥测：IMU/FOR(12)/Z(12)/XY(12)
    兼容旧用法：若只提供 --port，则该口既做控制也做遥测。
    单位说明：
      - 控制帧 dz/dx/dy 为 0.1mm（dm），与上位机 DriverSerial.mm_to_dm 对齐
      - 遥测 Z 为 mm，小数1位
      - 遥测 FOR 为牛顿（可简化）
    """
    def __init__(self, ctrl_port: str, telem_port: Optional[str] = None,
                 baudrate: int = 115200, logger=None, telemetry_interval: float = 0.1):
        self.ctrl = SerialInterface(ctrl_port, baudrate, timeout=0.02, logger=logger)
        self.telem = None
        if telem_port:
            self.telem = SerialInterface(telem_port, baudrate, timeout=0.02, logger=logger)
        else:
            # 兼容：若不指定，遥测也走控制口
            self.telem = self.ctrl

        self._stop = threading.Event()
        self._rx_buf = bytearray()
        # 内部状态（0.1mm）
        self._z_dm = [int(random.uniform(5800, 6200)) for _ in range(12)]
        # 受力（N*10，发文本时会/10）
        self._force = [int(random.uniform(900, 1100)) for _ in range(12)]
        # XY（mm）
        self._xy = self._default_xy()

        # 急停标志
        self._estop = False
        # 遥测间隔（秒）
        self._telem_interval = float(telemetry_interval)

    # ——— 初始化XY分布（上排 1/3/5/7/9/11， 下排 2/4/6/8/10/12）———
    def _default_xy(self):
        xy = []
        x_positions = [-8700, -8700, -6200, -6200, -3000, -3000, 0, 0, 3000, 3000, 6200, 6200]
        upper_base = random.uniform(760, 820)
        upper_offsets = [random.uniform(-40, 40) for _ in range(6)]
        upper_y = [upper_base + off for off in upper_offsets]
        gaps = [1450 + i * (2600 - 1450) / 5.0 for i in range(6)]
        for k in range(6):
            top_y = upper_y[k]
            bot_y = top_y - gaps[k] + random.uniform(-30, 30)
            xy.append((x_positions[2*k],   top_y))
            xy.append((x_positions[2*k+1], bot_y))

        # 将坐标整体平移，使 1 号腿（索引0）成为原点 (0,0)
        x0, y0 = xy[0]
        shift_x = -x0
        shift_y = -y0
        # 添加小扰动（±5 mm），并将 Y 方向取反（向下为正）
        xy_shifted = []
        for x, y in xy:
            nx = x + shift_x + random.uniform(-5.0, 5.0)
            ny = -(y + shift_y) + random.uniform(-5.0, 5.0)
            xy_shifted.append((nx, ny))
        return xy_shifted  # 长度12，索引0..11

    # ——— 对外入口 ———
    def start(self):
        self.ctrl.open()
        self.ctrl.start_reader(self._on_rx_bytes)
        if self.telem is not self.ctrl:
            self.telem.open()

        print(f"[MockDevice] 控制口: {self.ctrl.port}@{self.ctrl.baudrate}  | 遥测口: {self.telem.port}@{self.telem.baudrate}  | telem-interval: {self._telem_interval}s")
        t = threading.Thread(target=self._telemetry_loop, daemon=True, name="mock_telem")
        t.start()
        try:
            while not self._stop.is_set():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self.ctrl.stop_reader()
            try: self.ctrl.close()
            except: pass
            if self.telem and self.telem is not self.ctrl:
                try: self.telem.close()
                except: pass
            print("[MockDevice] 设备已退出")

    def stop(self):
        self._stop.set()

    # ——— 控制口：接收上位机帧 ———
    def _on_rx_bytes(self, chunk: bytes):
        if not chunk:
            return
        self._rx_buf.extend(chunk)
        i = 0
        while i + 4 <= len(self._rx_buf):
            try:
                stx, = struct.unpack_from("<H", self._rx_buf, i)
                if stx != 0xAA55:
                    i += 1
                    continue
                length = self._rx_buf[i+2]
                cmd = self._rx_buf[i+3]
                end = i + 4 + length + 2
                if end > len(self._rx_buf):
                    break
                frame = self._rx_buf[i:end]
                payload = frame[4:4+length-1]
                # 简化不验CRC
                self._handle_cmd(cmd, payload)
                # 丢弃已处理
                del self._rx_buf[:end]
                i = 0
            except Exception:
                del self._rx_buf[:1]
                i = 0

    def _handle_cmd(self, cmd: int, payload: bytes):
        # 回 ACK（在控制口）
        try:
            self.ctrl.write(pack_frame(0x81, b""))
        except Exception:
            pass

        if cmd == 0x03:
            # 急停：不再响应位移，但仍发遥测
            self._estop = True
            return

        if self._estop:
            # 急停状态下忽略移动命令
            return

        try:
            if cmd == 0x01:
                # 批量：N*(id:1B, dz:2B, dx:2B, dy:2B)  (单位dm)
                step = 1 + 2 + 2 + 2
                for off in range(0, len(payload), step):
                    if off + step > len(payload):
                        break
                    leg_id, dz_dm, dx_dm, dy_dm = struct.unpack_from("<Bhhh", payload, off)
                    self._apply_leg_delta(leg_id, dz_dm, dx_dm, dy_dm)
            elif cmd == 0x02:
                leg_id, dz_dm, dx_dm, dy_dm = struct.unpack("<Bhhh", payload)
                self._apply_leg_delta(leg_id, dz_dm, dx_dm, dy_dm)
        except Exception:
            pass

    # 将 dm(0.1mm) 的位移应用到内部状态
    def _apply_leg_delta(self, leg_id: int, dz_dm: int, dx_dm: int, dy_dm: int):
        idx = int(leg_id) - 1
        if idx < 0 or idx >= 12:
            return
        # Z 只允许“下降”（增大 dm 值表示上升，这里不加）
        self._z_dm[idx] = max(0, self._z_dm[idx] - int(dz_dm))
        # XY 小步跟随（单位同样按 0.1mm -> mm）
        x, y = self._xy[idx]
        self._xy[idx] = (x + dx_dm/10.0, y + dy_dm/10.0)
        # 受力稍微波动
        self._force[idx] = max(0, self._force[idx] + int(random.uniform(-5, 5)))

    # ——— 遥测口：周期发文本遥测 ———
    def _telemetry_loop(self):
        while not self._stop.is_set():
            try:
                # IMU（roll, pitch, yaw）
                imu_line = f"IMU,{random.uniform(-0.02,0.02):.4f},{random.uniform(-0.02,0.02):.4f},0.0000\n"
                self.telem.write(imu_line.encode("utf-8"))

                # FOR（12行）
                for i in range(12):
                    self.telem.write(f"FOR,{i+1},{self._force[i]/10.0:.1f}\n".encode("utf-8"))

                # Z（12行，mm）
                for i in range(12):
                    z_mm = self._z_dm[i] / 10.0
                    self.telem.write(f"Z,{i+1},{z_mm:.1f}\n".encode("utf-8"))

                # XY（12行，mm） — 不在遥测循环中修改 self._xy（移除持续扰动）
                for i in range(12):
                    x, y = self._xy[i]
                    self.telem.write(f"XY,{i+1},{x:.1f},{y:.1f}\n".encode("utf-8"))
            except Exception:
                # 端口被占用或断开，短暂等待再试
                time.sleep(0.2)
                continue
            time.sleep(self._telem_interval)

def main():
    ap = argparse.ArgumentParser(description="下位机串口模拟器（双口）")
    # 新用法：分别指定控制口与遥测口
    ap.add_argument("--ctrl-port", help="控制口（接收上位机指令，如 COM4）")
    ap.add_argument("--telem-port", help="遥测口（发送传感器数据，如 COM5）")
    # 兼容旧用法：只传一个 --port，则该口兼做控制+遥测
    ap.add_argument("--port", help="单口兼容模式（控制+遥测同口）")
    ap.add_argument("--baud", type=int, default=115200, help="波特率")
    ap.add_argument("--telem-interval", type=float, default=0.1, help="遥测发送间隔（秒），默认0.1s")
    args = ap.parse_args()

    if args.port:
        dev = MockSerialDevice(ctrl_port=args.port, telem_port=None, baudrate=args.baud, telemetry_interval=args.telem_interval)
    elif args.ctrl_port:
        dev = MockSerialDevice(ctrl_port=args.ctrl_port, telem_port=args.telem_port, baudrate=args.baud, telemetry_interval=args.telem_interval)
    else:
        print("请指定 --ctrl-port/--telem-port，或使用 --port 单口兼容模式。")
        return

    dev.start()

if __name__ == "__main__":
    main()

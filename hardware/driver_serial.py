# hardware/driver_serial.py
from typing import List, Dict
import struct, time
from .actuator_driver import ActuatorDriver
from .serial_interface import SerialInterface

def crc16_le(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc >> 1) ^ 0xA001) if (crc & 1) else (crc >> 1)
    return crc & 0xFFFF

def pack_frame(cmd: int, payload: bytes) -> bytes:
    stx = 0xAA55
    length = 1 + len(payload)
    head = struct.pack("<HB", stx, length) + struct.pack("<B", cmd)
    crc = crc16_le(head[2:] + payload)
    return head + payload + struct.pack("<H", crc)

def mm_to_dm(v_mm: float) -> int:
    return int(round(v_mm * 10.0))

class DriverSerial(ActuatorDriver):
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.05, retry: int = 1, logger=None):
        self.iface = SerialInterface(port, baudrate, timeout, logger=logger)
        self.retry = retry
        self.logger = logger
        self._last_rx = b""

    def connect(self) -> bool:
        ok = self.iface.open()
        self.iface.start_reader(self._on_rx)
        if ok and self.logger: self.logger.info(f"串口已连接：{self.iface.port}@{self.iface.baudrate}")
        return ok

    def disconnect(self) -> None:
        self.iface.stop_reader()
        self.iface.close()
        if self.logger: self.logger.info("串口已断开")

    def is_connected(self) -> bool:
        return self.iface.is_open()

    def apply_batch(self, cmds: List[Dict]) -> bool:
        # 先按腿记录可读的“人类友好日志”（非DEBUG也显示）
        if self.logger:
            for c in cmds:
                self.logger.serial(f"TX leg#{int(c['id']):02d} Δz={c['dz']:.2f} Δx={c['dx']:.2f} Δy={c['dy']:.2f}", direction="TX")

        # 再拼帧发送
        payload = bytearray()
        for c in cmds[:12]:
            payload += struct.pack("<Bhhh",
                                   int(c["id"]),
                                   mm_to_dm(float(c["dz"])),
                                   mm_to_dm(float(c["dx"])),
                                   mm_to_dm(float(c["dy"])))
        frame = pack_frame(0x01, bytes(payload))
        if self.logger: self.logger.serial(f"TX frame len={len(frame)}", direction="TX")
        return self._send(frame, expect_ack=True)

    def move_leg_delta(self, leg_id: int, dz: float, dx: float, dy: float) -> bool:
        if self.logger:
            self.logger.serial(f"TX leg#{int(leg_id):02d} Δz={dz:.2f} Δx={dx:.2f} Δy={dy:.2f}", direction="TX")
        payload = struct.pack("<Bhhh", int(leg_id), mm_to_dm(dz), mm_to_dm(dx), mm_to_dm(dy))
        frame = pack_frame(0x02, payload)
        if self.logger: self.logger.serial(f"TX frame len={len(frame)}", direction="TX")
        return self._send(frame, expect_ack=True)

    def stop_all(self) -> None:
        try:
            if self.logger: self.logger.serial("TX EMERGENCY STOP", direction="TX")
            self._send(pack_frame(0x03, b""), expect_ack=False)
        except Exception as e:
            if self.logger: self.logger.exception(e, "stop_all 发送失败")

    def _send(self, frame: bytes, expect_ack: bool = True) -> bool:
        last_err = None
        for attempt in range(max(1, self.retry)):
            try:
                if not self.is_connected():
                    if self.logger: self.logger.serial("reconnect", direction="TX")
                    self.connect()
                self.iface.write(frame)
                if expect_ack:
                    t0 = time.time()
                    while time.time() - t0 < 0.3:
                        if b"\x81" in self._last_rx:
                            return True
                        time.sleep(0.01)
                    if self.logger: self.logger.warn("等待ACK超时")
                else:
                    return True
            except Exception as e:
                last_err = e
                if self.logger: self.logger.exception(e, "串口发送失败")
                time.sleep(0.02)
        if last_err:
            raise last_err
        return False

    def _on_rx(self, chunk: bytes):
        self._last_rx = chunk
        if self.logger: self.logger.serial(f"RX {len(chunk)}B", direction="RX")

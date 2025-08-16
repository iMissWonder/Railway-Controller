
from __future__ import annotations
from dataclasses import dataclass
from .utils import crc16_modbus

STX = b"\x55\xAA"

@dataclass
class Frame:
    cmd: int
    payload: bytes
    raw: bytes

def encode_frame(cmd: int, payload: bytes) -> bytes:
    assert 0 <= cmd <= 0xFF
    body = bytes([cmd]) + payload
    frame_wo_crc = STX + bytes([len(body)]) + body
    c = crc16_modbus(frame_wo_crc)
    return frame_wo_crc + c.to_bytes(2, "little")

class Decoder:
    """状态机解包，处理拆包/粘包/错包。"""
    def __init__(self):
        self.buf = bytearray()
        self.state = 0  # 0: find 0x55, 1: find 0xAA, 2: LEN, 3: BODY+CRC
        self.need = 1
        self.length = 0

    def feed(self, data: bytes) -> list[Frame]:
        out: list[Frame] = []
        for b in data:
            self.buf.append(b)
            if self.state == 0:  # find 0x55
                if b == 0x55:
                    self.state = 1
                else:
                    self.buf.clear()
            elif self.state == 1:  # find 0xAA
                if b == 0xAA:
                    self.state = 2
                else:
                    self.buf.clear()
                    self.state = 0
            elif self.state == 2:  # LEN
                self.length = b
                self.state = 3
                self.need = self.length + 2  # BODY + CRC
            elif self.state == 3:  # BODY+CRC
                self.need -= 1
                if self.need == 0:
                    full = bytes(self.buf)
                    self.buf.clear()
                    self.state = 0
                    if len(full) < 5:
                        continue
                    frame_wo_crc = full[:-2]
                    crc_recv = int.from_bytes(full[-2:], "little")
                    if crc_recv != crc16_modbus(frame_wo_crc):
                        # CRC 错，丢弃这帧
                        continue
                    cmd = full[3]
                    payload = full[4:-2]
                    out.append(Frame(cmd=cmd, payload=payload, raw=full))
        return out

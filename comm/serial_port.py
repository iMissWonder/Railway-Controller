
from __future__ import annotations
import threading, time
import serial
from typing import Optional

class SerialPort:
    def __init__(self, port: str, baud: int = 115200, timeout=0.1):
        self.port_name = port
        self.baud = baud
        self.timeout = timeout
        self._ser: Optional[serial.Serial] = None
        self._lock = threading.Lock()

    def open(self):
        if self._ser and self._ser.is_open:
            return
        self._ser = serial.Serial(
            self.port_name, self.baud, timeout=self.timeout, write_timeout=0.5
        )
        # 某些 CH340 需要 DTR/RTS
        try:
            self._ser.setDTR(True); self._ser.setRTS(True)
        except Exception:
            pass
        self._ser.reset_input_buffer()
        self._ser.reset_output_buffer()

    def close(self):
        with self._lock:
            if self._ser:
                try:
                    self._ser.close()
                finally:
                    self._ser = None

    def write(self, data: bytes) -> int:
        with self._lock:
            if not self._ser:
                raise RuntimeError("Serial not open")
            n = self._ser.write(data)
            self._ser.flush()
            return n

    def read_some(self, max_bytes: int = 256) -> bytes:
        s = self._ser
        if not s:
            return b""
        try:
            return s.read(max_bytes)
        except Exception:
            return b""

    @property
    def is_open(self) -> bool:
        return bool(self._ser and self._ser.is_open)

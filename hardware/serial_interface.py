# hardware/serial_interface.py
from typing import Optional, Callable
import threading, time
try:
    import serial  # pip install pyserial
except Exception:
    serial = None

class SerialInterface:
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.05, logger=None):
        self.port = port; self.baudrate = baudrate; self.timeout = timeout
        self._ser: Optional["serial.Serial"] = None
        self._lock = threading.Lock()
        self._reader: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.logger = logger

    def open(self) -> bool:
        if serial is None:
            raise RuntimeError("pyserial 未安装：pip install pyserial")
        with self._lock:
            if self._ser and self._ser.is_open:
                if self.logger: self.logger.debug(f"SerialInterface.open: already open {self.port}")
                return True
            if self.logger: self.logger.debug(f"SerialInterface.open: opening {self.port}@{self.baudrate}")
            self._ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            if self.logger: self.logger.debug(f"SerialInterface.open: opened={self._ser.is_open}")
            return self._ser.is_open

    def close(self) -> None:
        self.stop_reader()
        with self._lock:
            if self._ser and self._ser.is_open:
                if self.logger: self.logger.debug("SerialInterface.close: closing")
                self._ser.close()
            self._ser = None

    def is_open(self) -> bool:
        with self._lock:
            return bool(self._ser and self._ser.is_open)

    def write(self, data: bytes) -> int:
        with self._lock:
            if not self._ser or not self._ser.is_open: raise RuntimeError("串口未打开")
            n = self._ser.write(data)
            if self.logger: self.logger.debug(f"SerialInterface.write: wrote {n} bytes")
            return n

    def read(self, size: int = 1024) -> bytes:
        with self._lock:
            if not self._ser or not self._ser.is_open: raise RuntimeError("串口未打开")
            b = self._ser.read(size)
            return b

    # 读线程
    def start_reader(self, on_bytes: Callable[[bytes], None]):
        if not callable(on_bytes): return
        if self._reader and self._reader.is_alive(): return
        self._stop.clear()
        self._reader = threading.Thread(target=self._loop, args=(on_bytes,), daemon=True, name="serial_rx")
        if self.logger: self.logger.debug("SerialInterface.start_reader: starting reader thread")
        self._reader.start()

    def stop_reader(self):
        self._stop.set()
        if self._reader and self._reader.is_alive():
            if self.logger: self.logger.debug("SerialInterface.stop_reader: joining reader thread")
            self._reader.join(timeout=1.0)
        self._reader = None

    def _loop(self, on_bytes):
        if self.logger: self.logger.debug("SerialInterface._loop: reader started")
        while not self._stop.is_set():
            try:
                chunk = self.read(512)
                if chunk:
                    on_bytes(chunk)
                else:
                    time.sleep(0.01)
            except Exception as e:
                if self.logger: self.logger.debug(f"SerialInterface._loop: read error {e}")
                time.sleep(0.02)
        if self.logger: self.logger.debug("SerialInterface._loop: reader stopped")


from __future__ import annotations
import threading, time, logging
from concurrent.futures import Future
from typing import Callable, Dict, Optional

from .serial_port import SerialPort
from .framer import encode_frame, Decoder
from .protocol import CMD, is_ack, ack_of, is_push
from .utils import to_hex

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

class CommState:
    DISCONNECTED = "DISCONNECTED"
    CONNECTING   = "CONNECTING"
    READY        = "READY"
    ERROR        = "ERROR"

class CommService:
    def __init__(self, port: str, baud: int = 115200,
                 heartbeat_interval: float = 1.0, reconnect_interval: float = 2.0):
        self.port = SerialPort(port, baud)
        self.decoder = Decoder()
        self.heartbeat_interval = heartbeat_interval
        self.reconnect_interval = reconnect_interval

        self._reader_th: Optional[threading.Thread] = None
        self._hb_th: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._seq = 0
        self._pending: Dict[int, Future] = {}
        self._subscribers: list[Callable[[int, bytes], None]] = []
        self.state = CommState.DISCONNECTED
        self._state_lock = threading.Lock()

    # ---------- lifecycle ----------
    def start(self):
        self._stop.clear()
        self._ensure_open()
        self._reader_th = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_th.start()
        self._hb_th = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._hb_th.start()

    def stop(self):
        self._stop.set()
        time.sleep(0.05)
        if self.port.is_open:
            self.port.close()
        self._clear_pending(RuntimeError("CommService stopped"))
        self._set_state(CommState.DISCONNECTED)

    def subscribe(self, cb: Callable[[int, bytes], None]):
        self._subscribers.append(cb)

    def wait_ready(self, timeout: float = 2.0) -> bool:
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.state == CommState.READY:
                return True
            time.sleep(0.05)
        return False

    # ---------- API ----------
    def request(self, cmd: int, payload_wo_seq: bytes,
                timeout: float = 0.5, retry: int = 2) -> tuple[bool, bytes]:
        """阻塞式请求，内部自动加 seq、封帧、等待 ACK。返回 (ok, ack_payload)"""
        for attempt in range(retry + 1):
            seq = self._next_seq()
            payload = bytes([seq]) + payload_wo_seq
            frame = encode_frame(cmd, payload)
            fut = Future()
            self._pending[seq] = fut
            try:
                self._send(frame, note=f"CMD=0x{cmd:02X} SEQ={seq}")
            except Exception as e:
                self._pending.pop(seq, None)
                self._set_state(CommState.ERROR)
                if attempt == retry:
                    return False, b""
                time.sleep(0.1)
                continue

            try:
                ok_payload = fut.result(timeout=timeout)
                return True, ok_payload
            except Exception:
                # 超时/错误，重试
                self._pending.pop(seq, None)
                if attempt == retry:
                    return False, b""
        return False, b""

    # ---------- internals ----------
    def _ensure_open(self):
        if not self.port.is_open:
            self._set_state(CommState.CONNECTING)
            try:
                self.port.open()
                self._set_state(CommState.READY)  # 先标 READY，后续心跳校验
            except Exception as e:
                logging.warning("Open serial failed: %s", e)
                self._set_state(CommState.DISCONNECTED)

    def _reader_loop(self):
        while not self._stop.is_set():
            if not self.port.is_open:
                time.sleep(self.reconnect_interval)
                self._ensure_open()
                continue
            data = self.port.read_some(256)
            if not data:
                time.sleep(0.005)
                continue
            frames = self.decoder.feed(data)
            for fr in frames:
                if is_ack(fr.cmd):
                    # ACK: payload = [seq, status, ...]
                    if len(fr.payload) >= 1:
                        seq = fr.payload[0]
                        fut = self._pending.pop(seq, None)
                        if fut and not fut.done():
                            fut.set_result(fr.payload)
                            logging.info("RX ACK  cmd=0x%02X seq=%d len=%d  raw=%s",
                                         fr.cmd, seq, len(fr.payload), to_hex(fr.raw))
                elif is_push(fr.cmd):
                    for cb in self._subscribers:
                        try: cb(fr.cmd, fr.payload)
                        except Exception as e: logging.warning("push cb err: %s", e)
                    logging.info("RX PUSH cmd=0x%02X len=%d  raw=%s",
                                 fr.cmd, len(fr.payload), to_hex(fr.raw))
                else:
                    # 非ACK、非PUSH 的“普通响应”也可能存在，直接广播
                    for cb in self._subscribers:
                        try: cb(fr.cmd, fr.payload)
                        except Exception as e: logging.warning("cb err: %s", e)
                    logging.info("RX     cmd=0x%02X len=%d  raw=%s",
                                 fr.cmd, len(fr.payload), to_hex(fr.raw))

    def _heartbeat_loop(self):
        miss = 0
        last_ok = time.time()
        while not self._stop.is_set():
            if not self.port.is_open:
                time.sleep(self.reconnect_interval)
                self._ensure_open()
                miss = 0
                continue

            ok, _ = self.request(CMD.PING, b"", timeout=0.3, retry=0)
            if ok:
                miss = 0
                last_ok = time.time()
                if self.state != CommState.READY:
                    self._set_state(CommState.READY)
            else:
                miss += 1
                if miss >= 3:
                    self._set_state(CommState.DISCONNECTED)
                    self.port.close()
                    # 等待下一轮 _ensure_open 重连
            time.sleep(self.heartbeat_interval)

    def _send(self, frame: bytes, note: str = ""):
        self.port.write(frame)
        logging.info("TX %s  %s", note, to_hex(frame))

    def _next_seq(self) -> int:
        self._seq = (self._seq + 1) & 0xFF
        if self._seq == 0:
            self._seq = 1
        return self._seq

    def _clear_pending(self, exc: Exception):
        for _, fut in list(self._pending.items()):
            if not fut.done():
                fut.set_exception(exc)
        self._pending.clear()

    def _set_state(self, st: str):
        with self._state_lock:
            if self.state != st:
                self.state = st
                logging.info("CommState => %s", st)

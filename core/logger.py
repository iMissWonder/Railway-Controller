# core/logger.py
import datetime, threading, time, queue, threading
from typing import Callable, Optional, Dict

_LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}

class Logger:
    """
    - 线程安全；所有GUI输出走队列，由GUI端定时drain（避免跨线程直接写Tk）
    - 支持两路队列：主日志队列 / 串口监视队列
    - throttled_log(key, msg, min_interval_s)
    """
    def __init__(self, gui_log_callback: Optional[Callable[[str], None]] = None,
                 level: str = "INFO"):
        self._level = _LEVELS.get(level.upper(), 20)
        self._throttle: Dict[str, float] = {}
        self._gui_sink: Optional[Callable[[str], None]] = gui_log_callback
        self._serial_sink: Optional[Callable[[str], None]] = None
        self.gui_queue: "queue.Queue[str]" = queue.Queue(maxsize=2000)
        self.serial_queue: "queue.Queue[str]" = queue.Queue(maxsize=4000)
        self._lock = threading.Lock()

    # GUI 绑定（GUI里会开启after定时从队列取消息写入）
    def bind_gui_log(self, drain_callback: Callable[[str], None]):
        with self._lock:
            self._gui_sink = drain_callback

    def bind_serial_log(self, drain_callback: Callable[[str], None]):
        with self._lock:
            self._serial_sink = drain_callback

    # 工具
    def _ts(self) -> str:
        return datetime.datetime.now().strftime("[%H:%M:%S]")

    def _tid(self) -> str:
        return threading.current_thread().name

    def _put_gui(self, s: str):
        try: self.gui_queue.put_nowait(s)
        except queue.Full: pass

    def _put_ser(self, s: str):
        try: self.serial_queue.put_nowait(s)
        except queue.Full: pass

    def _console(self, s: str):
        print(s, flush=True)

    def _should(self, level: str) -> bool:
        return _LEVELS.get(level.upper(), 999) >= self._level

    # 主日志
    def debug(self, msg: str):
        if self._should("DEBUG"):
            line = f"{self._ts()} [DEBUG]({self._tid()}) {msg}"
            self._console(line); self._put_gui(line)

    def info(self, msg: str):
        if self._should("INFO"):
            line = f"{self._ts()} [INFO]({self._tid()}) {msg}"
            self._console(line); self._put_gui(line)

    def warn(self, msg: str):
        if self._should("WARN"):
            line = f"{self._ts()} [WARN]({self._tid()}) {msg}"
            self._console(line); self._put_gui(line)

    def error(self, msg: str):
        if self._should("ERROR"):
            line = f"{self._ts()} [ERROR]({self._tid()}) {msg}"
            self._console(line); self._put_gui(line)

    def exception(self, exc: BaseException, msg: str = ""):
        self.error(f"{msg} | {exc.__class__.__name__}: {exc}")

    # 串口监视
    def serial(self, message: str, direction: str = "RX"):
        line = f"{self._ts()} [SERIAL:{direction}]({self._tid()}) {message}"
        self._console(line); self._put_ser(line)

    # 遥测
    def telemetry(self, **kv):
        pairs = ", ".join(f"{k}={v}" for k, v in kv.items())
        line = f"{self._ts()} [TEL]({self._tid()}) {pairs}"
        self._console(line); self._put_gui(line)

    # 腿子指令
    def command(self, leg_id: int, dx: float, dy: float, dz: float, reason: str = ""):
        line = f"{self._ts()} [CMD]({self._tid()}) LEG#{leg_id:02d} Δx={dx:.2f} Δy={dy:.2f} Δz={dz:.2f} {reason}"
        self._console(line); self._put_gui(line)

    # 阶段提示
    def enter_stage(self, name: str, target_center_z_mm: float = None):
        if target_center_z_mm is None:
            self.info(f"进入 {name}")
        else:
            self.info(f"进入 {name}，目标中心 {target_center_z_mm:.0f}mm")

    def complete_stage(self, name: str, current_center_z_mm: float = None):
        if current_center_z_mm is None:
            self.info(f"完成 {name}")
        else:
            self.info(f"完成 {name}，当前中心 {current_center_z_mm:.0f}mm")

    # 限流日志
    def throttled_log(self, key: str, msg: str, min_interval_s: float = 1.0, level: str = "DEBUG"):
        now = time.time()
        last = self._throttle.get(key, 0.0)
        if now - last >= min_interval_s:
            self._throttle[key] = now
            getattr(self, level.lower(), self.debug)(msg)

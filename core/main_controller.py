# core/main_controller.py
from typing import List, Optional, Callable
import random

from core.center_estimator import CenterEstimator
from core.control_system import ControlSystem
from core.sensor_system import SensorSystem
from hardware.actuator_driver import build_driver

class LegUnit:
    def __init__(self, leg_id: int):
        self.id = leg_id
        self.name = f"{leg_id:02d}"
        self.x: float = 0.0
        self.y: float = 0.0
        self.z: float = 0.0
        self.force: float = 0.0
        self.status: str = "初始化"
    def reset_random(self):
        self.status = "初始化"
        self.z = 600.0 + random.uniform(-20.0, 20.0)
        self.force = 0.0

class MainController:
    def __init__(self, logger, gui_update_cb: Optional[Callable] = None,
                 driver_mode: str = "mock", serial_port: Optional[str] = None,
                 baudrate: int = 115200, sensor_mode: str = "mock",
                 sensor_port: Optional[str] = None, sensor_baud: int = 115200):
        self.logger = logger
        self.update_ui = gui_update_cb

        self.legs: List[LegUnit] = [LegUnit(i+1) for i in range(12)]
        self._generate_leg_positions()
        self.logger.info("MainController 初始化：腿子坐标已随机生成。")

        self.estimator = CenterEstimator(
            center_indices=(4,5,6,7), corner_indices=(0,1,10,11),
            ema_alpha=0.35, outlier_mm=30.0, force_threshold=(80.0,120.0),
        )
        self.sensor = SensorSystem(
            logger=self.logger, mode=sensor_mode,
            port=sensor_port, baud=sensor_baud, fusion_rate_hz=20.0,
            legs=self.legs
        )

        if driver_mode == "serial" and serial_port:
            self.driver = build_driver("serial", port=serial_port, baudrate=baudrate, logger=self.logger)
        else:
            if driver_mode == "serial":
                self.logger.warn("未提供串口端口，回退 mock 驱动")
            self.driver = build_driver("mock", legs=self.legs, logger=self.logger)

        #simulate_feedback = True
        simulate_feedback = driver_mode == "mock" and sensor_mode == "mock"
        self.control = ControlSystem(
            legs=self.legs, logger=self.logger, update_callback=self._ui_draw_proxy,
            estimator=self.estimator, sensor_system=self.sensor, driver=self.driver,
            simulate_feedback=simulate_feedback
        )

        self.period_ms: int = 500  # 改为500，与GUI一致
        self.center_rate_mm_s: float = 10.0  # 改为10.0，与GUI一致
        self.logger.info(f"控制器就绪（driver={driver_mode}, sensor={sensor_mode}, simulate={simulate_feedback}）。"
                         f"周期={self.period_ms}ms，中心速率={self.center_rate_mm_s}mm/s")

    # GUI 接口
    def get_leg_data(self) -> List[LegUnit]: return self.legs

    def start_loop(self, period_ms: Optional[int] = None, rate_mm_s: Optional[float] = None):
        # 如果传入参数，则更新；否则使用当前值
        if period_ms is not None: 
            self.period_ms = max(30, int(period_ms))
        if rate_mm_s is not None: 
            self.center_rate_mm_s = max(0.0, float(rate_mm_s))

        # 允许从停止/急停恢复：先尝试重连驱动
        if hasattr(self.driver, "connect"):
            try:
                self.driver.connect(); self.logger.info("驱动连接成功。")
            except Exception as e:
                self.logger.exception(e, "驱动连接失败")

        # 一次性设置控制系统参数（避免重复调用）
        period_ms = self.period_ms
        rate_mm_s = self.center_rate_mm_s
        max_single_step = rate_mm_s * (period_ms / 1000.0)
        
        self.control.update_control_params(
            period_ms=float(period_ms),
            rate_mm_s=rate_mm_s,
            max_single_step=max_single_step
        )
        
        self.control.start_loop(int(self.period_ms))
        cz = self.get_current_center_z()
        self.logger.enter_stage("周期闭环", target_center_z_mm=cz-100)
        self.logger.info("控制循环启动。")

    def stop_loop(self):
        self.control.stop_loop()
        if hasattr(self.driver, "disconnect"):
            try: self.driver.disconnect()
            except Exception as e: self.logger.exception(e, "驱动断开异常")
        cz = self.get_current_center_z()
        self.logger.complete_stage("周期闭环", current_center_z_mm=cz)
        self.logger.info("控制循环停止。")

    def emergency_stop(self): self.control.emergency_stop()

    def set_center_rate(self, rate_mm_s: float):
        self.center_rate_mm_s = max(0.0, float(rate_mm_s))
        self.logger.info(f"更新中心下降速率：{self.center_rate_mm_s:.1f} mm/s")

    def set_period_ms(self, period_ms: int):
        self.period_ms = max(30, int(period_ms))
        self.logger.info(f"更新控制周期：{self.period_ms} ms")

    def reset_all(self):
        # 重置腿数据 + 重新随机 XY/Z；并通知 UI
        for l in self.legs: l.reset_random()
        self._generate_leg_positions(xy_only=True)
        self.logger.info("系统已重置：腿子位置/高度已随机初始化。")
        if self.update_ui: self.update_ui("已重置", "重置")

    def shutdown(self):
        try: self.stop_loop()
        except Exception: pass
        try: self.sensor.shutdown()
        except Exception: pass

    def _ui_draw_proxy(self, full_stage: str, short_stage: str):
        if self.update_ui:
            try: self.update_ui(full_stage, short_stage)
            except Exception: pass

    def _generate_leg_positions(self, xy_only: bool = False):
        # 固定的腿子坐标配置
        fixed_positions = [
            (0.0, 0.0),         # 腿子1
            (0.0, 171.7),       # 腿子2
            (489.9, 0.0),       # 腿子3
            (490.0, 182.3),     # 腿子4
            (969.9, 0.0),       # 腿子5
            (970.0, 197.1),     # 腿子6
            (1449.9, 0.0),      # 腿子7
            (1449.7, 223.1),    # 腿子8
            (1929.9, 0.0),      # 腿子9
            (1930.0, 262.6),    # 腿子10
            (2409.9, 0.0),      # 腿子11
            (2410.0, 311.6)     # 腿子12
        ]

        # 理论中心位置 (理论上应该是 1144.3, 85.0)
        self.theoretical_center_x = 1144.3
        self.theoretical_center_y = 85.0

        # 直接使用固定坐标设置每个腿的位置
        for i in range(12):
            x, y = fixed_positions[i]
            if not xy_only:
                # 若包含 Z/init 等，保留原逻辑对 z 的设置
                self.legs[i].reset_random() if hasattr(self.legs[i], "reset_random") else None
                self.legs[i].x = x
                self.legs[i].y = y
                # 保持原有 z 初始化策略（若有）不变
            else:
                self.legs[i].x = x
                self.legs[i].y = y

        self.logger.info("已设置固定的腿子 XY 坐标（理论中心: {:.1f}, {:.1f}）。".format(
            self.theoretical_center_x, self.theoretical_center_y))

    def get_current_center_z(self) -> float:
        try:
            st = self.estimator.estimate(self.legs, self.sensor)
            return st.center_z
        except Exception:
            return sum(l.z for l in self.legs)/max(1, len(self.legs))

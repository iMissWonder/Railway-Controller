# core/control_system.py
import threading, time, random
from typing import List, Dict, Tuple, Optional

FORCE_THRESHOLD = (80.0, 120.0)
ATTITUDE_OUTLIER_MM = 20.0
MAX_STEP_Z_MM = 8.0
MAX_STEP_XY_MM = 2.0
CENTER_Z_RATE_MM_S = 20.0
LEVELING_GAIN = 0.4
CENTER_GAIN_XY = 0.2
PAIR_CONSTRAINT_WEIGHT = 1.0
PAIR_X_JITTER_MM = 1.0

class ControlSystem:
    def __init__(self, legs, logger, update_callback, estimator, sensor_system, driver,
                 simulate_feedback: bool = False):
        self.legs = legs
        self.logger = logger
        self.update_ui = update_callback
        self.estimator = estimator
        self.sensor = sensor_system
        self.driver = driver
        self.simulate_feedback = bool(simulate_feedback)

        self._loop_thread: Optional[threading.Thread] = None
        self._loop_stop = threading.Event()
        self.period_s = 0.1
        self._last_ts = None
        self._target_center_z = self._get_initial_center_z()

        self.upper_leg_indices = [0, 2, 4, 6, 8, 10]
        self.lower_leg_indices = [1, 3, 5, 7, 9, 11]
        self._pair_initial_x_center = [(legs[i].x + legs[i+1].x)/2.0 for i in range(0,12,2)]
        self._pair_initial_y_diff = [legs[i+1].y - legs[i].y for i in range(0,12,2)]
        self._upper_band_avg_y0 = sum(legs[i].y for i in self.upper_leg_indices)/6.0

        self.center_indices = list(self.estimator.center_idxs)  # 通常 [4,5,6,7]

        self._emergency = False
        
        # 初始化时设置合理的目标中心Z，避免第一次调用时步长过大
        try:
            current_center_z = self._get_initial_center_z()
            self._target_center_z = current_center_z  # 初始目标等于当前值
        except Exception:
            self._target_center_z = 600.0  # 默认值
            
        self.logger.info(f"控制系统初始化完成：simulate_feedback={self.simulate_feedback}")

    # ===== 外部接口 =====
    def start_loop(self, period_ms: int = 100):
        self._emergency = False                         # 关键：允许从急停/停止恢复
        self.period_s = max(0.03, period_ms/1000.0)
        self._loop_stop.clear()
        self._last_ts = time.time()
        if self._loop_thread and self._loop_thread.is_alive():
            self.logger.warn("循环已在运行中"); return
        self._loop_thread = threading.Thread(target=self._loop, daemon=True, name="ctrl_loop")
        self.logger.debug(f"ControlSystem.start_loop: thread start, period={self.period_s}s")
        self._loop_thread.start()
        self.logger.info(f"控制循环启动，周期 {self.period_s*1000:.0f} ms")

    def stop_loop(self):
        self._loop_stop.set()
        if self._loop_thread: self._loop_thread.join(timeout=2.0)
        self._loop_thread = None                        # 关键：清理句柄，便于再次启动
        self.logger.info("控制循环已停止")

    def emergency_stop(self):
        self._emergency = True
        try:
            if hasattr(self.driver, "stop_all"): self.driver.stop_all()
        except Exception as e:
            self.logger.exception(e, "急停 stop_all 失败")
        self.logger.error("⚠️ 收到急停信号，已停止所有动作")

    def set_center_rate(self, rate_mm_s: float):
        global CENTER_Z_RATE_MM_S
        CENTER_Z_RATE_MM_S = max(0.0, float(rate_mm_s))
        self.logger.info(f"设置中心下降速率：{CENTER_Z_RATE_MM_S:.1f} mm/s")

    # ===== 主循环 =====
    def _loop(self):
        self.logger.debug("ControlSystem._loop: thread started")
        while not self._loop_stop.is_set():
            try:
                self.tick_once()
            except Exception as e:
                self.logger.exception(e, "tick 异常")
            time.sleep(self.period_s)
        self.logger.debug("ControlSystem._loop: thread stopped")

    def tick_once(self):
        self.logger.debug("tick_once: BEGIN")
        if self._emergency:
            self.logger.warn("tick_once: emergency, skip")
            return

        now = time.time()
        dt = self.period_s if self._last_ts is None else max(1e-3, now-self._last_ts)
        self._last_ts = now

        # (1) 传感器融合
        if self.sensor:
            self.logger.debug("tick_once: sensor.refresh_once")
            self.sensor.refresh_once()

        state = self.estimator.estimate(self.legs, self.sensor)
        self.logger.debug(f"tick_once: center_z={state.center_z:.2f}")

        # (2) 计划中心下降量（受步长约束）
        planned_center_delta = min(CENTER_Z_RATE_MM_S * dt, MAX_STEP_Z_MM)
        self._target_center_z = max(0.0, state.center_z - planned_center_delta)
        self.logger.debug(f"tick_once: target_center_z={self._target_center_z:.2f} (Δ={planned_center_delta:.2f})")

        # (3) 规划 Δz（含中心约束 + 只加不减）
        dz_plan = self._plan_dz_per_leg(state, planned_center_delta)

        # (4) 规划 Δx/Δy
        dx_plan, dy_plan = self._plan_dxy_per_leg(state)

        # (5) 下发命令
        cmds = [{"id": l.id, "dz": dz_plan[i], "dx": dx_plan[i], "dy": dy_plan[i]} for i,l in enumerate(self.legs)]
        self._apply_cmds(cmds)

        # (6) UI
        if self.update_ui:
            self.update_ui(f"周期闭环：目标中心Z={self._target_center_z:.0f}mm", "运行中")
        self.logger.debug("tick_once: END")

    # ===== Δz：中心约束 + 调平只“多降不回拉” =====
    def _plan_dz_per_leg(self, state, planned_center_delta: float) -> List[float]:
        n = len(self.legs)
        dz = [0.0]*n

        # 1) 基础：全腿同降 base，增加合理的单次步长限制
        # 限制单次下降不超过 5mm，避免一次性下降过多
        MAX_SINGLE_STEP = 5.0  # mm
        base = self._clip(planned_center_delta, 0.0, min(MAX_STEP_Z_MM, MAX_SINGLE_STEP))
        for i in range(n):
            dz[i] = base

        # 2) 调平：角点偏高(>0)才“多降”，永不“上提”（避免出现负Δz）
        id2idx = {leg.id:i for i,leg in enumerate(self.legs)}
        for lid, dz_rel in state.corner_dz.items():
            if dz_rel <= 0:        # 角点偏低，不做回拉
                continue
            idx = id2idx.get(lid, None)
            if idx is None: 
                continue
            add = self._clip(dz_rel * LEVELING_GAIN, 0.0, MAX_STEP_Z_MM - dz[idx])
            dz[idx] += add

        # 3) 中心约束：保证中心腿平均 Δz ≈ planned_center_delta（只做“加法校正”）
        cidx = self.center_indices
        current_avg = sum(dz[i] for i in cidx) / len(cidx)
        need = planned_center_delta - current_avg
        if need > 0:
            per = self._clip(need, 0.0, MAX_STEP_Z_MM)  # 均分校正，这里简单处理：每条加同额
            for i in cidx:
                room = MAX_STEP_Z_MM - dz[i]
                dz[i] += min(per, room)

        # 4) 统一保证非负
        dz = [max(0.0, v) for v in dz]
        return dz

    # ===== Δx/Δy（与之前一致，略清理） =====
    def _plan_dxy_per_leg(self, state) -> Tuple[List[float], List[float]]:
        n = len(self.legs)
        dx = [0.0]*n; dy = [0.0]*n

        shift_x = self._clip(-state.center_x*CENTER_GAIN_XY, -MAX_STEP_XY_MM, MAX_STEP_XY_MM)
        shift_y = self._clip(-state.center_y*CENTER_GAIN_XY, -MAX_STEP_XY_MM, MAX_STEP_XY_MM)

        upper_avg_y = sum(self.legs[i].y for i in self.upper_leg_indices)/len(self.upper_leg_indices)
        band_shift = self._clip((self._upper_band_avg_y0 - upper_avg_y)*0.05, -MAX_STEP_XY_MM, MAX_STEP_XY_MM)

        for i in range(n):
            dx[i] += shift_x
            dy[i] += shift_y
        for idx in self.upper_leg_indices:
            dy[idx] += band_shift

        # 成对约束
        for k in range(6):
            up = self.upper_leg_indices[k]; lo = self.lower_leg_indices[k]
            # Y 差保持：只调整下排，避免破坏上排一致性
            desired_lo_y = (self.legs[up].y + dy[up]) - self._pair_initial_y_diff[k]
            dy[lo] += self._clip(desired_lo_y - self.legs[lo].y, -MAX_STEP_XY_MM, MAX_STEP_XY_MM)

            # X 对齐：锁定对中线，带极小抖动
            x_center = self._pair_initial_x_center[k]
            jitter = random.uniform(-PAIR_X_JITTER_MM, PAIR_X_JITTER_MM)*PAIR_CONSTRAINT_WEIGHT
            desired_pair_x = x_center + jitter
            dx[up] += self._clip(desired_pair_x - self.legs[up].x, -MAX_STEP_XY_MM, MAX_STEP_XY_MM)
            dx[lo] += self._clip(desired_pair_x - self.legs[lo].x, -MAX_STEP_XY_MM, MAX_STEP_XY_MM)

        return dx, dy

    # ===== 下发 =====
    def _apply_cmds(self, cmds: List[Dict]):
        self.logger.debug(f"_apply_cmds: count={len(cmds)} driver={type(self.driver).__name__}")

        used = False
        if hasattr(self.driver, "apply_batch"):
            try:
                ok = self.driver.apply_batch(cmds)
                self.logger.debug(f"_apply_cmds: driver.apply_batch -> {ok}")
                used = True
            except Exception as e:
                self.logger.exception(e, "驱动 apply_batch 失败")

        if not used and hasattr(self.driver, "move_leg_delta"):
            for c in cmds:
                try:
                    self.driver.move_leg_delta(c["id"], c["dz"], c["dx"], c["dy"])
                except Exception as e:
                    self.logger.exception(e, f"driver.move_leg_delta 失败 leg={c['id']}")

        # 仅 mock 演示时“本地回写”
        if self.simulate_feedback:
            for c in cmds:
                leg = self.legs[c["id"]-1]
                leg.z = max(0.0, leg.z - float(c["dz"]))
                leg.x += float(c["dx"]); leg.y += float(c["dy"])
                leg.force = random.uniform(FORCE_THRESHOLD[0]+5, FORCE_THRESHOLD[1]-5)

    # ===== 工具 =====
    def _get_initial_center_z(self) -> float:
        try:
            st = self.estimator.estimate(self.legs, self.sensor)
            return st.center_z
        except Exception:
            return sum(l.z for l in self.legs)/max(1,len(self.legs))

    @staticmethod
    def _clip(v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))

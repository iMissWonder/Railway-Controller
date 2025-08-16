# core/center_estimator.py
# 估计几何中心/四角相对高差/受力越限等状态；含EMA与离群剔除
from dataclasses import dataclass
from typing import Tuple, List, Dict, Optional

@dataclass
class EstimationState:
    center_x: float
    center_y: float
    center_z: float
    corner_dz: Dict[int, float]          # {leg_id: leg.z - center_z}
    attitude_outliers: List[int]         # 超出阈值的角点 leg_id 列表
    force_abnormal: bool                 # 是否存在受力越限
    forces: List[float]                  # 回传12腿受力（如可得）

class CenterEstimator:
    """
    规则：
      - 几何中心Z：默认取 legs[4..7]（腿子5、6、7、8）平均；若传入 sensor，可优先使用 sensor.estimate_center()
      - EMA平滑：alpha ∈ (0,1)，默认0.35
      - 离群剔除：abs(测点-均值) > outlier_mm 将被剔除后重算
      - 四角相对值：取 [1,2,11,12]（索引0,1,10,11）各自 z - center_z
      - 力判定：超出 force_threshold=(low, high) 认为受力异常
    """
    def __init__(self,
                 center_indices: Tuple[int, int, int, int] = (4, 5, 6, 7),
                 corner_indices: Tuple[int, int, int, int] = (0, 1, 10, 11),
                 ema_alpha: float = 0.35,
                 outlier_mm: float = 30.0,
                 force_threshold: Tuple[float, float] = (80.0, 120.0),
                 attitude_limit_mm: float = 20.0,
                 logger=None):
        self.center_idxs = center_indices
        self.corner_idxs = corner_indices
        self.alpha = float(ema_alpha)
        self.outlier_mm = float(outlier_mm)
        self.force_lo, self.force_hi = map(float, force_threshold)
        self.att_limit = float(attitude_limit_mm)
        self._ema_z: Optional[float] = None
        self.logger = logger

    def _ema(self, prev: Optional[float], val: float) -> float:
        if prev is None: return val
        return self.alpha * val + (1.0 - self.alpha) * prev

    def estimate(self, legs: List, sensor_system=None) -> EstimationState:
        # 1) 取原始数据
        z_vals = [getattr(l, "z", 0.0) for l in legs]
        forces = [float(getattr(l, "force", 0.0)) for l in legs]

        # 如有传感器系统，优先融合后的中心Z
        if sensor_system is not None:
            try:
                cx_s, cy_s, cz_s = sensor_system.estimate_center()
            except Exception:
                cx_s = cy_s = 0.0
                cz_s = None
        else:
            cx_s = cy_s = 0.0
            cz_s = None

        # 2) 计算中心Z（若无传感器中心，基于 legs[4..7] 并做离群剔除）
        if cz_s is None:
            cidx = self.center_idxs
            samples = [z_vals[i] for i in cidx]
            mean0 = sum(samples) / max(1, len(samples))
            inliers = [v for v in samples if abs(v - mean0) <= self.outlier_mm]
            cz_raw = (sum(inliers) / len(inliers)) if inliers else mean0
        else:
            cz_raw = float(cz_s)

        cz = self._ema(self._ema_z, cz_raw)
        self._ema_z = cz

        # 3) 中心X/Y（暂留：有需要可接全站仪/激光）
        cx = float(cx_s) if sensor_system is not None else 0.0
        cy = float(cy_s) if sensor_system is not None else 0.0

        # 4) 四角相对高度 & 越限
        corner_dz: Dict[int, float] = {}
        attitude_outliers: List[int] = []
        for idx in self.corner_idxs:
            leg_id = getattr(legs[idx], "id", idx + 1)
            dz = z_vals[idx] - cz
            corner_dz[leg_id] = dz
            if abs(dz) > self.att_limit:
                attitude_outliers.append(leg_id)

        # 5) 受力异常：任一腿越界即 True；如传感器系统提供 forces 列表可覆盖
        if sensor_system is not None:
            try:
                forces = sensor_system.latest_forces()
            except Exception:
                pass
        force_abnormal = any((f < self.force_lo or f > self.force_hi) for f in forces if f is not None)

        return EstimationState(
            center_x=cx,
            center_y=cy,
            center_z=cz,
            corner_dz=corner_dz,
            attitude_outliers=attitude_outliers,
            force_abnormal=force_abnormal,
            forces=forces
        )

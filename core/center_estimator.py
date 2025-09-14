# core/center_estimator.py
# 估计几何中心/四角相对高差/受力越限等状态；含EMA与离群剔除
from dataclasses import dataclass
from typing import Tuple, List, Dict, Optional

# 引入几何计算模块
from core.geometry import compute_center_and_theory, SensorSnapshot

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
      - 几何中心：使用 geometry.py 中的精确计算
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
        self._ema_x: Optional[float] = None
        self._ema_y: Optional[float] = None
        self.logger = logger

    def _ema(self, prev: Optional[float], val: float) -> float:
        if prev is None: return val
        return self.alpha * val + (1.0 - self.alpha) * prev

    def _create_sensor_snapshot(self, legs: List, sensor_system=None) -> SensorSnapshot:
        """创建传感器快照，用于几何计算"""
        y_meas = {}
        z_meas = {}
        x_meas = {}
        force_meas = {}
        healthy = {}
        
        for i, leg in enumerate(legs):
            leg_id = getattr(leg, "id", i + 1)
            y_meas[leg_id] = getattr(leg, "y", 0.0)
            z_meas[leg_id] = getattr(leg, "z", 0.0)
            x_meas[leg_id] = getattr(leg, "x", 0.0)
            force_meas[leg_id] = getattr(leg, "force", 0.0)
            healthy[leg_id] = True  # 简化处理，可扩展健康状态判断
            
        return SensorSnapshot(
            y_meas=y_meas,
            z_meas=z_meas,
            x_meas=x_meas,
            force=force_meas,
            healthy=healthy
        )

    def estimate(self, legs: List, sensor_system=None) -> EstimationState:
        # 1) 创建传感器快照
        snap = self._create_sensor_snapshot(legs, sensor_system)
        
        # 2) 使用几何模块计算精确的几何中心
        try:
            geo_result = compute_center_and_theory(snap)
            cx_raw = geo_result.Xc  # 几何中心X
            cz_raw = geo_result.Zc  # 几何中心Z
            
            # 计算几何中心Y（只使用腿对(1,2)）
            cy_raw = 0.0
            if 1 in snap.y_meas and 2 in snap.y_meas:
                cy_raw = (snap.y_meas[1] + snap.y_meas[2]) / 2.0
            else:
                # 如果腿对(1,2)数据不可用，回退到所有腿对平均
                valid_pairs = 0
                for i in range(1, 13, 2):  # 1,3,5,7,9,11号腿（上排）
                    if i in snap.y_meas and (i+1) in snap.y_meas:
                        cy_raw += (snap.y_meas[i] + snap.y_meas[i+1]) / 2.0
                        valid_pairs += 1
                cy_raw = cy_raw / max(1, valid_pairs)
            
            if self.logger:
                self.logger.debug(f"几何计算结果: Xc={cx_raw:.2f}, Zc={cz_raw:.2f}, Yc={cy_raw:.2f}")
                
        except Exception as e:
            if self.logger:
                self.logger.warning(f"几何计算失败，使用备用方案: {e}")
            # 备用方案：使用原有的简化计算
            cx_raw = 0.0
            cy_raw = 0.0
            z_vals = [getattr(l, "z", 0.0) for l in legs]
            cidx = self.center_idxs
            samples = [z_vals[i] for i in cidx]
            mean0 = sum(samples) / max(1, len(samples))
            inliers = [v for v in samples if abs(v - mean0) <= self.outlier_mm]
            cz_raw = (sum(inliers) / len(inliers)) if inliers else mean0

        # 3) EMA平滑处理
        cx = self._ema(self._ema_x, cx_raw)
        cy = self._ema(self._ema_y, cy_raw)
        cz = self._ema(self._ema_z, cz_raw)
        
        self._ema_x = cx
        self._ema_y = cy
        self._ema_z = cz

        # 4) 四角相对高度 & 越限检测
        z_vals = [getattr(l, "z", 0.0) for l in legs]
        corner_dz: Dict[int, float] = {}
        attitude_outliers: List[int] = []
        for idx in self.corner_idxs:
            leg_id = getattr(legs[idx], "id", idx + 1)
            dz = z_vals[idx] - cz
            corner_dz[leg_id] = dz
            if abs(dz) > self.att_limit:
                attitude_outliers.append(leg_id)

        # 5) 受力异常检测
        forces = [float(getattr(l, "force", 0.0)) for l in legs]
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

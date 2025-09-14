# core/geometry.py
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

LegId = int  # 1..12

@dataclass
class SensorSnapshot:
    """单周期原始数据（由 SensorSystem 整理好传入）"""
    y_meas: Dict[LegId, float]     # 每腿 Y 实测（mm 或 m，与你全局单位一致）
    z_meas: Dict[LegId, float]     # 每腿 Z 实测
    x_meas: Dict[LegId, float]     # 每腿 X 实测（由 SensorSystem 传入）
    force:  Dict[LegId, float]     # 受力，可用于权重
    healthy: Dict[LegId, bool]     # 该腿本周期数据是否可信（CRC/范围/突变等已校验）

# 硬编码的腿子配置
LEG_TAN_VALUES = {
    1: 0.0744, 2: 0.0757, 3: 0.1301, 4: 0.1484,
    5: 0.4885, 6: 0.0685, 7: 0.2785, 8: 0.4514,
    9: 0.1084, 10: 0.2255, 11: 0.0673, 12: 0.1789,
    13: 0.0227, 14: 0.0913  # 额外传感器位置，暂时不用
}

# 对称腿对配置（用于计算几何中心）
CENTER_PAIRS = [(1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 12)]

# 中心高程计算用的腿子编号
Z_CENTER_LEGS = [5, 6, 7, 8]

# 左右符号配置（奇数腿为上排+1，偶数腿为下排-1）
SIDE_SIGN = {
    1: 1, 2: -1, 3: 1, 4: -1, 5: 1, 6: -1,
    7: 1, 8: -1, 9: 1, 10: -1, 11: 1, 12: -1
}

@dataclass
class GeometryResult:
    Xc: float                               # 几何中心（相对"①为原点"的 X 偏移）
    Zc: float                               # 中心高程
    y_theo: Dict[LegId, float]              # 每腿理论 Y
    e_y: Dict[LegId, float]                 # 每腿平面偏差 e_yi = y_meas - y_theo
    pair_details: List[Tuple[Tuple[LegId,LegId], float, float]]  
    # [( (i,j), Xc_ij, weight_ij ), ...] 便于日志/诊断

def _pair_weight(i: LegId, j: LegId, snap: SensorSnapshot) -> float:
    """对某一对腿的置信权重：特殊配置让腿对(1,2)权重最高，其他为0"""
    if not (snap.healthy.get(i, False) and snap.healthy.get(j, False)):
        return 0.0
    
    # 特殊权重配置：只有腿对(1,2)有权重，其他腿对权重为0
    if (i == 1 and j == 2) or (i == 2 and j == 1):
        return 1.0  # 腿对(1,2)的权重最高
    else:
        return 0.0  # 其他腿对权重为0

def compute_geometric_center_Xc(snap: SensorSnapshot) -> Tuple[float, List[Tuple[Tuple[LegId,LegId], float, float]]]:
    """
    用多对对称腿联合估计几何中心 Xc。
    对每一对 (i,j)：Δy = y_j - y_i，tan_ij = (tan_i + tan_j)/2，Xc_ij = (Δy/2)/tan_ij
    再按权重求加权平均。
    """
    numers, denoms = 0.0, 0.0
    details = []
    for (i, j) in CENTER_PAIRS:
        yi, yj = snap.y_meas.get(i), snap.y_meas.get(j)
        tani, tanj = LEG_TAN_VALUES.get(i), LEG_TAN_VALUES.get(j)
        if yi is None or yj is None or tani is None or tanj is None:
            continue
        tan_ij = (tani + tanj) / 2.0
        if abs(tan_ij) < 1e-9:
            continue
        dy = (yj - yi)
        Xc_ij = (dy / 2.0) / tan_ij
        w = _pair_weight(i, j, snap)
        details.append(((i, j), Xc_ij, w))
        numers += Xc_ij * w
        denoms += w
    Xc = numers / denoms if denoms > 0 else 0.0
    return Xc, details

def compute_center_Zc(snap: SensorSnapshot) -> float:
    """中心高程，默认取 5~8 号腿平均；可按需改成加权平均。"""
    vals = [snap.z_meas[k] for k in Z_CENTER_LEGS if k in snap.z_meas]
    return sum(vals)/len(vals) if vals else 0.0

def compute_theoretical_Y(Xc: float, snap: SensorSnapshot) -> Dict[LegId, float]:
    """
    y_i_theo = s_i * tan_i * (x_i - Xc)
    """
    y_theo = {}
    for i in range(1, 13):  # 腿子编号 1-12
        xi = snap.x_meas.get(i)
        tan_i = LEG_TAN_VALUES.get(i)
        s_i = SIDE_SIGN.get(i, 0)
        if xi is None or tan_i is None or s_i == 0:
            continue
        y_theo[i] = s_i * tan_i * (xi - Xc)
    return y_theo

def compute_center_and_theory(snap: SensorSnapshot) -> GeometryResult:
    Xc, details = compute_geometric_center_Xc(snap)
    Zc = compute_center_Zc(snap)
    y_theo = compute_theoretical_Y(Xc, snap)
    e_y = {}
    for i, yth in y_theo.items():
        ym = snap.y_meas.get(i)
        if ym is not None:
            e_y[i] = ym - yth
    return GeometryResult(Xc=Xc, Zc=Zc, y_theo=y_theo, e_y=e_y, pair_details=details)

# Railway-Controller

道岔腿子控制系统 - 一个基于多传感器融合的高精度12腿道岔控制系统

## 📋 项目概述

本项目是一个道岔腿子控制系统，用于控制12个腿子的协同运动，实现道岔的精确定位和调平。系统采用闭环控制算法，通过传感器反馈实现高精度的几何中心控制和姿态调平。

### 主要特性
- ✅ **12腿协同控制** - 支持12个腿子的独立运动控制
- ✅ **几何中心计算** - 基于对称腿对的精确几何中心算法
- ✅ **实时传感器融合** - 集成多种传感器数据（位置、力、姿态）
- ✅ **可视化GUI界面** - 实时显示腿子状态和控制参数
- ✅ **闭环控制算法** - PID控制 + 约束优化
- ✅ **安全保护机制** - 紧急停止、限位保护、异常检测

## 🏗️ 项目结构

```
Railway-Controller/
├── core/                     # 🔥 核心算法模块
│   ├── control_system.py     # 主控制算法（核心流程）
│   ├── geometry.py          # 几何中心计算算法
│   ├── center_estimator.py  # 中心估计与状态融合
│   ├── sensor_system.py     # 传感器数据融合
│   ├── leg_unit.py          # 腿子单元模型
│   └── logger.py            # 日志系统
├── gui/                      # 图形用户界面
│   └── interface.py         # GUI主界面
├── hardware/                 # 硬件驱动层
│   ├── driver_interface.py  # 驱动抽象接口
│   ├── mock_driver.py       # 模拟驱动（调试用）
│   └── mock_serial_device.py # 模拟串口设备
├── controller/               # 系统控制器
│   └── main_controller.py   # 主控制器（整合各模块）
├── comm/                     # 🚧 串口通信模块（暂未使用）
│   ├── service.py           # 通信服务
│   ├── framer.py            # 数据帧处理
│   └── protocol.py          # 通信协议
├── comm_test/               # 🚧 通信测试工具（暂未使用）
│   ├── sim_device.py        # 设备模拟器
│   └── demo_use_comm.py     # 通信演示
└── main.py                  # 🚀 程序入口点
```

## 🔥 核心算法流程

### 主控制循环 (`core/control_system.py`)

系统的核心算法位于 `core/control_system.py` 的 `tick_once()` 方法中：

```python
def tick_once(self):
    # 1️⃣ 传感器数据刷新
    self.sensor.refresh_once()
    
    # 2️⃣ 状态估计（几何中心、姿态偏差）
    state = self.estimator.estimate(self.legs, self.sensor)
    
    # 3️⃣ 运动规划
    planned_dz = self._rate_mm_s * dt  # Z轴下降量
    dz_per_leg = self._plan_dz_per_leg(state, planned_dz)  # Z轴分解
    dx_per_leg, dy_per_leg = self._plan_dxy_per_leg(state)  # XY轴分解
    
    # 4️⃣ 指令下发
    cmds = [{"id": i+1, "dx": dx[i], "dy": dy[i], "dz": dz[i]} 
            for i in range(12)]
    self._apply_cmds(cmds)
```

### 几何中心计算 (`core/geometry.py`)

基于6对对称腿子计算几何中心：

```python
# 对称腿对配置
CENTER_PAIRS = [(1,2), (3,4), (5,6), (7,8), (9,10), (11,12)]

# 几何中心计算公式
for (i, j) in CENTER_PAIRS:
    Δy = y_j - y_i
    tan_avg = (tan_i + tan_j) / 2
    Xc_ij = (Δy / 2) / tan_avg
    
# 加权平均得到最终几何中心
Xc = Σ(Xc_ij * weight_ij) / Σ(weight_ij)
```

### 运动分解算法

#### Z轴控制 (`_plan_dz_per_leg`)
1. **统一下降** - 所有腿子按目标速率下降
2. **调平修正** - 偏高的角点腿子额外下降
3. **中心约束** - 确保中心腿子平均下降量符合预期

#### XY轴控制 (`_plan_dxy_per_leg`)
1. **中心校正** - 将当前几何中心拉向固定理论中心
2. **上排一致性** - 维护上排6个腿子的Y向一致
3. **成对约束** - 保持对称腿对的几何关系

## 🚀 快速启动

### 安装依赖
```bash
pip install tkinter matplotlib numpy threading
```

### 运行系统
```bash
python main.py
```

### 命令行参数
```bash
python main.py --help

可选参数：
  --driver {mock,serial}     驱动模式（默认：mock）
  --sensor {mock,serial}     传感器模式（默认：mock）
  --port PORT               串口端口（如：COM3）
  --baud BAUD               波特率（默认：115200）
  --log-level {DEBUG,INFO,WARN,ERROR}  日志级别
```

## 🎛️ GUI界面说明

### 显示区域
- **腿子Z轴高度** - 柱状图显示12个腿子的高度
- **腿子XY坐标分布** - 散点图显示腿子位置和几何中心
- **四角翘曲监测** - 显示角点腿子相对中心的高度偏差
- **受力监测** - 显示各腿子的受力状态

### 控制参数
- **控制周期** - 系统控制循环的执行周期（ms）
- **下降速率** - 中心Z轴下降速度（mm/s）
- **最大步长** - 单次运动的最大步长限制（mm）

### 状态信息
- **目标中心Z** - 控制目标的中心高度
- **当前几何中心** - 实时计算的几何中心位置
- **理论几何中心** - 初始化时固定的理论中心位置

## ⚙️ 核心参数配置

```python
# 控制参数 (core/control_system.py)
MAX_STEP_Z_MM = 10.0        # Z轴最大步长
MAX_STEP_XY_MM = 5.0        # XY轴最大步长
CENTER_Z_RATE_MM_S = 20.0   # 中心下降速率
LEVELING_GAIN = 0.4         # 调平增益
CENTER_GAIN_XY = 0.2        # 中心校正增益

# 传感器参数 (core/sensor_system.py)
fusion_rate_hz = 20.0       # 传感器融合频率

# 估计器参数 (core/center_estimator.py)
ema_alpha = 0.35           # EMA平滑系数
outlier_mm = 30.0          # 离群值阈值
force_threshold = (80, 120) # 受力范围
```

## 🔧 开发说明

### 添加新的控制算法
1. 继承 `ControlSystem` 类
2. 重写 `_plan_dz_per_leg` 或 `_plan_dxy_per_leg` 方法
3. 在 `MainController` 中注册新算法

### 添加新的传感器
1. 实现 `SensorSystem` 接口
2. 重写 `refresh_once()` 和相关数据获取方法
3. 更新传感器配置参数

### 添加新的硬件驱动
1. 继承 `DriverInterface` 类
2. 实现 `move_leg_delta()` 和 `apply_batch()` 方法
3. 在驱动工厂中注册新驱动

## 📊 数据流图

```
传感器数据 → 数据融合 → 状态估计 → 控制算法 → 运动指令 → 硬件驱动
     ↑                    ↓
   硬件反馈 ←── 位置更新 ←── 运动分解
```

## ⚠️ 注意事项

### 当前状态
- ✅ **core/** - 核心算法已完成，系统可正常运行
- ✅ **gui/** - 图形界面已完成，支持实时监控
- ✅ **hardware/** - 模拟硬件已完成，支持调试测试
- 🚧 **comm/** - 串口通信模块已实现但暂未集成到主系统
- 🚧 **comm_test/** - 通信测试工具完整，可独立测试串口功能

### 已知问题
- [ ] 几何中心计算在某些情况下可能出现数值不稳定
- [ ] XY轴控制算法需要进一步调优以减少震荡
- [ ] 串口通信模块需要与主控制系统集成

### 下一步开发
1. 集成串口通信到主控制系统
2. 优化几何中心计算的数值稳定性
3. 添加更多安全保护机制
4. 完善异常处理和错误恢复

## 📝 许可证

本项目仅用于教育和研究目的。

## 🤝 贡献

欢迎提交Issues和Pull Requests来改进项目！

---

**核心算法流程总结：**
- 主控制循环：`core/control_system.py` → `tick_once()`
- 几何计算：`core/geometry.py` → `compute_center_and_theory()`
- 状态估计：`core/center_estimator.py` → `estimate()`
- 运动分解：`core/control_system.py` → `_plan_dz_per_leg()` + `_plan_dxy_per_leg()`

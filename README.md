# Railway-Controller

道岔腿子控制系统 - 一个基于多传感器融合的高精度12腿道岔控制系统

## 📋 项目概述

本项目是一个道岔腿子控制系统，用于控制12个腿子的协同运动，实现道岔的精确定位和调平。系统采用闭环控制算法，通过传感器反馈实现高精度的几何中心控制和姿态调平。

### 主要特性
- ✅ **12腿协同控制** - 支持12个腿子的独立运动控制
- ✅ **单腿精确控制** - 专用单腿控制面板，支持XY平面和Z轴精确调节
- ✅ **GIF动画演示** - 实时动画演示腿子运动过程，直观展示控制效果
- ✅ **几何中心计算** - 基于对称腿对的精确几何中心算法
- ✅ **实时传感器融合** - 集成多种传感器数据（位置、力、姿态）
- ✅ **可视化GUI界面** - 实时显示腿子状态和控制参数，支持全屏模式
- ✅ **闭环控制算法** - PID控制 + 约束优化
- ✅ **安全保护机制** - 紧急停止、限位保护、异常检测
- ✅ **串口通信支持** - 支持真实硬件设备的串口通信

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
├── gui/                      # 🎨 图形用户界面
│   └── gui_controller.py    # GUI主界面与单腿控制面板
├── gif/                      # 🎬 GIF动画资源
│   ├── 1.Z轴降低100mm.gif    # 腿子1运动演示动画
│   ├── 2.Z轴升高50mm.gif     # 腿子2运动演示动画
│   ├── 3.X轴正方向5mm.gif    # 腿子3运动演示动画
│   ├── 4.X轴负方向10mm.gif   # 腿子4运动演示动画
│   ├── 5.Y轴负方向5mm.gif    # 腿子5运动演示动画
│   └── 6.Y轴正方向15mm.gif   # 腿子6运动演示动画
├── hardware/                 # 硬件驱动层
│   ├── actuator_driver.py   # 驱动抽象接口
│   ├── driver_serial.py     # 串口驱动（真实硬件）
│   ├── driver_mock.py       # 模拟驱动（调试用）
│   ├── driver_multi.py      # 多驱动支持
│   ├── mock_serial_device.py # 模拟串口设备
│   └── serial_interface.py  # 串口通信接口
├── core/                     # 系统控制器
│   └── main_controller.py   # 主控制器（整合各模块）
├── comm/                     # 🚧 串口通信模块（暂未使用）
│   ├── service.py           # 通信服务
│   ├── framer.py            # 数据帧处理
│   └── protocol.py          # 通信协议
├── comm_test/               # 🚧 通信测试工具（暂未使用）
│   ├── sim_device.py        # 设备模拟器
│   └── demo_use_comm.py     # 通信演示
├── test_*.py                # 🧪 测试脚本集合
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
# 核心依赖
pip install tkinter matplotlib numpy threading pyserial

# GIF动画支持 (PIL/Pillow)
pip install pillow

# 或使用requirements.txt安装
pip install -r requirements.txt
```

### 模拟模式运行（默认）
```bash
python main.py
```

### 串口模式运行

#### 1. 准备虚拟串口环境
推荐使用 VSPE (Virtual Serial Port Emulator) 创建虚拟串口对：
- **COM1-COM2**: 控制通道串口对
- **COM3-COM4**: 传感器通道串口对

#### 2. 启动模拟硬件设备
```bash
# 启动模拟硬件设备（双口模式）
python -m hardware.mock_serial_device --ctrl-port COM2 --telem-port COM4 --baud 115200 --telem-interval 0.5

# 或单口兼容模式
python -m hardware.mock_serial_device --port COM2 --baud 115200 --telem-interval 0.1
```

#### 3. 启动主控制系统
```bash
# 完整串口模式（推荐）
python main.py --driver serial --port COM1 --sensor serial --sensor-port COM3 --log-level INFO

# 混合模式（仅控制使用串口）
python main.py --driver serial --port COM1 --sensor mock --log-level INFO

# 仅传感器使用串口
python main.py --driver mock --sensor serial --sensor-port COM3 --log-level INFO
```

### 命令行参数
```bash
python main.py --help

可选参数：
  --driver {mock,serial}         驱动模式（默认：mock）
  --sensor {mock,serial}         传感器模式（默认：mock）
  --port PORT                   控制串口端口（如：COM1）
  --baud BAUD                   控制串口波特率（默认：115200）
  --sensor-port SENSOR_PORT     传感器串口端口（如：COM3）
  --sensor-baud SENSOR_BAUD     传感器串口波特率（默认：115200）
  --log-level {DEBUG,INFO,WARN,ERROR}  日志级别（默认：INFO）
```

## 🔌 串口通信说明

### 串口配置
系统支持双通道串口通信：

| 通道 | 功能 | 主控端口 | 设备端口 | 数据流向 |
|------|------|----------|----------|----------|
| 控制通道 | 执行器指令 | COM1 | COM2 | 主控→设备 |
| 传感器通道 | 传感器数据 | COM3 | COM4 | 设备→主控 |

### 通信协议

#### 控制通道协议（二进制帧）
```
帧格式: STX(2B) + LENGTH(1B) + CMD(1B) + PAYLOAD + CRC(2B)
- STX: 0xAA55 (固定帧头)
- 批量控制(0x01): N × (leg_id:1B + dz:2B + dx:2B + dy:2B)
- 单腿控制(0x02): leg_id:1B + dz:2B + dx:2B + dy:2B  
- 急停指令(0x03): 无载荷
- ACK应答(0x81): 状态码
```

#### 传感器通道协议（文本格式）
```
IMU,<roll>,<pitch>,<yaw>          # 姿态数据（弧度）
FOR,<leg_id>,<force>              # 受力数据（牛顿）
Z,<leg_id>,<height>               # Z轴高度（毫米）
XY,<leg_id>,<x>,<y>              # XY坐标（毫米）
```

### 串口测试工具

#### 基础连通性测试
```bash
# 单端口回环测试
python comm_test/single.py

# 双端口对通测试  
python comm_test/dual_test.py

# 搜索可用串口
python comm_test/search_com.py
```

#### 模拟设备测试
```bash
# 启动模拟设备
python comm_test/sim_device.py

# 测试通信服务
python comm_test/demo_use_comm.py
```

## 🎛️ GUI界面说明

### 主界面功能
- **F11全屏模式** - 默认进入全屏，按Esc或F11退出
- **实时数据监控** - 动态显示系统运行状态
- **串口监视器** - 置顶窗口，实时显示通信数据
- **单腿控制面板** - 专用置顶窗口，精确控制单个腿子

### 显示区域
- **腿子Z轴高度** - 柱状图显示12个腿子的高度
- **腿子XY坐标分布** - 散点图显示腿子位置和几何中心
- **四角翘曲监测** - 显示角点腿子相对中心的高度偏差
- **受力监测** - 显示各腿子的受力状态
- **串口监视器** - 实时显示串口收发数据（串口模式）

### 🎮 单腿控制系统

单腿控制系统是本项目的重要特色功能，提供了精确的单腿操作界面和直观的动画演示。

#### 核心特性
- ✅ **精确移动控制** - XY轴±0.1cm，Z轴±1.0cm的精确调节
- ✅ **实时GIF演示** - 选择腿子1-6时显示对应的运动动画
- ✅ **智能播放逻辑** - 每个腿子的动画仅在首次操作时播放
- ✅ **状态实时同步** - 腿子位置和受力信息实时更新
- ✅ **硬件命令集成** - 控制指令同步发送到硬件驱动

#### 界面布局
```
┌─────────────────────────────────────────────────────────────┐
│                     单腿控制 (置顶窗口)                      │
├──────────────────────────┬──────────────────────────────────┤
│     GIF动画演示区         │           控制操作区             │
│   (60%宽度，动态显示)      │         (40%宽度，固定)          │
│                          │                                  │
│  ┌────────────────────┐   │  ┌─────────────────────────────┐ │
│  │                    │   │  │        腿子状态信息         │ │
│  │   腿子运动演示      │   │  │  位置: (X, Y, Z) cm        │ │
│  │   (GIF动画播放)     │   │  │  受力: 0.0 N               │ │
│  │                    │   │  └─────────────────────────────┘ │
│  │                    │   │                                  │
│  │                    │   │  ┌─────────────────────────────┐ │
│  │                    │   │  │      XY轴平面控制           │ │
│  │                    │   │  │        (±0.1cm)             │ │
│  │                    │   │  │      ↑                      │ │
│  │                    │   │  │   ←  腿子X  →                │ │
│  │                    │   │  │      ↓                      │ │
│  │                    │   │  └─────────────────────────────┘ │
│  │                    │   │                                  │
│  │                    │   │  ┌─────────────────────────────┐ │
│  │                    │   │  │      Z轴高度控制             │ │
│  │                    │   │  │   [升高+1cm] [降低-1cm]      │ │
│  └────────────────────┘   │  └─────────────────────────────┘ │
│                          │                                  │
│                          │  ┌─────────────────────────────┐ │
│                          │  │        腿子选择             │ │
│                          │  │  [1][2][3][4][5][6]         │ │
│                          │  │  [7][8][9][10][11][12]      │ │
│                          │  └─────────────────────────────┘ │
└──────────────────────────┴──────────────────────────────────┘
```

#### 🎬 GIF动画系统

**动画资源映射**
- 腿子1 → `1.Z轴降低100mm.gif` - Z轴下降动作演示
- 腿子2 → `2.Z轴升高50mm.gif` - Z轴上升动作演示  
- 腿子3 → `3.X轴正方向5mm.gif` - X轴正向移动演示
- 腿子4 → `4.X轴负方向10mm.gif` - X轴负向移动演示
- 腿子5 → `5.Y轴负方向5mm.gif` - Y轴负向移动演示
- 腿子6 → `6.Y轴正方向15mm.gif` - Y轴正向移动演示

**播放特性**
- 🎯 **按需加载** - GIF帧仅在首次使用时加载并缓存
- 🖼️ **保持比例** - 自动等比例缩放，避免图像拉伸变形
- ⏱️ **缓慢播放** - 200ms/帧的播放速度，便于观察细节
- 🔄 **智能状态** - 每个腿子仅在第一次操作时播放动画
- 🎬 **预览显示** - 选择腿子时立即显示第一帧预览

**使用流程**
1. **进入控制面板** → 默认显示腿子1的GIF第一帧
2. **选择其他腿子** → 立即切换到对应GIF的第一帧，播放状态重置
3. **首次点击移动** → 播放完整动画演示，展示运动效果
4. **后续点击移动** → 执行实际控制，但不重复播放动画
5. **切换腿子** → 新腿子可重新播放动画演示

#### 技术实现
```python
# 核心播放逻辑
def _move_leg(self, direction):
    # 执行实际移动控制
    leg.x += step  # 更新坐标
    self.controller.driver.move_leg_delta(leg_num, dx, dy, dz)
    
    # GIF动画控制（仅首次播放）
    if self.selected_leg_index < 6 and not self.gif_has_played:
        self._start_gif_animation(self.selected_leg_index)
        self.gif_has_played = True

# 腿子切换时重置播放状态
def _select_leg(self, leg_index):
    self.gif_has_played = False  # 重置播放状态
    self._show_gif_first_frame(leg_index)  # 显示第一帧
```

### 控制参数
- **控制周期** - 系统控制循环的执行周期（ms）
- **下降速率** - 中心Z轴下降速度（mm/s）
- **最大步长** - 单次运动的最大步长限制（mm）

### 状态信息
- **目标中心Z** - 控制目标的中心高度
- **当前几何中心** - 实时计算的几何中心位置
- **理论几何中心** - 初始化时固定的理论中心位置
- **连接状态** - 显示串口连接状态（串口模式）

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

# 串口参数
baudrate = 115200          # 串口波特率
timeout = 0.05             # 串口超时时间
retry = 1                  # 重试次数
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
1. 继承 [`ActuatorDriver`](hardware/actuator_driver.py) 抽象类
2. 实现 [`move_leg_delta()`](hardware/actuator_driver.py) 和 [`apply_batch()`](hardware/actuator_driver.py) 方法
3. 在 [`build_driver()`](hardware/actuator_driver.py) 工厂方法中注册新驱动

### 串口驱动开发
参考 [`DriverSerial`](hardware/driver_serial.py) 实现：
1. 使用 [`SerialInterface`](hardware/serial_interface.py) 进行底层通信
2. 实现帧封装和CRC校验
3. 处理ACK应答和重试机制

## 📊 数据流图

```
传感器数据 → 数据融合 → 状态估计 → 控制算法 → 运动指令 → 硬件驱动
     ↑                    ↓
   硬件反馈 ←── 位置更新 ←── 运动分解
     ↑                    ↓
   串口接收 ←── 数据帧 ←─── 串口发送
```

## ⚠️ 注意事项

### 当前状态
- ✅ **core/** - 核心算法已完成，系统可正常运行
- ✅ **gui/** - 图形界面已完成，支持全屏模式和单腿控制面板
- ✅ **gif/** - GIF动画系统已集成，支持智能播放逻辑
- ✅ **hardware/** - 模拟硬件和串口驱动已完成，支持真实设备
- ✅ **串口通信** - 双通道串口通信已集成到主系统
- ✅ **单腿控制** - 精确控制系统已完成，支持XY±0.1cm，Z±1.0cm调节
- ✅ **动画演示** - 6个腿子的GIF运动演示已集成，支持首次播放逻辑
- 🚧 **comm/** - 高级通信模块已实现但暂未集成（可独立使用）

### 串口使用建议
1. **虚拟串口**: 推荐使用VSPE创建COM1-COM4，配置为COM1-COM2和COM3-COM4两对
2. **端口权限**: 确保串口端口未被其他程序占用
3. **波特率**: 建议使用115200，确保控制和传感器通道波特率一致
4. **超时设置**: 默认超时为50ms，可根据实际硬件调整

### 已知问题
- [ ] 几何中心计算在某些情况下可能出现数值不稳定
- [ ] XY轴控制算法需要进一步调优以减少震荡
- [x] ~~串口通信模块需要与主控制系统集成~~ (已完成)
- [x] ~~单腿控制系统需要实现~~ (已完成)
- [x] ~~GIF动画演示功能需要添加~~ (已完成)

### 下一步开发
1. ~~集成串口通信到主控制系统~~ (已完成)
2. ~~实现单腿精确控制功能~~ (已完成)  
3. ~~添加GIF动画演示系统~~ (已完成)
4. 优化几何中心计算的数值稳定性
5. 添加更多安全保护机制
6. 完善异常处理和错误恢复
7. 支持多端口驱动器配置
8. 添加腿子7-12的GIF动画资源
9. 实现控制历史记录和回放功能

## 📝 许可证

本项目仅用于教育和研究目的。

## 🤝 贡献

欢迎提交Issues和Pull Requests来改进项目！

---

**核心算法流程总结：**
- 主控制循环：[`core/control_system.py`](core/control_system.py) → `tick_once()`
- 几何计算：[`core/geometry.py`](core/geometry.py) → `compute_center_and_theory()`
- 状态估计：[`core/center_estimator.py`](core/center_estimator.py) → `estimate()`
- 运动分解：[`core/control_system.py`](core/control_system.py) → `_plan_dz_per_leg()` + `_plan_dxy_per_leg()`
- 单腿控制：[`gui/gui_controller.py`](gui/gui_controller.py) → `_move_leg()` + `_start_gif_animation()`
- GIF动画系统：[`gui/gui_controller.py`](gui/gui_controller.py) → `_load_gif_frames()` + `_animate_gif()`
- 串口驱动：[`hardware/driver_serial.py`](hardware/driver_serial.py) → [`DriverSerial`](hardware/driver_serial.py)
- 模拟设备：[`hardware/mock_serial_device.py`](hardware/mock_serial_device.py) → [`MockSerialDevice`](hardware/mock_serial_device.py)

**🎮 快速体验单腿控制：**
1. 运行 `python main.py` 启动系统
2. 按F11进入全屏模式
3. 点击"单腿控制"按钮打开控制面板
4. 选择腿子1-6中任意一个，观察GIF第一帧预览
5. 点击移动按钮，观看完整运动动画演示
6. 继续点击移动按钮，验证动画不会重复播放
7. 切换到其他腿子，体验不同的运动动画

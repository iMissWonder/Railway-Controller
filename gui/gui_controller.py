# gui_controller.py
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import threading
import subprocess
import sys
import os

matplotlib.rcParams['font.sans-serif'] = ['SimHei']
matplotlib.rcParams['axes.unicode_minus'] = False

DRAIN_INTERVAL_MS = 50  # 日志队列刷新周期

class GUIController:
    def __init__(self, parent, controller):
        self.parent = parent  # 可滚动的Frame
        self.root = parent.winfo_toplevel()  # 获取顶层窗口
        self.controller = controller
        self.logger = controller.logger
        self.legs = controller.get_leg_data()
        
        # 串口监视器窗口引用
        self.serial_monitor_window = None
        
        # 模拟硬件进程引用
        self.mock_device_process = None
        
        # 单腿控制相关变量
        self.single_leg_window = None
        self.selected_leg_index = 0  # 默认选择腿子1（索引0）
        self.leg_colors = ['red'] * 12  # 所有腿子初始为红色
        
        # 受力模拟相关变量
        import time
        self.force_simulation_active = False
        self.force_start_time = 0.0
        self.force_base_values = [0.0] * 12  # 基础受力值
        self.force_target_values = [0.0] * 12  # 目标受力值
        self.force_current_values = [0.0] * 12  # 当前受力值

        self.root.title("道岔腿子控制系统")

        # 顶部状态显示区域
        top = tk.Frame(self.parent); top.pack(fill=tk.X, pady=4)
        self.status_label = tk.Label(top, text="运行状态：初始化完成", font=("黑体", 14))
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # 中心信息显示（合并所有中心信息）
        self.center_info_label = tk.Label(top, text="目标中心Z：-  实际中心：-  几何中心：-", font=("宋体", 20))
        self.center_info_label.pack(side=tk.RIGHT, padx=10)

        # 模拟硬件控制区域
        hardware_frame = tk.Frame(self.parent)
        hardware_frame.pack(fill=tk.X, pady=4)
        
        # 左侧：模拟硬件端口配置
        port_config_frame = tk.Frame(hardware_frame)
        port_config_frame.pack(side=tk.LEFT, padx=10)
        
        tk.Label(port_config_frame, text="模拟硬件端口配置:", font=("黑体", 14)).pack(anchor="w")
        
        port_input_frame = tk.Frame(port_config_frame)
        port_input_frame.pack(anchor="w")
        
        tk.Label(port_input_frame, text="控制口:", font=("宋体", 13)).pack(side=tk.LEFT)
        self.mock_ctrl_port_var = tk.StringVar(value="COM2")
        tk.Entry(port_input_frame, textvariable=self.mock_ctrl_port_var, width=8, font=("宋体", 12)).pack(side=tk.LEFT, padx=(2,8))
        
        tk.Label(port_input_frame, text="遥测口:", font=("宋体", 13)).pack(side=tk.LEFT)
        self.mock_telem_port_var = tk.StringVar(value="COM4")
        tk.Entry(port_input_frame, textvariable=self.mock_telem_port_var, width=8, font=("宋体", 12)).pack(side=tk.LEFT, padx=(2,8))

        # XY扰动配置
        disturbance_frame = tk.Frame(port_config_frame)
        disturbance_frame.pack(anchor="w", pady=(5,0))
        
        self.disturbance_enabled_var = tk.BooleanVar(value=True)
        tk.Checkbutton(disturbance_frame, text="启用XY扰动", variable=self.disturbance_enabled_var, font=("宋体", 12)).pack(side=tk.LEFT)
        
        tk.Label(disturbance_frame, text="幅度:", font=("宋体", 12)).pack(side=tk.LEFT, padx=(10,2))
        self.disturbance_amplitude_var = tk.DoubleVar(value=0.1)
        tk.Entry(disturbance_frame, textvariable=self.disturbance_amplitude_var, width=4, font=("宋体", 12)).pack(side=tk.LEFT, padx=(0,2))
        tk.Label(disturbance_frame, text="cm", font=("宋体", 12)).pack(side=tk.LEFT, padx=(0,8))
        
        tk.Label(disturbance_frame, text="频率:", font=("宋体", 12)).pack(side=tk.LEFT)
        self.disturbance_frequency_var = tk.DoubleVar(value=0.3)
        tk.Entry(disturbance_frame, textvariable=self.disturbance_frequency_var, width=4, font=("宋体", 12)).pack(side=tk.LEFT, padx=(2,2))
        tk.Label(disturbance_frame, text="Hz", font=("宋体", 12)).pack(side=tk.LEFT)
        
        # 右侧：模拟硬件控制按钮
        hardware_buttons_frame = tk.Frame(hardware_frame)
        hardware_buttons_frame.pack(side=tk.LEFT, padx=20)
        
        # 配置按钮样式
        style = ttk.Style()
        style.configure("Large.TButton", font=("宋体", 13))
        style.configure("Medium.TButton", font=("宋体", 16), padding=(10, 5))  # 中等大小，介于Large和ExtraLarge之间
        style.configure("Selected.TButton", font=("宋体", 13), background="lightgreen")
        style.configure("ExtraLarge.TButton", font=("宋体", 24), padding=(20, 10))
        
        self.mock_device_btn = ttk.Button(hardware_buttons_frame, text="启动模拟硬件", command=self._toggle_mock_device, style="Large.TButton")
        self.mock_device_btn.pack(side=tk.LEFT, padx=5)
        
        self.mock_device_status_label = tk.Label(hardware_buttons_frame, text="状态: 未启动", font=("宋体", 13), fg="gray")
        self.mock_device_status_label.pack(side=tk.LEFT, padx=10)

        # 控制区
        ctr = tk.Frame(self.parent); ctr.pack(fill=tk.X, pady=4)
        tk.Label(ctr, text="控制周期(ms)：", font=("宋体", 13)).pack(side=tk.LEFT)
        self.period_var = tk.IntVar(value=500); tk.Entry(ctr, textvariable=self.period_var, width=6, font=("宋体", 12)).pack(side=tk.LEFT, padx=(0,10))
        tk.Label(ctr, text="中心下降速率(cm/s)：", font=("宋体", 13)).pack(side=tk.LEFT)
        self.rate_var = tk.DoubleVar(value=5.0); tk.Entry(ctr, textvariable=self.rate_var, width=6, font=("宋体", 12)).pack(side=tk.LEFT, padx=(0,10))
        ttk.Button(ctr, text="开始", command=self._on_start, style="Large.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(ctr, text="停止", command=self._on_stop, style="Large.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(ctr, text="急停", command=self._on_emergency, style="Large.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(ctr, text="重置", command=self._on_reset, style="Large.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(ctr, text="串口监视器", command=self._open_serial_monitor, style="Large.TButton").pack(side=tk.LEFT, padx=5)
        
        # 单腿控制按钮放在控制区右侧，使用稍大的样式
        ttk.Button(ctr, text="单腿控制", command=self._open_single_leg_control, 
                  style="Medium.TButton").pack(side=tk.RIGHT, padx=10)

        # 图表 - 调整布局让XY坐标图占据上半部分大面积
        fig = plt.figure(figsize=(14,10))
        # 使用 GridSpec 来自定义布局
        gs = gridspec.GridSpec(2, 3, height_ratios=[2, 1], width_ratios=[1, 1, 1])
        
        # XY坐标图占据整个上半部分
        self.ax_xy = fig.add_subplot(gs[0, :])
        
        # 下半部分三个小图并排
        self.ax_z = fig.add_subplot(gs[1, 0])
        self.ax_att = fig.add_subplot(gs[1, 1])
        self.ax_force = fig.add_subplot(gs[1, 2])
        
        # 调整子图间距
        plt.tight_layout(pad=2.0)
        
        self.canvas = FigureCanvasTkAgg(fig, master=self.parent)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 底部三个板块横向排列
        bottom_frame = tk.Frame(self.parent)
        bottom_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        # 左侧：腿子坐标信息
        coord_frame = tk.Frame(bottom_frame)
        coord_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        
        coord_title = tk.Label(coord_frame, text="腿子坐标信息", font=("黑体", 20))
        coord_title.pack(pady=(0,5))
        
        # 坐标信息表格容器
        coord_content = tk.Frame(coord_frame)
        coord_content.pack(fill=tk.BOTH, expand=True)
        
        # 左右两列坐标信息
        left = tk.Frame(coord_content)
        right = tk.Frame(coord_content)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,10))
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 左侧标题和表头
        left_title = tk.Label(left, text="腿子 1-6", font=("黑体", 16))
        left_title.pack(pady=(0,5))
        left_head = tk.Frame(left); left_head.pack()
        for i,t in enumerate(("编号","X","Y","Z")):
            tk.Label(left_head, text=t, font=("黑体", 16)).grid(row=0, column=i, padx=6)
        
        # 右侧标题和表头
        right_title = tk.Label(right, text="腿子 7-12", font=("黑体", 16))
        right_title.pack(pady=(0,5))
        right_head = tk.Frame(right); right_head.pack()
        for i,t in enumerate(("编号","X","Y","Z")):
            tk.Label(right_head, text=t, font=("黑体", 16)).grid(row=0, column=i, padx=6)
        
        self.coord_entries = [None]*12
        for i in range(6):
            self.coord_entries[i] = self._row(left, i)
            self.coord_entries[i+6] = self._row(right, i+6)

        # 中间：控制循环日志
        left_log = tk.Frame(bottom_frame)
        left_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        tk.Label(left_log, text="控制循环", font=("黑体", 20)).pack(anchor="w")
        self.log_window = scrolledtext.ScrolledText(left_log, width=60, height=12, font=("宋体", 14), wrap='word')
        self.log_window.configure(state='normal')
        # 禁用水平滚动条
        self.log_window.configure(xscrollcommand=None)
        self.log_window.pack(fill=tk.BOTH, expand=True)

        # 右侧：系统运行状态日志
        right_log = tk.Frame(bottom_frame)
        right_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0))
        tk.Label(right_log, text="系统运行状态", font=("黑体", 20)).pack(anchor="w")
        self.status_log_window = scrolledtext.ScrolledText(right_log, width=60, height=12, font=("宋体", 14), wrap='word')
        self.status_log_window.configure(state='normal')
        # 禁用水平滚动条
        self.status_log_window.configure(xscrollcommand=None)
        self.status_log_window.pack(fill=tk.BOTH, expand=True)

        # 将 GUI 更新函数给控制器
        self.controller.update_ui = self._threadsafe_update

        # 初始日志（放入队列）
        self.logger.info("系统初始化完成，准备就绪。")

        # 周期刷新：从 logger 队列拉日志并写入 Tk 文本框
        self._schedule_drain_logs()

        # 初始绘图
        self._refresh(status_text="初始化完成")
        
        # 启动受力模拟定时器
        self._start_force_simulation_timer()

        # 全屏功能相关变量
        self.is_fullscreen = False
        self.normal_geometry = None
        
        # 绑定F11键切换全屏
        self.root.bind('<F11>', self._toggle_fullscreen)
        self.root.bind('<Escape>', self._exit_fullscreen)
        
        # 确保窗口可以获得焦点以接收键盘事件
        self.root.focus_set()

        # 默认启动全屏模式
        self.root.after(100, self._enter_fullscreen)  # 延迟执行以确保窗口完全初始化

        # 在窗口关闭时停止模拟硬件
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _row(self, parent, idx):
        f = tk.Frame(parent); f.pack(pady=1)
        tk.Label(f, text=f"{idx+1:02d}", font=("宋体", 15)).pack(side=tk.LEFT, padx=6)
        x = tk.Entry(f, width=8, font=("宋体", 14)); y = tk.Entry(f, width=8, font=("宋体", 14)); z = tk.Entry(f, width=8, font=("宋体", 14))
        # 移除readonly状态，让输入框可以正常显示和更新内容
        # for e in (x,y,z): e.configure(state="readonly")
        x.pack(side=tk.LEFT); y.pack(side=tk.LEFT, padx=4); z.pack(side=tk.LEFT)
        return (x,y,z)

    # ——— 按钮事件 ———
    def _on_start(self):
        period_ms = max(30, int(self.period_var.get()))
        rate_cm_s = max(0.0, float(self.rate_var.get()))
        
        # 启动受力模拟
        self._start_force_simulation()
        
        # 只通过MainController的set方法设置参数（它们内部会调用update_control_params）
        self.controller.set_period_ms(period_ms)
        self.controller.set_center_rate(rate_cm_s)
        self.controller.start_loop()
        self.logger.info(f"启动闭环：period={period_ms}ms, rate={rate_cm_s}cm/s")

    def _on_stop(self):
        # 停止受力模拟
        self._stop_force_simulation()
        
        self.controller.stop_loop(); self.logger.info("停止闭环。")

    def _on_emergency(self):
        # 紧急停止时立即停止受力模拟
        self._stop_force_simulation()
        
        self.controller.emergency_stop(); self.logger.error("⚠️ 急停已触发。")

    def _on_reset(self):
        # 重置时停止受力模拟
        self._stop_force_simulation()
        
        self.controller.reset_all(); self.logger.info("系统重置完成。")

    def _open_single_leg_control(self):
        """打开单腿控制窗口"""
        if self.single_leg_window and self.single_leg_window.winfo_exists():
            # 如果窗口已存在，则置前显示
            self.single_leg_window.lift()
            self.single_leg_window.focus()
            self.single_leg_window.attributes('-topmost', True)
            return
            
        # 创建单腿控制窗口
        self.single_leg_window = tk.Toplevel(self.root)
        self.single_leg_window.title("单腿控制 (置顶窗口)")
        self.single_leg_window.geometry("1400x900")  # 增大窗口尺寸
        
        # 设置窗口始终在最前端（永久置顶）
        self.single_leg_window.attributes('-topmost', True)
        self.single_leg_window.lift()
        self.single_leg_window.focus()
        
        # 设置选中第一个腿子（默认腿子1）
        self.selected_leg_index = 0
        self.leg_colors[0] = 'green'
        self._update_main_display()
        
        # 创建单腿控制界面内容
        self._create_single_leg_interface()
        
        # 窗口关闭时的处理
        def on_close():
            # 恢复所有腿子颜色为红色
            self.leg_colors = ['red'] * 12
            self._update_main_display()
            self.single_leg_window.destroy()
            self.single_leg_window = None
            
        self.single_leg_window.protocol("WM_DELETE_WINDOW", on_close)

    def _create_single_leg_interface(self):
        """创建单腿控制界面内容"""
        # 主框架
        main_frame = tk.Frame(self.single_leg_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧60%区域：单腿子模型展示
        left_frame = tk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left_frame.config(width=int(1200*0.6))
        
        # 左侧标题
        tk.Label(left_frame, text="单腿子模型展示", font=("黑体", 20)).pack(pady=10)
        
        # 创建单腿图表
        self.single_leg_fig = plt.figure(figsize=(8, 10))
        
        # 单个腿子的详细视图
        self.single_leg_ax = self.single_leg_fig.add_subplot(111)
        self.single_leg_canvas = FigureCanvasTkAgg(self.single_leg_fig, master=left_frame)
        self.single_leg_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # 右侧40%区域：控制布局
        right_frame = tk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(20, 0))
        right_frame.config(width=int(1200*0.4))
        
        # 右侧标题
        tk.Label(right_frame, text="单腿控制", font=("黑体", 20)).pack(pady=10)
        
        # 腿子信息显示区域
        self._create_leg_info_display(right_frame)
        
        # 十字键控制区域
        self._create_cross_control(right_frame)
        
        # Z轴控制区域
        self._create_z_control(right_frame)
        
        # 腿子选择按钮区域
        self._create_leg_selection(right_frame)
        
        # 初始更新显示
        self._update_single_leg_display()

    def _create_leg_info_display(self, parent):
        """创建腿子信息显示区域"""
        info_frame = tk.Frame(parent, relief=tk.RAISED, bd=2)
        info_frame.pack(pady=10, fill=tk.X)
        
        tk.Label(info_frame, text="腿子状态信息", font=("黑体", 14)).pack(pady=5)
        
        # 位置信息
        pos_frame = tk.Frame(info_frame)
        pos_frame.pack(pady=5)
        tk.Label(pos_frame, text="位置:", font=("宋体", 12)).pack(side=tk.LEFT)
        self.leg_pos_label = tk.Label(pos_frame, text="(0, 0, 0)", font=("宋体", 12), fg="blue")
        self.leg_pos_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # 受力信息
        force_frame = tk.Frame(info_frame)
        force_frame.pack(pady=5)
        tk.Label(force_frame, text="受力:", font=("宋体", 12)).pack(side=tk.LEFT)
        self.leg_force_label = tk.Label(force_frame, text="0.0 N", font=("宋体", 12), fg="red")
        self.leg_force_label.pack(side=tk.LEFT, padx=(5, 0))

    def _create_cross_control(self, parent):
        """创建十字键控制区域"""
        control_frame = tk.Frame(parent)
        control_frame.pack(pady=20)
        
        tk.Label(control_frame, text="XY轴平面控制（±1mm）", font=("黑体", 16)).pack(pady=10)
        
        # 十字键布局框架
        cross_frame = tk.Frame(control_frame)
        cross_frame.pack(pady=10)
        
        # 创建3x3网格布局
        # 第一行：空、上、空
        tk.Label(cross_frame, text="", width=8).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(cross_frame, text="↑\n上(1mm)", command=lambda: self._move_leg('up'), style="Large.TButton", width=8).grid(row=0, column=1, padx=5, pady=5)
        tk.Label(cross_frame, text="", width=8).grid(row=0, column=2, padx=5, pady=5)
        
        # 第二行：左、中心显示、右
        ttk.Button(cross_frame, text="←\n左(1mm)", command=lambda: self._move_leg('left'), style="Large.TButton", width=8).grid(row=1, column=0, padx=5, pady=5)
        self.current_leg_label = tk.Label(cross_frame, text=f"腿子{self.selected_leg_index+1}", font=("黑体", 16), 
                                         bg="lightgray", width=8, height=3, relief=tk.RAISED)
        self.current_leg_label.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(cross_frame, text="→\n右(1mm)", command=lambda: self._move_leg('right'), style="Large.TButton", width=8).grid(row=1, column=2, padx=5, pady=5)
        
        # 第三行：空、下、空
        tk.Label(cross_frame, text="", width=8).grid(row=2, column=0, padx=5, pady=5)
        ttk.Button(cross_frame, text="↓\n下(1mm)", command=lambda: self._move_leg('down'), style="Large.TButton", width=8).grid(row=2, column=1, padx=5, pady=5)
        tk.Label(cross_frame, text="", width=8).grid(row=2, column=2, padx=5, pady=5)

    def _create_z_control(self, parent):
        """创建Z轴高度控制区域"""
        z_control_frame = tk.Frame(parent)
        z_control_frame.pack(pady=20)
        
        tk.Label(z_control_frame, text="Z轴高度控制", font=("黑体", 16)).pack(pady=10)
        
        # Z轴按钮布局
        z_buttons_frame = tk.Frame(z_control_frame)
        z_buttons_frame.pack(pady=10)
        
        # Z轴升高按钮
        ttk.Button(z_buttons_frame, text="Z轴升高\n(+10mm)", command=lambda: self._move_leg('up_z'), 
                  style="Large.TButton", width=12).pack(side=tk.LEFT, padx=5)
        
        # Z轴降低按钮
        ttk.Button(z_buttons_frame, text="Z轴降低\n(-10mm)", command=lambda: self._move_leg('down_z'), 
                  style="Large.TButton", width=12).pack(side=tk.LEFT, padx=5)

    def _create_leg_selection(self, parent):
        """创建腿子选择按钮区域"""
        selection_frame = tk.Frame(parent)
        selection_frame.pack(pady=20, fill=tk.BOTH, expand=True)
        
        tk.Label(selection_frame, text="腿子选择", font=("黑体", 16)).pack(pady=10)
        
        # 创建12个腿子选择按钮，4行3列布局
        buttons_frame = tk.Frame(selection_frame)
        buttons_frame.pack(pady=10)
        
        self.leg_buttons = []
        for i in range(12):
            row = i // 3
            col = i % 3
            btn = ttk.Button(buttons_frame, text=f"腿子{i+1}", 
                           command=lambda idx=i: self._select_leg(idx), 
                           style="Large.TButton", width=10)
            btn.grid(row=row, column=col, padx=5, pady=5)
            self.leg_buttons.append(btn)
        
        # 更新按钮状态
        self._update_leg_buttons()

    def _select_leg(self, leg_index):
        """选择指定的腿子"""
        # 恢复之前选中腿子的颜色
        self.leg_colors[self.selected_leg_index] = 'red'
        
        # 设置新选中的腿子
        self.selected_leg_index = leg_index
        self.leg_colors[leg_index] = 'green'
        
        # 更新界面显示
        self.current_leg_label.config(text=f"腿子{leg_index+1}")
        self._update_leg_buttons()
        self._update_single_leg_display()
        self._update_main_display()

    def _update_leg_buttons(self):
        """更新腿子选择按钮的状态"""
        for i, btn in enumerate(self.leg_buttons):
            if i == self.selected_leg_index:
                btn.config(style="Selected.TButton")
            else:
                btn.config(style="Large.TButton")

    def _move_leg(self, direction):
        """移动选中的腿子"""
        leg_num = self.selected_leg_index + 1
        
        # 根据方向类型输出不同的日志信息
        if direction in ['left', 'right', 'up', 'down']:
            # XY轴控制
            direction_map = {
                'left': '左(-1mm X轴)',
                'right': '右(+1mm X轴)', 
                'up': '上(+1mm Y轴)',
                'down': '下(-1mm Y轴)'
            }
            self.logger.info(f"XY轴控制：腿子{leg_num} {direction_map[direction]}")
        elif direction in ['up_z', 'down_z']:
            # Z轴控制
            direction_map = {
                'up_z': '升高(+10mm Z轴)',
                'down_z': '降低(-10mm Z轴)'
            }
            self.logger.info(f"Z轴控制：腿子{leg_num} {direction_map[direction]}")
        
        # 这里可以添加实际的腿子移动控制逻辑
        
    def _update_single_leg_display(self):
        """更新单腿显示"""
        if not hasattr(self, 'single_leg_ax'):
            return
            
        # 清空并重绘单腿图表
        self.single_leg_ax.clear()
        # 移除标题，让图表更简洁
        
        # 获取选中腿子的数据
        try:
            leg = self.legs[self.selected_leg_index]
            x_pos = getattr(leg, 'x', 0.0)
            y_pos = getattr(leg, 'y', 0.0)
            z_pos = getattr(leg, 'z', 0.0)
            force = getattr(leg, 'force', 0.0)
            
            # 更新右侧信息面板
            if hasattr(self, 'leg_pos_label'):
                self.leg_pos_label.config(text=f"({x_pos:.1f}, {y_pos:.1f}, {z_pos:.1f})")
            if hasattr(self, 'leg_force_label'):
                self.leg_force_label.config(text=f"{force:.1f} N")
            
            # 简单的腿子图形表示（只显示图形，不显示文字信息）
            self.single_leg_ax.scatter([0], [0], c='green' if self.leg_colors[self.selected_leg_index] == 'green' else 'red', 
                                     s=800, marker='o', edgecolors='black', linewidth=3)
            self.single_leg_ax.text(0, -0.15, f"腿子{self.selected_leg_index+1}", ha='center', fontsize=20, fontweight='bold')
            
            self.single_leg_ax.set_xlim(-1, 1)
            self.single_leg_ax.set_ylim(-1, 1)
            self.single_leg_ax.set_aspect('equal')
            self.single_leg_ax.axis('off')  # 隐藏坐标轴，使图形更简洁
            
        except Exception as e:
            self.single_leg_ax.text(0.5, 0.5, f"数据加载错误: {e}", 
                                  transform=self.single_leg_ax.transAxes, fontsize=12, ha='center')
            
        except Exception as e:
            self.single_leg_ax.text(0.5, 0.5, f"数据加载错误: {e}", 
                                  transform=self.single_leg_ax.transAxes, fontsize=12, ha='center')
        
        self.single_leg_canvas.draw()

    def _update_main_display(self):
        """更新主界面显示"""
        # 触发主界面的刷新，以显示腿子颜色变化
        if hasattr(self, '_refresh'):
            self._refresh()

    def _open_serial_monitor(self):
        """打开串口监视器窗口"""
        if self.serial_monitor_window and self.serial_monitor_window.winfo_exists():
            # 如果窗口已存在，则置前显示
            self.serial_monitor_window.lift()
            self.serial_monitor_window.focus()
            self.serial_monitor_window.attributes('-topmost', True)
            return
        
        # 创建新的串口监视器窗口
        self.serial_monitor_window = tk.Toplevel(self.root)
        self.serial_monitor_window.title("串口监视器 (置顶窗口)")
        self.serial_monitor_window.geometry("1000x600")
        
        # 设置窗口始终在最前端（永久置顶）
        self.serial_monitor_window.attributes('-topmost', True)
        self.serial_monitor_window.lift()
        self.serial_monitor_window.focus()
        
        # 创建TX和RX分离的窗口
        main_frame = tk.Frame(self.serial_monitor_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # TX窗口
        tx_frame = tk.Frame(main_frame)
        tx_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(tx_frame, text="发送 (TX)", font=("黑体", 16)).pack(anchor="w")
        self.serial_monitor_window.tx_window = scrolledtext.ScrolledText(
            tx_frame, width=60, height=25, font=("Consolas", 13), wrap='word'
        )
        # 禁用水平滚动条
        self.serial_monitor_window.tx_window.configure(xscrollcommand=None)
        self.serial_monitor_window.tx_window.pack(fill=tk.BOTH, expand=True)
        
        # RX窗口
        rx_frame = tk.Frame(main_frame)
        rx_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10,0))
        tk.Label(rx_frame, text="接收 (RX)", font=("黑体", 16)).pack(anchor="w")
        self.serial_monitor_window.rx_window = scrolledtext.ScrolledText(
            rx_frame, width=60, height=25, font=("Consolas", 13), wrap='word'
        )
        # 禁用水平滚动条
        self.serial_monitor_window.rx_window.configure(xscrollcommand=None)
        self.serial_monitor_window.rx_window.pack(fill=tk.BOTH, expand=True)
        
        # 控制按钮
        button_frame = tk.Frame(self.serial_monitor_window)
        button_frame.pack(fill=tk.X, padx=10, pady=(0,10))
        ttk.Button(button_frame, text="清空TX", command=lambda: self.serial_monitor_window.tx_window.delete(1.0, tk.END), style="Large.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空RX", command=lambda: self.serial_monitor_window.rx_window.delete(1.0, tk.END), style="Large.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空全部", command=self._clear_all_serial, style="Large.TButton").pack(side=tk.LEFT, padx=5)
        
        # 窗口关闭事件
        self.serial_monitor_window.protocol("WM_DELETE_WINDOW", self._close_serial_monitor)
    
    def _clear_all_serial(self):
        """清空串口监视器所有内容"""
        if self.serial_monitor_window and self.serial_monitor_window.winfo_exists():
            self.serial_monitor_window.tx_window.delete(1.0, tk.END)
            self.serial_monitor_window.rx_window.delete(1.0, tk.END)
    
    def _close_serial_monitor(self):
        """关闭串口监视器窗口"""
        if self.serial_monitor_window:
            self.serial_monitor_window.destroy()
            self.serial_monitor_window = None

    def _toggle_mock_device(self):
        """启动/停止模拟硬件设备"""
        if self.mock_device_process is None:
            self._start_mock_device()
        else:
            self._stop_mock_device()

    def _start_mock_device(self):
        """启动模拟硬件设备"""
        try:
            ctrl_port = self.mock_ctrl_port_var.get().strip()
            telem_port = self.mock_telem_port_var.get().strip()
            
            if not ctrl_port or not telem_port:
                messagebox.showerror("错误", "请输入有效的控制口和遥测口")
                return
            
            # 构建启动命令
            cmd = [
                sys.executable, "-m", "hardware.mock_serial_device",
                "--ctrl-port", ctrl_port,
                "--telem-port", telem_port,
                "--baud", "115200",
                "--telem-interval", "0.1"
            ]
            
            # 添加XY扰动参数
            if self.disturbance_enabled_var.get():
                cmd.extend([
                    "--xy-disturbance",
                    "--disturbance-amplitude", str(self.disturbance_amplitude_var.get()),
                    "--disturbance-frequency", str(self.disturbance_frequency_var.get())
                ])
            
            # 获取项目根目录
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # 启动进程
            self.mock_device_process = subprocess.Popen(
                cmd,
                cwd=project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
            )
            
            # 更新UI状态显示
            disturbance_status = ""
            if self.disturbance_enabled_var.get():
                amplitude = self.disturbance_amplitude_var.get()
                frequency = self.disturbance_frequency_var.get()
                disturbance_status = f" [XY扰动: {amplitude}cm@{frequency}Hz]"
            
            self.mock_device_btn.config(text="停止模拟硬件")
            self.mock_device_status_label.config(text=f"状态: 运行中 ({ctrl_port}, {telem_port}){disturbance_status}", fg="green")
            
            # 启动监控线程
            threading.Thread(target=self._monitor_mock_device, daemon=True).start()
            
            log_msg = f"模拟硬件已启动: 控制口={ctrl_port}, 遥测口={telem_port}"
            if self.disturbance_enabled_var.get():
                log_msg += f", XY扰动={self.disturbance_amplitude_var.get()}cm@{self.disturbance_frequency_var.get()}Hz"
            self.logger.info(log_msg)
            
        except Exception as e:
            messagebox.showerror("错误", f"启动模拟硬件失败: {str(e)}")
            self.logger.error(f"启动模拟硬件失败: {e}")

    def _stop_mock_device(self):
        """停止模拟硬件设备"""
        if self.mock_device_process:
            try:
                self.mock_device_process.terminate()
                self.mock_device_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.mock_device_process.kill()
            except Exception as e:
                self.logger.error(f"停止模拟硬件时出错: {e}")
            finally:
                self.mock_device_process = None
                
        # 更新UI状态
        self.mock_device_btn.config(text="启动模拟硬件")
        self.mock_device_status_label.config(text="状态: 已停止", fg="gray")
        self.logger.info("模拟硬件已停止")

    def _monitor_mock_device(self):
        """监控模拟硬件进程状态"""
        if self.mock_device_process:
            try:
                # 等待进程结束
                return_code = self.mock_device_process.wait()
                
                # 如果进程意外退出，更新UI状态
                if return_code != 0:
                    self.root.after(0, lambda: self._on_mock_device_crashed(return_code))
                else:
                    self.root.after(0, self._on_mock_device_stopped)
                    
            except Exception as e:
                self.logger.error(f"监控模拟硬件进程时出错: {e}")

    def _on_mock_device_crashed(self, return_code):
        """处理模拟硬件进程崩溃"""
        self.mock_device_process = None
        self.mock_device_btn.config(text="启动模拟硬件")
        self.mock_device_status_label.config(text=f"状态: 异常退出 (代码: {return_code})", fg="red")
        self.logger.error(f"模拟硬件进程异常退出，返回码: {return_code}")

    def _on_mock_device_stopped(self):
        """处理模拟硬件正常停止"""
        self.mock_device_process = None
        self.mock_device_btn.config(text="启动模拟硬件")
        self.mock_device_status_label.config(text="状态: 已停止", fg="gray")

    # ——— 线程安全 UI 更新入口 ———
    def _threadsafe_update(self, full_text, short_text):
        if self.root and self.root.winfo_exists():
            self.root.after(0, lambda: self._refresh(status_text=full_text))

    # ——— 定时从队列取日志并写入 Text（核心修复点） ———
    def _schedule_drain_logs(self):
        # 处理主日志队列（按级别分流）
        while not self.logger.gui_queue.empty():
            s = self.logger.gui_queue.get_nowait()
            
            # 判断日志级别，INFO级别显示到右侧"系统运行状态"，其他显示到左侧"控制循环"
            if "[INFO]" in s:
                # INFO级别日志显示到系统运行状态窗口
                self.status_log_window.insert(tk.END, s+"\n")
                self.status_log_window.see(tk.END)
            else:
                # DEBUG、WARN、ERROR等其他级别显示到控制循环窗口
                self.log_window.insert(tk.END, s+"\n")
                self.log_window.see(tk.END)
        
        # 串口日志队列处理（分流TX/RX和其他内容）
        while not self.logger.serial_queue.empty():
            s = self.logger.serial_queue.get_nowait()
            
            # 判断是否为TX/RX内容
            if "[SERIAL:TX]" in s or "[SERIAL:RX]" in s:
                # 如果串口监视器窗口存在，则显示到对应窗口
                if self.serial_monitor_window and self.serial_monitor_window.winfo_exists():
                    if "[SERIAL:TX]" in s:
                        self.serial_monitor_window.tx_window.insert(tk.END, s+"\n")
                        self.serial_monitor_window.tx_window.see(tk.END)
                    elif "[SERIAL:RX]" in s:
                        self.serial_monitor_window.rx_window.insert(tk.END, s+"\n")
                        self.serial_monitor_window.rx_window.see(tk.END)
            else:
                # 非TX/RX的串口内容按级别分流
                if "[INFO]" in s:
                    self.status_log_window.insert(tk.END, s+"\n")
                    self.status_log_window.see(tk.END)
                else:
                    self.log_window.insert(tk.END, s+"\n")
                    self.log_window.see(tk.END)
        
        self.root.after(DRAIN_INTERVAL_MS, self._schedule_drain_logs)

    # ——— 绘图与输入框刷新（仍在主线程） ———
    def _refresh(self, status_text=""):
        self.status_label.config(text=f"运行状态：{status_text}")
        
        # 直接使用LegUnit数据，确保显示的是控制器实际使用的数据
        display_z = [l.z for l in self.legs]
        display_xy = [(l.x, l.y) for l in self.legs]
        
        # 获取各种中心点信息
        cz = sum(display_z[i] for i in [4,5,6,7]) / 4.0  # 实际中心Z
        
        # 获取目标中心Z
        tgt = getattr(self.controller.control, '_target_center_z', None)
        tgt_txt = f"{tgt:.0f}cm" if tgt is not None else "-"
        
        # 获取固定的理论几何中心
        try:
            theory_cx, theory_cy = self.controller.control._initial_geometric_center
            theory_cz = sum(display_z[i] for i in [4,5,6,7]) / 4.0  # Z轴暂时使用实时计算
        except Exception:
            theory_cx, theory_cy, theory_cz = 0.0, 0.0, cz
        
        # 获取当前实际几何中心
        try:
            state = self.controller.estimator.estimate(self.legs, self.controller.sensor)
            current_cx, current_cy, current_cz = state.center_x, state.center_y, state.center_z
        except Exception:
            current_cx, current_cy, current_cz = 0.0, 0.0, cz
        
        # 更新中心信息显示
        self.center_info_label.config(
            text=f"目标中心Z：{tgt_txt}  |  "
                 f"当前几何中心：X={current_cx:.1f}, Y={current_cy:.1f}, Z={current_cz:.1f}cm  |  "
                 f"理论几何中心：X={theory_cx:.1f}, Y={theory_cy:.1f}, Z={theory_cz:.1f}cm"
        )

        # Z 柱状图 - 调整为小图显示
        self.ax_z.clear(); self.ax_z.set_title("Z轴高度", fontsize=20); self.ax_z.set_ylim(0,700)
        names = [l.name for l in self.legs]
        zvals = display_z
        bars = self.ax_z.bar(names, zvals, color='skyblue')
        # 调整字体大小和标签旋转
        self.ax_z.tick_params(axis='x', labelsize=9, rotation=45)
        self.ax_z.tick_params(axis='y', labelsize=9)
        for i,b in enumerate(bars):
            self.ax_z.text(b.get_x()+b.get_width()/2, b.get_height()+8, f"{zvals[i]:.0f}",
                           ha='center', va='bottom', fontsize=8)

        # XY坐标图（放大显示，占据上半部分）
        self.ax_xy.clear(); self.ax_xy.set_title("腿子XY坐标分布", fontsize=20)
        self.ax_xy.set_xlabel("X (cm)", fontsize=12); self.ax_xy.set_ylabel("Y (cm)", fontsize=12)
        self.ax_xy.grid(True); self.ax_xy.set_aspect('equal')
        self.ax_xy.tick_params(axis='both', labelsize=12)
        
        # 设置固定的坐标轴范围（紧凑显示，减少边界）
        self.ax_xy.set_xlim(-100, 2500)
        self.ax_xy.set_ylim(-20, 350)
        
        # 画腿子位置 - 支持不同颜色显示
        xs = [xy[0] for xy in display_xy]; ys = [xy[1] for xy in display_xy]
        
        # 根据腿子颜色状态分别绘制
        for i in range(12):
            color = self.leg_colors[i] if hasattr(self, 'leg_colors') else 'red'
            self.ax_xy.scatter([xs[i]], [ys[i]], c=color, s=120, marker='o', 
                             edgecolors='black', linewidth=1)
        
        # 标注腿子编号 - 放大字体
        for i in range(12):
            self.ax_xy.text(xs[i], ys[i]+50, str(i+1), fontsize=14, ha='center', fontweight='bold')
        
        # 画对称腿对连线
        for i in range(0,12,2):
            self.ax_xy.plot([xs[i], xs[i+1]], [ys[i], ys[i+1]], color='gray', linestyle='--', alpha=0.6, linewidth=2)

        # 画当前几何中心点（蓝色边框正方形，透明填充） - 小尺寸
        self.ax_xy.scatter([current_cx], [current_cy], c='none', s=10, marker='s', 
                          label=f'当前几何中心 ({current_cx:.1f}, {current_cy:.1f})', edgecolors='blue', linewidth=1)

        # 画理论几何中心点（绿色边框圆形，透明填充） - 更大尺寸
        self.ax_xy.scatter([theory_cx], [theory_cy], c='none', s=80, marker='o', 
                          label=f'理论几何中心 ({theory_cx:.1f}, {theory_cy:.1f})', edgecolors='green', linewidth=1)

        # 画中心偏差连线（很细的红色实线）
        if abs(current_cx - theory_cx) > 1 or abs(current_cy - theory_cy) > 1:
            self.ax_xy.plot([current_cx, theory_cx], [current_cy, theory_cy], 
                           color='red', linestyle='-', linewidth=0.8, alpha=0.8, label='中心偏差')

        # 添加图例 - 使用实际形状和颜色
        import matplotlib.patches as mpatches
        import matplotlib.lines as mlines
        
        # 创建自定义图例元素
        # 普通腿子 - 红色圆形
        red_leg = mlines.Line2D([], [], color='red', marker='o', linestyle='None',
                               markersize=10, markeredgecolor='black', markeredgewidth=1,
                               label='普通腿子')
        
        # 选中腿子 - 绿色圆形
        green_leg = mlines.Line2D([], [], color='green', marker='o', linestyle='None',
                                 markersize=10, markeredgecolor='black', markeredgewidth=1,
                                 label='选中腿子')
        
        # 当前几何中心 - 蓝色边框方形，透明填充
        current_center = mlines.Line2D([], [], color='none', marker='s', linestyle='None',
                                     markersize=8, markeredgecolor='blue', markeredgewidth=2,
                                     label=f'当前几何中心 ({current_cx:.1f}, {current_cy:.1f})')
        
        # 理论几何中心 - 绿色边框圆形，透明填充
        theory_center = mlines.Line2D([], [], color='none', marker='o', linestyle='None',
                                    markersize=12, markeredgecolor='green', markeredgewidth=2,
                                    label=f'理论几何中心 ({theory_cx:.1f}, {theory_cy:.1f})')
        
        # 构建图例元素列表
        legend_elements = [red_leg, green_leg, current_center, theory_center]
        
        # 如果有中心偏差，添加偏差线图例
        if abs(current_cx - theory_cx) > 1 or abs(current_cy - theory_cy) > 1:
            deviation_line = mlines.Line2D([], [], color='red', linestyle='-', 
                                         linewidth=2, alpha=0.8, label='中心偏差')
            legend_elements.append(deviation_line)
        
        self.ax_xy.legend(handles=legend_elements, loc='upper right', fontsize=12)

        # 四角翘曲图 - 调整为小图显示
        self.ax_att.clear(); self.ax_att.set_title("四角翘曲", fontsize=20)
        dzs = [display_z[i] - cz for i in [0,1,10,11]]
        bars = self.ax_att.bar(["左前", "左后", "右后", "右前"], dzs, color='orange')
        self.ax_att.set_ylim(-100, 100)
        self.ax_att.tick_params(axis='x', labelsize=9, rotation=30)
        self.ax_att.tick_params(axis='y', labelsize=9)
        # 添加数值标签
        for i, bar in enumerate(bars):
            height = bar.get_height()
            self.ax_att.text(bar.get_x() + bar.get_width()/2., height + (5 if height >= 0 else -10),
                           f'{dzs[i]:.0f}', ha='center', va='bottom' if height >= 0 else 'top', fontsize=8)

        # 受力监测图 - 调整为小图显示
        self.ax_force.clear(); self.ax_force.set_title("受力监测", fontsize=20)
        try:
            # 优先使用GUI模拟的受力值
            if hasattr(self, 'force_current_values') and self.force_current_values:
                force_vals = self.force_current_values
            else:
                # 回退到传感器数据
                forces = self.controller.sensor.latest_forces()
                force_vals = forces if len(forces) >= 12 else [getattr(l,"force",0.0) for l in self.legs]
        except Exception:
            force_vals = [getattr(l,"force",0.0) for l in self.legs]
        self.ax_force.bar(names, force_vals, color='green')
        self.ax_force.set_ylim(0, 150)
        self.ax_force.tick_params(axis='x', labelsize=9, rotation=45)
        self.ax_force.tick_params(axis='y', labelsize=9)

        self.canvas.draw()
        
        # 更新输入框内容
        for i,(xe,ye,ze) in enumerate(self.coord_entries):
            # 输入框显示传感器实际值
            try:
                x_val, y_val = display_xy[i] if i < len(display_xy) else (0.0, 0.0)
                z_val = display_z[i] if i < len(display_z) else 0.0
                
                # 更新输入框内容
                xe.config(state="normal")
                xe.delete(0, tk.END)
                xe.insert(0, f"{x_val:.1f}")
                xe.config(state="readonly")
                
                ye.config(state="normal")
                ye.delete(0, tk.END)
                ye.insert(0, f"{y_val:.1f}")
                ye.config(state="readonly")
                
                ze.config(state="normal")
                ze.delete(0, tk.END)
                ze.insert(0, f"{z_val:.1f}")
                ze.config(state="readonly")
            except Exception:
                pass

    # ——— 受力模拟相关方法 ———
    def _start_force_simulation_timer(self):
        """启动受力模拟定时器"""
        self._update_force_simulation()
    
    def _start_force_simulation(self):
        """启动受力模拟"""
        import time
        self.force_simulation_active = True
        self.force_start_time = time.time()
        
        # 设置目标受力值（在正常工作范围内，带有一些差异）
        import random
        base_force = 95.0  # 基础受力值
        for i in range(12):
            # 每个腿子有不同的基础受力，模拟实际负载差异
            variation = random.uniform(-10.0, 10.0)
            self.force_base_values[i] = base_force + variation
            self.force_target_values[i] = self.force_base_values[i]
    
    def _stop_force_simulation(self):
        """停止受力模拟"""
        self.force_simulation_active = False
        # 目标值设为0，让受力值逐渐降到0
        for i in range(12):
            self.force_target_values[i] = 0.0
    
    def _update_force_simulation(self):
        """更新受力模拟值"""
        import time
        import random
        import math
        
        if self.force_simulation_active:
            # 系统运行中，模拟正常工作受力
            current_time = time.time()
            elapsed = current_time - self.force_start_time
            
            for i in range(12):
                base = self.force_base_values[i]
                
                # 添加周期性抖动（模拟振动和负载变化）
                sine_component = 3.0 * math.sin(2 * math.pi * 0.5 * elapsed + i * 0.5)
                noise_component = random.uniform(-2.0, 2.0)
                
                # 目标值 = 基础值 + 抖动
                self.force_target_values[i] = base + sine_component + noise_component
                
        # 无论是否激活，都让当前值逐渐向目标值靠拢
        for i in range(12):
            target = self.force_target_values[i]
            current = self.force_current_values[i]
            
            # 平滑过渡到目标值
            diff = target - current
            step = diff * 0.1  # 10%的步长，提供平滑过渡
            
            self.force_current_values[i] = max(0.0, current + step)
        
        # 更新传感器系统的受力值
        try:
            if hasattr(self.controller, 'sensor') and hasattr(self.controller.sensor, '_forces'):
                self.controller.sensor._forces = self.force_current_values.copy()
        except Exception:
            pass
        
        # 定时调用自己
        self.root.after(100, self._update_force_simulation)  # 每100ms更新一次

    def _toggle_fullscreen(self, event=None):
        """切换全屏状态"""
        if self.is_fullscreen:
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    def _enter_fullscreen(self, event=None):
        """进入全屏模式"""
        if not self.is_fullscreen:
            # 保存当前窗口几何信息（如果还没保存的话）
            if self.normal_geometry is None:
                self.normal_geometry = self.root.geometry()
            
            # 设置全屏 - 不使用overrideredirect以保持任务栏可见性
            self.root.state('zoomed')  # Windows下的最大化
            self.root.attributes('-fullscreen', True)  # 使用-fullscreen属性
            
            # 隐藏滚动条
            self._hide_scrollbars()
            
            self.is_fullscreen = True
            self.logger.info("进入全屏模式 (按Esc或F11退出)")

    def _exit_fullscreen(self, event=None):
        """退出全屏模式"""
        if self.is_fullscreen:
            # 恢复窗口状态
            self.root.attributes('-fullscreen', False)  # 退出全屏属性
            self.root.state('normal')
            
            # 恢复原始窗口大小
            if self.normal_geometry:
                self.root.geometry(self.normal_geometry)
            
            # 恢复滚动条
            self._show_scrollbars()
            
            self.is_fullscreen = False
            self.logger.info("退出全屏模式")

    def _hide_scrollbars(self):
        """隐藏所有滚动条"""
        try:
            # 隐藏主窗口的滚动条
            if hasattr(self, 'scrollbar_y'):
                self.scrollbar_y.pack_forget()
            if hasattr(self, 'scrollbar_x'):
                self.scrollbar_x.pack_forget()
            
            # 禁用Canvas的滚动命令
            if hasattr(self, 'main_canvas'):
                self.main_canvas.configure(yscrollcommand=None, xscrollcommand=None)
            
            # 隐藏日志窗口的滚动条
            if hasattr(self, 'log_window'):
                # 获取内部的Text组件并禁用其滚动条
                self.log_window.vbar.pack_forget()
            
            if hasattr(self, 'status_log_window'):
                self.status_log_window.vbar.pack_forget()
                
        except Exception as e:
            self.logger.debug(f"隐藏滚动条时出错: {e}")

    def _show_scrollbars(self):
        """显示所有滚动条"""
        try:
            # 恢复主窗口的滚动条
            if hasattr(self, 'scrollbar_y'):
                self.scrollbar_y.pack(side="right", fill="y")
            if hasattr(self, 'scrollbar_x'):
                self.scrollbar_x.pack(side="bottom", fill="x")
            
            # 重新启用Canvas的滚动命令
            if hasattr(self, 'main_canvas'):
                if hasattr(self, 'scrollbar_y'):
                    self.main_canvas.configure(yscrollcommand=self.scrollbar_y.set)
                if hasattr(self, 'scrollbar_x'):
                    self.main_canvas.configure(xscrollcommand=self.scrollbar_x.set)
            
            # 恢复日志窗口的滚动条
            if hasattr(self, 'log_window'):
                self.log_window.vbar.pack(side="right", fill="y")
                self.log_window.configure(yscrollcommand=self.log_window.vbar.set)
            
            if hasattr(self, 'status_log_window'):
                self.status_log_window.vbar.pack(side="right", fill="y")
                self.status_log_window.configure(yscrollcommand=self.status_log_window.vbar.set)
                
        except Exception as e:
            self.logger.debug(f"恢复滚动条时出错: {e}")

    def _on_close(self):
        try: 
            # 关闭串口监视器窗口
            if self.serial_monitor_window:
                self.serial_monitor_window.destroy()
            self.controller.shutdown(); self.logger.info("窗口关闭，程序退出")
        except Exception: pass
        self.root.destroy(); sys.exit(0)

def start_gui(controller):
    root = tk.Tk()
    
    # 设置窗口初始大小（作为退出全屏时的默认尺寸）
    root.geometry("1400x1000")
    
    # 创建主Canvas和滚动条
    main_canvas = tk.Canvas(root)
    scrollbar_y = ttk.Scrollbar(root, orient="vertical", command=main_canvas.yview)
    scrollbar_x = ttk.Scrollbar(root, orient="horizontal", command=main_canvas.xview)
    
    # 创建可滚动的Frame
    scrollable_frame = tk.Frame(main_canvas)
    
    # 配置Canvas
    scrollable_frame.bind(
        "<Configure>",
        lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
    )
    
    # 将Frame添加到Canvas
    canvas_frame = main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    
    # 配置Canvas滚动
    main_canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
    
    # 布局Canvas和滚动条
    main_canvas.pack(side="left", fill="both", expand=True)
    scrollbar_y.pack(side="right", fill="y")
    scrollbar_x.pack(side="bottom", fill="x")
    
    # 绑定鼠标滚轮事件
    def _on_mousewheel(event):
        main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def _on_shift_mousewheel(event):
        main_canvas.xview_scroll(int(-1*(event.delta/120)), "units")
    
    # 绑定滚轮事件
    main_canvas.bind("<MouseWheel>", _on_mousewheel)
    main_canvas.bind("<Shift-MouseWheel>", _on_shift_mousewheel)
    
    # 动态调整Canvas内Frame的宽度
    def _configure_canvas_frame(event):
        canvas_width = event.width
        main_canvas.itemconfig(canvas_frame, width=canvas_width)
    
    main_canvas.bind('<Configure>', _configure_canvas_frame)
    
    # 创建GUI控制器，传入scrollable_frame而不是root
    app = GUIController(scrollable_frame, controller)
    
    # 将滚动条引用传递给app，以便在全屏时控制
    app.main_canvas = main_canvas
    app.scrollbar_y = scrollbar_y
    app.scrollbar_x = scrollbar_x
    
    # 确保焦点在Canvas上以支持键盘滚动
    main_canvas.focus_set()
    
    root.mainloop()

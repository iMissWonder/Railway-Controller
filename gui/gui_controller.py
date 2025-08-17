# gui_controller.py
import tkinter as tk
from tkinter import scrolledtext, ttk
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sys

matplotlib.rcParams['font.sans-serif'] = ['SimHei']
matplotlib.rcParams['axes.unicode_minus'] = False

DRAIN_INTERVAL_MS = 50  # 日志队列刷新周期

class GUIController:
    def __init__(self, root, controller):
        self.root = root
        self.controller = controller
        self.logger = controller.logger
        self.legs = controller.get_leg_data()
        
        # 串口监视器窗口引用
        self.serial_monitor_window = None

        self.root.title("道岔腿子控制系统（周期闭环 + 串口监视器）")

        # 顶部状态显示区域
        top = tk.Frame(root); top.pack(fill=tk.X, pady=4)
        self.status_label = tk.Label(top, text="运行状态：初始化完成", font=("黑体", 14))
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # 中心信息显示（合并所有中心信息）
        self.center_info_label = tk.Label(top, text="目标中心Z：-  实际中心：-  几何中心：-", font=("宋体", 10))
        self.center_info_label.pack(side=tk.RIGHT, padx=10)

        # 控制区
        ctr = tk.Frame(root); ctr.pack(fill=tk.X, pady=4)
        tk.Label(ctr, text="控制周期(ms)：").pack(side=tk.LEFT)
        self.period_var = tk.IntVar(value=500); tk.Entry(ctr, textvariable=self.period_var, width=6).pack(side=tk.LEFT, padx=(0,10))
        tk.Label(ctr, text="中心下降速率(mm/s)：").pack(side=tk.LEFT)
        self.rate_var = tk.DoubleVar(value=10.0); tk.Entry(ctr, textvariable=self.rate_var, width=6).pack(side=tk.LEFT, padx=(0,10))
        ttk.Button(ctr, text="开始", command=self._on_start).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctr, text="停止", command=self._on_stop).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctr, text="急停", command=self._on_emergency).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctr, text="重置", command=self._on_reset).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctr, text="串口监视器", command=self._open_serial_monitor).pack(side=tk.LEFT, padx=5)

        # 图表
        fig = plt.figure(figsize=(14,10))
        self.ax_z = fig.add_subplot(2,2,1)
        self.ax_xy = fig.add_subplot(2,2,2)
        self.ax_att = fig.add_subplot(2,2,3)
        self.ax_force = fig.add_subplot(2,2,4)
        self.canvas = FigureCanvasTkAgg(fig, master=root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 输入框
        wrap = tk.Frame(root); wrap.pack(pady=4)
        left = tk.Frame(wrap); right = tk.Frame(wrap)
        left.pack(side=tk.LEFT, padx=20); right.pack(side=tk.LEFT, padx=20)
        
        # 左侧标题和表头
        left_title = tk.Label(left, text="腿子 1-6 坐标信息", font=("黑体", 12))
        left_title.pack(pady=(0,5))
        left_head = tk.Frame(left); left_head.pack()
        for i,t in enumerate(("编号","X","Y","Z")):
            tk.Label(left_head, text=t, font=("黑体", 10)).grid(row=0, column=i, padx=6)
        
        # 右侧标题和表头
        right_title = tk.Label(right, text="腿子 7-12 坐标信息", font=("黑体", 12))
        right_title.pack(pady=(0,5))
        right_head = tk.Frame(right); right_head.pack()
        for i,t in enumerate(("编号","X","Y","Z")):
            tk.Label(right_head, text=t, font=("黑体", 10)).grid(row=0, column=i, padx=6)
        
        self.coord_entries = [None]*12
        for i in range(6):
            self.coord_entries[i] = self._row(left, i)
            self.coord_entries[i+6] = self._row(right, i+6)

        # 日志区
        logs = tk.Frame(root); logs.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        # 左侧日志窗口（控制循环 - INFO外的信息）
        left_log = tk.Frame(logs); left_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(left_log, text="控制循环").pack(anchor="w")
        self.log_window = scrolledtext.ScrolledText(left_log, width=80, height=8, font=("宋体", 10))
        self.log_window.pack(fill=tk.BOTH, expand=True)

        # 右侧日志窗口（系统运行状态 - 只显示INFO信息）
        right_log = tk.Frame(logs); right_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6,0))
        tk.Label(right_log, text="系统运行状态").pack(anchor="w")
        self.status_log_window = scrolledtext.ScrolledText(right_log, width=80, height=8, font=("宋体", 10))
        self.status_log_window.pack(fill=tk.BOTH, expand=True)

        # 将 GUI 更新函数给控制器
        self.controller.update_ui = self._threadsafe_update

        # 初始日志（放入队列）
        self.logger.info("系统初始化完成，准备就绪。")

        # 周期刷新：从 logger 队列拉日志并写入 Tk 文本框
        self._schedule_drain_logs()

        # 初始绘图
        self._refresh(status_text="初始化完成")

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _row(self, parent, idx):
        f = tk.Frame(parent); f.pack(pady=1)
        tk.Label(f, text=f"{idx+1:02d}").pack(side=tk.LEFT, padx=6)
        x = tk.Entry(f, width=8); y = tk.Entry(f, width=8); z = tk.Entry(f, width=8)
        # 移除readonly状态，让输入框可以正常显示和更新内容
        # for e in (x,y,z): e.configure(state="readonly")
        x.pack(side=tk.LEFT); y.pack(side=tk.LEFT, padx=4); z.pack(side=tk.LEFT)
        return (x,y,z)

    # ——— 按钮事件 ———
    def _on_start(self):
        period_ms = max(30, int(self.period_var.get()))
        rate_mm_s = max(0.0, float(self.rate_var.get()))
        
        # 只通过MainController的set方法设置参数（它们内部会调用update_control_params）
        self.controller.set_period_ms(period_ms)
        self.controller.set_center_rate(rate_mm_s)
        self.controller.start_loop()
        self.logger.info(f"启动闭环：period={period_ms}ms, rate={rate_mm_s}mm/s")

    def _on_stop(self):
        self.controller.stop_loop(); self.logger.info("停止闭环。")

    def _on_emergency(self):
        self.controller.emergency_stop(); self.logger.error("⚠️ 急停已触发。")

    def _on_reset(self):
        self.controller.reset_all(); self.logger.info("系统重置完成。")

    def _open_serial_monitor(self):
        """打开串口监视器窗口"""
        if self.serial_monitor_window and self.serial_monitor_window.winfo_exists():
            # 如果窗口已存在，则置前显示
            self.serial_monitor_window.lift()
            self.serial_monitor_window.focus()
            return
        
        # 创建新的串口监视器窗口
        self.serial_monitor_window = tk.Toplevel(self.root)
        self.serial_monitor_window.title("串口监视器")
        self.serial_monitor_window.geometry("1000x600")
        
        # 创建TX和RX分离的窗口
        main_frame = tk.Frame(self.serial_monitor_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # TX窗口
        tx_frame = tk.Frame(main_frame)
        tx_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(tx_frame, text="发送 (TX)", font=("黑体", 12)).pack(anchor="w")
        self.serial_monitor_window.tx_window = scrolledtext.ScrolledText(
            tx_frame, width=60, height=25, font=("Consolas", 9)
        )
        self.serial_monitor_window.tx_window.pack(fill=tk.BOTH, expand=True)
        
        # RX窗口
        rx_frame = tk.Frame(main_frame)
        rx_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10,0))
        tk.Label(rx_frame, text="接收 (RX)", font=("黑体", 12)).pack(anchor="w")
        self.serial_monitor_window.rx_window = scrolledtext.ScrolledText(
            rx_frame, width=60, height=25, font=("Consolas", 9)
        )
        self.serial_monitor_window.rx_window.pack(fill=tk.BOTH, expand=True)
        
        # 控制按钮
        button_frame = tk.Frame(self.serial_monitor_window)
        button_frame.pack(fill=tk.X, padx=10, pady=(0,10))
        ttk.Button(button_frame, text="清空TX", command=lambda: self.serial_monitor_window.tx_window.delete(1.0, tk.END)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空RX", command=lambda: self.serial_monitor_window.rx_window.delete(1.0, tk.END)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空全部", command=self._clear_all_serial).pack(side=tk.LEFT, padx=5)
        
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
        
        # 优先使用传感器系统的最新数据更新显示
        try:
            sensor_state = self.controller.sensor.legs_state()
            sensor_z = sensor_state.get("z", [])
            sensor_xy = sensor_state.get("xy", [])
            
            # 如果传感器有数据，用传感器数据；否则用 LegUnit 数据
            if len(sensor_z) >= 12 and len(sensor_xy) >= 12:
                display_z = sensor_z
                display_xy = sensor_xy
            else:
                display_z = [l.z for l in self.legs]
                display_xy = [(l.x, l.y) for l in self.legs]
        except Exception:
            # 传感器数据获取失败，回退到 LegUnit 数据
            display_z = [l.z for l in self.legs]
            display_xy = [(l.x, l.y) for l in self.legs]
        
        # 获取各种中心点信息
        cz = sum(display_z[i] for i in [4,5,6,7]) / 4.0  # 实际中心Z
        
        # 获取实际中心XYZ（从传感器系统）
        try:
            actual_center = self.controller.sensor.estimate_center()
            actual_cx, actual_cy, actual_cz = actual_center
        except Exception:
            actual_cx, actual_cy, actual_cz = 0.0, 0.0, cz
        
        # 获取几何中心XYZ（从估计器）
        try:
            state = self.controller.estimator.estimate(self.legs, self.controller.sensor)
            geo_cx, geo_cy, geo_cz = state.center_x, state.center_y, state.center_z
        except Exception:
            geo_cx, geo_cy, geo_cz = 0.0, 0.0, cz
        
        # 获取目标中心Z
        tgt = getattr(self.controller.control, '_target_center_z', None)
        tgt_txt = f"{tgt:.0f}mm" if tgt is not None else "-"
        
        # 更新中心信息显示
        self.center_info_label.config(
            text=f"目标中心Z：{tgt_txt}  |  "
                 f"实际中心：X={actual_cx:.1f}, Y={actual_cy:.1f}, Z={actual_cz:.1f}mm  |  "
                 f"几何中心：X={geo_cx:.1f}, Y={geo_cy:.1f}, Z={geo_cz:.1f}mm"
        )

        # Z 柱状
        self.ax_z.clear(); self.ax_z.set_title("腿子Z轴高度"); self.ax_z.set_ylim(0,700)
        names = [l.name for l in self.legs]
        zvals = display_z
        bars = self.ax_z.bar(names, zvals, color='skyblue')
        for i,b in enumerate(bars):
            self.ax_z.text(b.get_x()+b.get_width()/2, b.get_height()+8, f"{zvals[i]:.0f}mm",
                           ha='center', va='bottom', fontsize=8)

        # XY坐标图（添加中心点显示）
        self.ax_xy.clear(); self.ax_xy.set_title("腿子XY坐标分布")
        self.ax_xy.set_xlabel("X (mm)"); self.ax_xy.set_ylabel("Y (mm)")
        self.ax_xy.grid(True); self.ax_xy.set_aspect('equal')
        
        # 画腿子位置
        xs = [xy[0] for xy in display_xy]; ys = [xy[1] for xy in display_xy]
        self.ax_xy.scatter(xs, ys, c='red', s=50, marker='o', label='腿子位置')
        
        # 标注腿子编号
        for i in range(12):
            self.ax_xy.text(xs[i], ys[i]+40, str(i+1), fontsize=9, ha='center')
        
        # 画对称腿对连线
        for i in range(0,12,2):
            self.ax_xy.plot([xs[i], xs[i+1]], [ys[i], ys[i+1]], color='gray', linestyle='--', alpha=0.5)

        # 画实际中心点（蓝色三角形）
        self.ax_xy.scatter([actual_cx], [actual_cy], c='blue', s=100, marker='^', 
                          label=f'实际中心 ({actual_cx:.1f}, {actual_cy:.1f})', edgecolors='black', linewidth=2)

        # 画几何中心点（绿色菱形）
        self.ax_xy.scatter([geo_cx], [geo_cy], c='green', s=100, marker='D', 
                          label=f'几何中心 ({geo_cx:.1f}, {geo_cy:.1f})', edgecolors='black', linewidth=2)

        # 添加图例
        self.ax_xy.legend(loc='upper right', fontsize=8)

        # 四角翘曲图
        self.ax_att.clear(); self.ax_att.set_title("四角翘曲高度（相对中心Z）")
        dzs = [display_z[i] - cz for i in [0,1,10,11]]
        self.ax_att.bar(["左前(1)", "左后(2)", "右后(11)", "右前(12)"], dzs, color='orange')
        self.ax_att.set_ylim(-100, 100)

        # 受力监测图
        self.ax_force.clear(); self.ax_force.set_title("腿子受力监测")
        try:
            forces = self.controller.sensor.latest_forces()
            force_vals = forces if len(forces) >= 12 else [getattr(l,"force",0.0) for l in self.legs]
        except Exception:
            force_vals = [getattr(l,"force",0.0) for l in self.legs]
        self.ax_force.bar(names, force_vals, color='green')
        self.ax_force.set_ylim(0, 150)

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
    app = GUIController(root, controller)
    root.mainloop()

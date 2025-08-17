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

        self.root.title("道岔腿子控制系统（周期闭环 + 串口监视器）")

        # 顶部
        top = tk.Frame(root); top.pack(fill=tk.X, pady=4)
        self.status_label = tk.Label(top, text="运行状态：初始化完成", font=("黑体", 14))
        self.status_label.pack(side=tk.LEFT, padx=10)
        self.center_info_label = tk.Label(top, text="目标中心Z：-  实际中心Z：-")
        self.center_info_label.pack(side=tk.LEFT, padx=10)

        # 控制区
        ctr = tk.Frame(root); ctr.pack(fill=tk.X, pady=4)
        tk.Label(ctr, text="控制周期(ms)：").pack(side=tk.LEFT)
        self.period_var = tk.IntVar(value=100); tk.Entry(ctr, textvariable=self.period_var, width=6).pack(side=tk.LEFT, padx=(0,10))
        tk.Label(ctr, text="中心下降速率(mm/s)：").pack(side=tk.LEFT)
        self.rate_var = tk.DoubleVar(value=20.0); tk.Entry(ctr, textvariable=self.rate_var, width=6).pack(side=tk.LEFT, padx=(0,10))
        ttk.Button(ctr, text="开始", command=self._on_start).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctr, text="停止", command=self._on_stop).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctr, text="急停", command=self._on_emergency).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctr, text="重置", command=self._on_reset).pack(side=tk.LEFT, padx=5)

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
        head = tk.Frame(wrap); head.pack()
        for i,t in enumerate(("腿子","X","Y","Z")):
            tk.Label(head, text=t).grid(row=0, column=i, padx=6)
        left = tk.Frame(wrap); right = tk.Frame(wrap)
        left.pack(side=tk.LEFT, padx=20); right.pack(side=tk.LEFT, padx=20)
        self.coord_entries = [None]*12
        for i in range(6):
            self.coord_entries[i] = self._row(left, i)
            self.coord_entries[i+6] = self._row(right, i+6)

        # 日志区
        logs = tk.Frame(root); logs.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        left_log = tk.Frame(logs); left_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(left_log, text="主日志").pack(anchor="w")
        self.log_window = scrolledtext.ScrolledText(left_log, width=80, height=8, font=("宋体", 10))
        self.log_window.pack(fill=tk.BOTH, expand=True)

        right_log = tk.Frame(logs); right_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6,0))
        tk.Label(right_log, text="串口监视器").pack(anchor="w")
        self.serial_window = scrolledtext.ScrolledText(right_log, width=80, height=8, font=("Consolas", 10))
        self.serial_window.pack(fill=tk.BOTH, expand=True)

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
        for e in (x,y,z): e.configure(state="readonly")
        x.pack(side=tk.LEFT); y.pack(side=tk.LEFT, padx=4); z.pack(side=tk.LEFT)
        return (x,y,z)

    # ——— 按钮事件 ———
    def _on_start(self):
        p = max(30, int(self.period_var.get())); r = max(0.0, float(self.rate_var.get()))
        self.controller.set_period_ms(p); self.controller.set_center_rate(r)
        self.controller.start_loop()
        self.logger.info(f"启动闭环：period={p}ms, rate={r}mm/s")

    def _on_stop(self):
        self.controller.stop_loop(); self.logger.info("停止闭环。")

    def _on_emergency(self):
        self.controller.emergency_stop(); self.logger.error("⚠️ 急停已触发。")

    def _on_reset(self):
        self.controller.reset_all(); self.logger.info("系统重置完成。")

    # ——— 线程安全 UI 更新入口 ———
    def _threadsafe_update(self, full_text, short_text):
        if self.root and self.root.winfo_exists():
            self.root.after(0, lambda: self._refresh(status_text=full_text))

    # ——— 定时从队列取日志并写入 Text（核心修复点） ———
    def _schedule_drain_logs(self):
        # 主日志
        while not self.logger.gui_queue.empty():
            s = self.logger.gui_queue.get_nowait()
            self.log_window.insert(tk.END, s+"\n"); self.log_window.see(tk.END)
        # 串口监视器
        while not self.logger.serial_queue.empty():
            s = self.logger.serial_queue.get_nowait()
            self.serial_window.insert(tk.END, s+"\n"); self.serial_window.see(tk.END)
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
        
        cz = sum(display_z[i] for i in [4,5,6,7]) / 4.0
        tgt = getattr(self.controller.control, '_target_center_z', None)
        tgt_txt = f"{tgt:.0f}mm" if tgt is not None else "-"
        self.center_info_label.config(text=f"目标中心Z：{tgt_txt}    实际中心Z：{cz:.0f}mm")

        # Z 柱状
        self.ax_z.clear(); self.ax_z.set_title("腿子Z轴高度"); self.ax_z.set_ylim(0,700)
        names = [l.name for l in self.legs]
        zvals = display_z
        bars = self.ax_z.bar(names, zvals, color='skyblue')
        for i,b in enumerate(bars):
            self.ax_z.text(b.get_x()+b.get_width()/2, b.get_height()+8, f"{zvals[i]:.0f}mm",
                           ha='center', va='bottom', fontsize=8)

        # XY
        self.ax_xy.clear(); self.ax_xy.set_title("腿子XY坐标分布")
        self.ax_xy.set_xlabel("X (mm)"); self.ax_xy.set_ylabel("Y (mm)")
        self.ax_xy.grid(True); self.ax_xy.set_aspect('equal')
        xs = [xy[0] for xy in display_xy]; ys = [xy[1] for xy in display_xy]
        self.ax_xy.scatter(xs, ys, c='red')
        for i in range(12):
            self.ax_xy.text(xs[i], ys[i]+40, str(i+1), fontsize=9, ha='center')
        for i in range(0,12,2):
            self.ax_xy.plot([xs[i], xs[i+1]], [ys[i], ys[i+1]], color='gray', linestyle='--')

        # 四角
        self.ax_att.clear(); self.ax_att.set_title("四角翘曲高度（相对中心Z）")
        dzs = [display_z[i] - cz for i in [0,1,10,11]]
        self.ax_att.bar(["左前(1)", "左后(2)", "右后(11)", "右前(12)"], dzs, color='orange')
        self.ax_att.set_ylim(-100, 100)

        # 受力（保持原逻辑，或也可从传感器系统获取）
        self.ax_force.clear(); self.ax_force.set_title("腿子受力监测")
        try:
            forces = self.controller.sensor.latest_forces()
            force_vals = forces if len(forces) >= 12 else [getattr(l,"force",0.0) for l in self.legs]
        except Exception:
            force_vals = [getattr(l,"force",0.0) for l in self.legs]
        self.ax_force.bar(names, force_vals, color='green')
        self.ax_force.set_ylim(0, 150)

        self.canvas.draw()
        # 输入框
        for i,(xe,ye,ze) in enumerate(self.coord_entries):
            # 输入框显示传感器实际值
            x_val, y_val = display_xy[i]
            z_val = display_z[i]
            for e,v in ((xe,x_val),(ye,y_val),(ze,z_val)):
                e.delete(0, tk.END)
                e.insert(0, f"{v:.1f}")

    def _on_close(self):
        try: self.controller.shutdown(); self.logger.info("窗口关闭，程序退出")
        except Exception: pass
        self.root.destroy(); sys.exit(0)

def start_gui(controller):
    root = tk.Tk()
    app = GUIController(root, controller)
    root.mainloop()

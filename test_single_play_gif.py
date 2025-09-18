#!/usr/bin/env python3
# test_single_play_gif.py
"""测试GIF动画只播放一次的功能"""

import tkinter as tk
from tkinter import ttk
import os
from PIL import Image, ImageTk
import sys

class SinglePlayGIFTest:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("GIF单次播放测试")
        self.root.geometry("900x700")
        
        # GIF相关变量
        self.gif_frames = {}
        self.current_gif_frames = []
        self.gif_frame_index = 0
        self.gif_animation_id = None
        self.gif_playing = False
        self.gif_has_played = False  # 关键标志：是否已播放过
        
        # 当前选中的腿子
        self.selected_leg_index = 0
        
        self.create_widgets()
        self.show_gif_first_frame(0)  # 默认显示腿子1的第一帧
    
    def create_widgets(self):
        """创建测试界面"""
        # 主框架
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧：GIF显示区域
        left_frame = tk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tk.Label(left_frame, text="GIF动画演示", font=("黑体", 18)).pack(pady=10)
        
        # GIF显示标签
        self.gif_label = tk.Label(left_frame, text="等待播放动画", 
                                 font=("宋体", 14), fg="gray",
                                 width=60, height=25, relief=tk.SUNKEN, bd=2)
        self.gif_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 状态显示
        self.status_label = tk.Label(left_frame, text="状态：未播放", 
                                    font=("宋体", 12), fg="blue")
        self.status_label.pack(pady=5)
        
        # 右侧：控制区域
        right_frame = tk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(20, 0))
        
        tk.Label(right_frame, text="控制测试", font=("黑体", 16)).pack(pady=10)
        
        # 腿子选择区域
        self.create_leg_selection(right_frame)
        
        # 移动按钮区域
        self.create_movement_buttons(right_frame)
        
        # 重置按钮
        reset_frame = tk.Frame(right_frame)
        reset_frame.pack(pady=20)
        
        ttk.Button(reset_frame, text="重置播放状态", 
                  command=self.reset_play_status, 
                  style="TButton").pack()
    
    def create_leg_selection(self, parent):
        """创建腿子选择按钮"""
        selection_frame = tk.Frame(parent, relief=tk.RAISED, bd=2)
        selection_frame.pack(pady=10, fill=tk.X)
        
        tk.Label(selection_frame, text="选择腿子", font=("黑体", 14)).pack(pady=5)
        
        buttons_frame = tk.Frame(selection_frame)
        buttons_frame.pack(pady=5)
        
        self.leg_buttons = []
        for i in range(6):  # 只测试前6个腿子
            btn = ttk.Button(buttons_frame, text=f"腿子{i+1}",
                           command=lambda idx=i: self.select_leg(idx),
                           width=8)
            btn.pack(side=tk.LEFT, padx=2)
            self.leg_buttons.append(btn)
        
        # 当前选中腿子显示
        self.current_leg_label = tk.Label(selection_frame, 
                                         text=f"当前：腿子1", 
                                         font=("宋体", 12), fg="green")
        self.current_leg_label.pack(pady=5)
    
    def create_movement_buttons(self, parent):
        """创建移动按钮"""
        movement_frame = tk.Frame(parent, relief=tk.RAISED, bd=2)
        movement_frame.pack(pady=10, fill=tk.X)
        
        tk.Label(movement_frame, text="移动控制", font=("黑体", 14)).pack(pady=5)
        
        # 创建移动按钮
        directions = [
            ("向上", "up"), ("向下", "down"), 
            ("向左", "left"), ("向右", "right"),
            ("升高", "up_z"), ("降低", "down_z")
        ]
        
        buttons_grid = tk.Frame(movement_frame)
        buttons_grid.pack(pady=5)
        
        for i, (text, direction) in enumerate(directions):
            row = i // 2
            col = i % 2
            btn = ttk.Button(buttons_grid, text=text,
                           command=lambda d=direction: self.move_leg(d),
                           width=8)
            btn.grid(row=row, column=col, padx=5, pady=2)
    
    def select_leg(self, leg_index):
        """选择腿子"""
        old_index = self.selected_leg_index
        self.selected_leg_index = leg_index
        
        # 重置播放状态（新腿子可以播放动画）
        self.gif_has_played = False
        
        # 更新显示
        self.current_leg_label.config(text=f"当前：腿子{leg_index+1}")
        self.status_label.config(text="状态：切换腿子，播放状态已重置", fg="blue")
        
        # 更新按钮样式
        for i, btn in enumerate(self.leg_buttons):
            if i == leg_index:
                btn.config(state="disabled")
            else:
                btn.config(state="normal")
        
        # 显示新腿子的第一帧
        self.show_gif_first_frame(leg_index)
        
        print(f"切换腿子: {old_index+1} -> {leg_index+1}, 播放状态已重置")
    
    def move_leg(self, direction):
        """移动腿子"""
        print(f"腿子{self.selected_leg_index+1} 执行 {direction} 移动")
        
        # 关键逻辑：仅在第一次点击时播放动画
        if not self.gif_has_played:
            self.start_gif_animation(self.selected_leg_index)
            self.gif_has_played = True
            self.status_label.config(text="状态：第一次点击，播放动画", fg="green")
            print(f"第一次点击移动按钮，开始播放腿子{self.selected_leg_index+1}的动画")
        else:
            self.status_label.config(text="状态：已播放过，不再重复播放", fg="orange")
            print(f"已播放过动画，本次点击不播放")
    
    def reset_play_status(self):
        """重置播放状态（用于测试）"""
        self.gif_has_played = False
        self.status_label.config(text="状态：播放状态已手动重置", fg="purple")
        print("手动重置播放状态")
    
    def load_gif_frames(self, leg_index):
        """加载GIF帧"""
        if leg_index in self.gif_frames:
            return self.gif_frames[leg_index]
        
        gif_files = {
            0: "1.Z轴降低100mm.gif", 1: "2.Z轴升高50mm.gif", 
            2: "3.X轴正方向5mm.gif", 3: "4.X轴负方向10mm.gif",
            4: "5.Y轴负方向5mm.gif", 5: "6.Y轴正方向15mm.gif"
        }
        
        if leg_index not in gif_files:
            return []
        
        try:
            gif_path = os.path.join("gif", gif_files[leg_index])
            if not os.path.exists(gif_path):
                return []
            
            frames = []
            gif = Image.open(gif_path)
            
            try:
                while True:
                    frame = gif.copy()
                    # 保持宽高比缩放
                    original_width, original_height = frame.size
                    max_width, max_height = 500, 350
                    scale_w = max_width / original_width
                    scale_h = max_height / original_height
                    scale = min(scale_w, scale_h)
                    new_width = int(original_width * scale)
                    new_height = int(original_height * scale)
                    frame = frame.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(frame)
                    frames.append(photo)
                    gif.seek(len(frames))
            except EOFError:
                pass
            
            self.gif_frames[leg_index] = frames
            return frames
            
        except Exception as e:
            print(f"加载GIF失败: {e}")
            return []
    
    def show_gif_first_frame(self, leg_index):
        """显示GIF第一帧"""
        self.stop_gif_animation()
        frames = self.load_gif_frames(leg_index)
        if frames:
            self.gif_label.config(image=frames[0])
            self.current_gif_frames = frames
    
    def start_gif_animation(self, leg_index):
        """开始播放GIF动画"""
        self.stop_gif_animation()
        
        frames = self.load_gif_frames(leg_index)
        if not frames:
            return
        
        self.current_gif_frames = frames
        self.gif_frame_index = 0
        self.gif_playing = True
        
        self.animate_gif()
    
    def animate_gif(self):
        """执行动画播放"""
        if not self.gif_playing or not self.current_gif_frames:
            return
        
        if self.gif_frame_index < len(self.current_gif_frames):
            self.gif_label.config(image=self.current_gif_frames[self.gif_frame_index])
            self.gif_frame_index += 1
            self.gif_animation_id = self.root.after(150, self.animate_gif)
        else:
            self.gif_playing = False
            self.status_label.config(text="状态：动画播放完成", fg="green")
            print("动画播放完成")
    
    def stop_gif_animation(self):
        """停止动画"""
        if self.gif_animation_id:
            self.root.after_cancel(self.gif_animation_id)
            self.gif_animation_id = None
        self.gif_playing = False
    
    def run(self):
        """运行测试"""
        try:
            # 初始化第一个腿子的按钮状态
            self.leg_buttons[0].config(state="disabled")
            self.root.mainloop()
        except KeyboardInterrupt:
            print("测试中断")

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    print("=== GIF单次播放测试 ===")
    print("测试逻辑：")
    print("1. 选择腿子时显示第一帧，播放状态重置")
    print("2. 第一次点击移动按钮时播放完整动画")
    print("3. 后续点击移动按钮不会重新播放动画")
    print("4. 切换到其他腿子时播放状态重置")
    print("=" * 30)
    
    if not os.path.exists("gif"):
        print("错误：gif目录不存在！")
        sys.exit(1)
    
    test = SinglePlayGIFTest()
    test.run()
#!/usr/bin/env python3
# test_gif_animation.py
"""测试GIF动画功能的简化脚本"""

import tkinter as tk
from tkinter import ttk
import os
from PIL import Image, ImageTk
import sys

class GIFTestWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("GIF动画测试")
        self.root.geometry("800x600")
        
        # GIF相关变量
        self.gif_frames = {}
        self.current_gif_frames = []
        self.gif_frame_index = 0
        self.gif_animation_id = None
        self.gif_playing = False
        
        self.create_widgets()
    
    def create_widgets(self):
        """创建测试界面"""
        # GIF显示标签
        self.gif_label = tk.Label(self.root, text="点击按钮测试GIF动画", 
                                 font=("宋体", 16), fg="gray",
                                 width=60, height=25, relief=tk.SUNKEN, bd=2)
        self.gif_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 按钮框架
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=20)
        
        # 创建6个测试按钮
        for i in range(6):
            btn = ttk.Button(button_frame, 
                           text=f"腿子{i+1}动画",
                           command=lambda idx=i: self.test_gif(idx))
            btn.pack(side=tk.LEFT, padx=5)
    
    def load_gif_frames(self, leg_index):
        """加载指定腿子的GIF帧"""
        if leg_index in self.gif_frames:
            return self.gif_frames[leg_index]
        
        # GIF文件路径映射
        gif_files = {
            0: "1.Z轴降低100mm.gif",  # 腿子1
            1: "2.Z轴升高50mm.gif",   # 腿子2
            2: "3.X轴正方向5mm.gif",  # 腿子3
            3: "4.X轴负方向10mm.gif", # 腿子4
            4: "5.Y轴负方向5mm.gif",  # 腿子5
            5: "6.Y轴正方向15mm.gif", # 腿子6
        }
        
        if leg_index not in gif_files:
            return []
        
        try:
            gif_path = os.path.join("gif", gif_files[leg_index])
            
            if not os.path.exists(gif_path):
                print(f"GIF文件不存在: {gif_path}")
                return []
            
            # 加载GIF的所有帧
            frames = []
            gif = Image.open(gif_path)
            
            try:
                while True:
                    # 调整图片大小以适应显示区域
                    frame = gif.copy()
                    frame = frame.resize((600, 400), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(frame)
                    frames.append(photo)
                    gif.seek(len(frames))  # 移动到下一帧
            except EOFError:
                pass  # 到达GIF末尾
            
            self.gif_frames[leg_index] = frames
            print(f"已加载腿子{leg_index+1}的GIF动画，共{len(frames)}帧")
            return frames
            
        except Exception as e:
            print(f"加载腿子{leg_index+1}的GIF失败: {e}")
            return []
    
    def test_gif(self, leg_index):
        """测试GIF动画播放"""
        print(f"测试腿子{leg_index+1}的GIF动画")
        
        self.stop_gif_animation()  # 停止当前动画
        
        frames = self.load_gif_frames(leg_index)
        if not frames:
            print(f"无法加载腿子{leg_index+1}的GIF动画")
            return
        
        self.current_gif_frames = frames
        self.gif_frame_index = 0
        self.gif_playing = True
        
        self.animate_gif()
        print(f"开始播放腿子{leg_index+1}的GIF动画")
    
    def animate_gif(self):
        """执行GIF动画播放"""
        if not self.gif_playing or not self.current_gif_frames:
            return
        
        if self.gif_frame_index < len(self.current_gif_frames):
            # 显示当前帧
            self.gif_label.config(image=self.current_gif_frames[self.gif_frame_index])
            self.gif_frame_index += 1
            
            # 缓慢播放：每帧间隔200ms
            self.gif_animation_id = self.root.after(200, self.animate_gif)
        else:
            # 动画播放完毕，停留在最后一帧
            self.gif_playing = False
            print("GIF动画播放完成，停留在最后一帧")
    
    def stop_gif_animation(self):
        """停止GIF动画"""
        if self.gif_animation_id:
            self.root.after_cancel(self.gif_animation_id)
            self.gif_animation_id = None
        self.gif_playing = False
    
    def run(self):
        """运行测试窗口"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("测试中断")

if __name__ == "__main__":
    # 确保在正确的目录中运行
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    print("启动GIF动画测试...")
    print("当前工作目录:", os.getcwd())
    
    # 检查gif目录是否存在
    if not os.path.exists("gif"):
        print("错误：gif目录不存在！")
        sys.exit(1)
    
    # 检查gif文件
    gif_files = [
        "1.Z轴降低100mm.gif",
        "2.Z轴升高50mm.gif", 
        "3.X轴正方向5mm.gif",
        "4.X轴负方向10mm.gif",
        "5.Y轴负方向5mm.gif",
        "6.Y轴正方向15mm.gif"
    ]
    
    missing_files = []
    for gif_file in gif_files:
        if not os.path.exists(os.path.join("gif", gif_file)):
            missing_files.append(gif_file)
    
    if missing_files:
        print(f"警告：以下GIF文件不存在: {missing_files}")
    else:
        print("所有GIF文件都存在，可以开始测试")
    
    # 启动测试窗口
    test_window = GIFTestWindow()
    test_window.run()
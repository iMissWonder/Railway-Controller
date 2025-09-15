#!/usr/bin/env python3
# test_single_leg_gui.py - 测试单腿控制界面
import tkinter as tk
from gui.gui_controller import GUIController

# 创建一个简单的模拟控制器用于测试
class MockController:
    def __init__(self):
        self.logger = self
        
        # 添加队列相关属性
        import queue
        self.gui_queue = queue.Queue()
        self.serial_queue = queue.Queue()
        
        # 模拟12个腿子的数据
        self.legs = []
        for i in range(12):
            leg = type('Leg', (), {})()
            leg.name = f"腿{i+1}"
            leg.x = 100 + (i % 6) * 400  # X坐标
            leg.y = 50 + (i // 6) * 250   # Y坐标
            leg.z = 500 + (i * 10)        # Z坐标
            leg.force = 95.0 + (i * 2)    # 受力
            self.legs.append(leg)
            
        # 模拟传感器系统
        self.sensor = self
        self._forces = [95.0 + (i * 2) for i in range(12)]
        
        # 模拟控制系统
        self.control = self
        self._target_center_z = 550.0
        self._initial_geometric_center = (1200.0, 175.0)
        
        # 模拟状态估计器
        self.estimator = self
        
        # 其他必要的属性
        self.update_ui = None
        
    def get_leg_data(self):
        return self.legs
        
    def latest_forces(self):
        return self._forces
        
    def estimate(self, legs, sensor):
        """模拟状态估计"""
        # 返回模拟的状态信息
        state = type('State', (), {})()
        state.center_xy = (1210.0, 180.0)  # 模拟当前几何中心
        state.center_z = 545.0  # 模拟当前Z中心
        return state
        
    def info(self, msg):
        print(f"INFO: {msg}")
        
    def error(self, msg):
        print(f"ERROR: {msg}")
        
    def set_period_ms(self, period):
        pass
        
    def set_center_rate(self, rate):
        pass
        
    def start_loop(self):
        pass
        
    def stop_loop(self):
        pass
        
    def emergency_stop(self):
        pass
        
    def reset_all(self):
        pass
        
    def shutdown(self):
        pass

def main():
    # 创建主窗口
    root = tk.Tk()
    
    # 创建模拟控制器
    controller = MockController()
    
    # 创建GUI控制器
    gui = GUIController(root, controller)
    
    print("单腿控制界面测试启动...")
    print("请点击右上角的'单腿控制'按钮测试功能")
    
    # 运行主循环
    root.mainloop()

if __name__ == "__main__":
    main()
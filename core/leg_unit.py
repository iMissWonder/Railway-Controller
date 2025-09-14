import random

class LegUnit:
    def __init__(self, id):
        self.id = id
        self.name = f"{str(id).zfill(2)}"
        self.x = 0.0
        self.y = 0.0
        self.z = 600.0
        self.force = 0.0
        self.status = "未初始化"

    def reset(self):
        # 使用固定的道岔腿子坐标配置
        self.status = "初始化"
        fixed_positions = [
            (0.0, 0.0),         # 腿子1
            (0.0, 171.7),       # 腿子2
            (489.9, 0.0),       # 腿子3
            (490.0, 182.3),     # 腿子4
            (969.9, 0.0),       # 腿子5
            (970.0, 197.1),     # 腿子6
            (1449.9, 0.0),      # 腿子7
            (1449.7, 223.1),    # 腿子8
            (1929.9, 0.0),      # 腿子9
            (1930.0, 262.6),    # 腿子10
            (2409.9, 0.0),      # 腿子11
            (2410.0, 311.6)     # 腿子12
        ]
        
        i = self.id - 1
        if 0 <= i < len(fixed_positions):
            self.x, self.y = fixed_positions[i]
        else:
            self.x, self.y = 0.0, 0.0

        self.z = 600 + random.uniform(-20, 20)
        self.force = 0.0

def create_legs(n=12):
    return [LegUnit(i + 1) for i in range(n)]

def generate_leg_positions(legs):
    # 使用固定的道岔腿子坐标配置
    fixed_positions = [
        (0.0, 0.0),         # 腿子1
        (0.0, 171.7),       # 腿子2
        (489.9, 0.0),       # 腿子3
        (490.0, 182.3),     # 腿子4
        (969.9, 0.0),       # 腿子5
        (970.0, 197.1),     # 腿子6
        (1449.9, 0.0),      # 腿子7
        (1449.7, 223.1),    # 腿子8
        (1929.9, 0.0),      # 腿子9
        (1930.0, 262.6),    # 腿子10
        (2409.9, 0.0),      # 腿子11
        (2410.0, 311.6)     # 腿子12
    ]

    # 直接使用固定坐标设置每个腿的位置
    for idx, leg in enumerate(legs):
        if idx < len(fixed_positions):
            leg.x, leg.y = fixed_positions[idx]
        else:
            leg.x, leg.y = 0.0, 0.0
        leg.z = 600 + random.uniform(-20, 20)
        leg.status = "初始化"
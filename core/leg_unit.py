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
        # 模拟道岔布置规则（XY、Z）
        self.status = "初始化"
        x_positions = [-8700, -8700, -6200, -6200, -3000, -3000,
                       0, 0, 3000, 3000, 6200, 6200]
        i = self.id - 1
        self.x = x_positions[i]

        base_upper_y = random.uniform(800, 900)
        gap_step = 1450 + (i // 2) * (2600 - 1450) / 5
        if i % 2 == 0:
            self.y = base_upper_y + random.uniform(-50, 50)
        else:
            self.y = base_upper_y - gap_step + random.uniform(-50, 50)

        self.z = 600 + random.uniform(-20, 20)
        self.force = 0.0

def create_legs(n=12):
    return [LegUnit(i + 1) for i in range(n)]

def generate_leg_positions(legs):
    import random
    # 生成 12 个腿子的 XY 坐标，符合道岔分布逻辑
    x_positions = [-8700, -8700, -6200, -6200, -3000, -3000,
                   0, 0, 3000, 3000, 6200, 6200]

    # 五个“奇数号腿子”Y差不多（控制在100mm内）
    base_upper_y = random.uniform(800, 900)
    upper_y_values = [base_upper_y + random.uniform(-50, 50) for _ in range(6)]

    # 逐步增大的间距，用于生成“偶数号腿子”
    gap_steps = [1450 + i * (2600 - 1450) / 5 for i in range(6)]

    for i in range(6):
        # 左边腿
        leg_left = legs[i * 2]
        leg_left.x = x_positions[i * 2]
        leg_left.y = upper_y_values[i]
        leg_left.z = 600 + random.uniform(-20, 20)
        leg_left.status = "初始化"

        # 右边腿
        leg_right = legs[i * 2 + 1]
        leg_right.x = x_positions[i * 2 + 1]
        leg_right.y = upper_y_values[i] - gap_steps[i]
        leg_right.z = 600 + random.uniform(-20, 20)
        leg_right.status = "初始化"
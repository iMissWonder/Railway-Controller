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
    x_positions = [-8700, -8700, -6200, -6200, -3000, -3000,
                   0, 0, 3000, 3000, 6200, 6200]

    base_upper_y = random.uniform(760, 820)
    upper_y_values = [base_upper_y + random.uniform(-40, 40) for _ in range(6)]
    gap_steps = [1450 + i * (2600 - 1450) / 5 for i in range(6)]

    tmp_xy = [(0.0, 0.0)] * 12
    for i in range(6):
        leg_left = legs[i * 2]
        leg_right = legs[i * 2 + 1]
        top_y = upper_y_values[i]
        bot_y = top_y - gap_steps[i] + random.uniform(-30, 30)
        tmp_xy[i * 2] = (x_positions[i * 2], top_y)
        tmp_xy[i * 2 + 1] = (x_positions[i * 2 + 1], bot_y)

    # 平移使1号腿成为(0,0)，并加入 ±5mm 微扰，Y 向下为正
    x0, y0 = tmp_xy[0]
    shift_x = -x0
    shift_y = -y0
    for idx, (x, y) in enumerate(tmp_xy):
        legs[idx].x = x + shift_x + random.uniform(-5.0, 5.0)
        legs[idx].y = -(y + shift_y) + random.uniform(-5.0, 5.0)
        legs[idx].z = 600 + random.uniform(-20, 20)
        legs[idx].status = "初始化"
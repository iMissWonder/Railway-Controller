# demo_use_comm.py
from comm import CommService, CMD
from comm.commands import dec_ack_status, enc_set_param

comm = CommService(port="COM4", baud=115200)
comm.start()
comm.wait_ready(2.0)

# 订阅设备上报（例：姿态推送 0xC1）
def on_push(cmd, payload):
    if cmd == 0xC1:
        print("PUSH pose len=", len(payload))
comm.subscribe(on_push)

# 例1：设置参数（快速/慢速下降高度）
ok, payload = comm.request(CMD.SET_PARAM, enc_set_param(seq=0, fast_mm=300, slow_mm=50), timeout=0.5, retry=2)
if ok:
    seq, status, data = dec_ack_status(payload)
    print("SET_PARAM status=", status)
else:
    print("SET_PARAM failed")

# 例2：急停
ok, payload = comm.request(CMD.EMERGENCY_STOP, b"\x00", timeout=0.3, retry=1)
print("ESTOP", ok)

# 结束
comm.stop()

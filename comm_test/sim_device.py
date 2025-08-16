# sim_device.py  —— 简易串口设备模拟器，挂在 COM5
# 依赖 comm/ 目录（用里面的封帧/解帧）
import time, math, threading
import serial
from comm.framer import encode_frame, Decoder
from comm.protocol import CMD

PORT = "COM5"
BAUD = 115200

def open_ser():
    s = serial.Serial(PORT, BAUD, timeout=0.05, write_timeout=0.2)
    try:
        s.setDTR(True); s.setRTS(True)
    except Exception:
        pass
    s.reset_input_buffer(); s.reset_output_buffer()
    return s

def send_frame(ser, cmd, payload=b""):
    ser.write(encode_frame(cmd, payload)); ser.flush()

def ack(ser, cmd, seq, status=0x00, data=b""):
    send_frame(ser, (cmd | 0x80) & 0xFF, bytes([seq & 0xFF, status]) + data)

def pose_push_loop(ser: serial.Serial, stop_evt: threading.Event):
    t0 = time.time()
    while not stop_evt.is_set():
        t = time.time() - t0
        # 伪造一个缓慢摆动的姿态：单位 0.01 度，int16
        roll  = int( 50 * math.sin(t))   # 0.50°
        pitch = int( 30 * math.cos(t))   # 0.30°
        yaw   = int( 10 * math.sin(0.5*t))
        payload = bytes([0x00, 0x00]) + roll.to_bytes(2, "little", signed=True) \
                                   + pitch.to_bytes(2, "little", signed=True) \
                                   + yaw.to_bytes(2, "little", signed=True)
        send_frame(ser, 0xC1, payload)  # PUSH
        time.sleep(0.2)

def main():
    ser = open_ser()
    dec = Decoder()
    stop_evt = threading.Event()
    th = threading.Thread(target=pose_push_loop, args=(ser, stop_evt), daemon=True)
    th.start()
    print(f"[SIM] Running on {PORT} @ {BAUD}. Waiting for frames...")

    try:
        while True:
            data = ser.read(256)
            if not data:
                continue
            frames = dec.feed(data)
            for fr in frames:
                cmd = fr.cmd
                pld = fr.payload
                seq = pld[0] if len(pld) else 0
                # 处理指令
                if cmd == CMD.PING:
                    ack(ser, cmd, seq)
                elif cmd == CMD.GET_VERSION:
                    ack(ser, cmd, seq, 0x00, b"\x01\x00")   # v1.0
                elif cmd == CMD.SET_PARAM:
                    # 这里可校验参数长度等；先直接OK
                    ack(ser, cmd, seq, 0x00)
                elif cmd == CMD.EMERGENCY_STOP:
                    ack(ser, cmd, seq, 0x00)
                else:
                    # 未识别命令 → 用通用错误码 0x01
                    ack(ser, cmd, seq, 0x01)
    except KeyboardInterrupt:
        pass
    finally:
        stop_evt.set()
        time.sleep(0.1)
        ser.close()
        print("[SIM] Stopped.")

if __name__ == "__main__":
    main()

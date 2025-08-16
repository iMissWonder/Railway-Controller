import serial, time

PORT = "COM5"  # 换成要测的那个
BAUD = 115200
payload = bytes.fromhex("55 AA 01 02 03 04")

with serial.Serial(PORT, BAUD, timeout=0.5, write_timeout=0.5) as ser:
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(payload)
    ser.flush()
    time.sleep(0.05)
    rx = ser.read(len(payload))
    print(f"TX: {payload.hex(' ').upper()}")
    print(f"RX: {rx.hex(' ').upper()}")
    print("OK" if rx == payload else "MISMATCH")

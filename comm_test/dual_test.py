import time, serial

def send_and_receive(port_tx, port_rx, baud=115200, payload=bytes.fromhex("55 AA 01 02 03 04")):
    with serial.Serial(port_tx, baud, timeout=0.5, write_timeout=0.5) as tx, \
         serial.Serial(port_rx, baud, timeout=0.5, write_timeout=0.5) as rx:
        rx.reset_input_buffer()
        rx.reset_output_buffer()
        tx.write(payload)
        tx.flush()
        time.sleep(0.05)
        data = rx.read(len(payload))
        return data

COM_A = "COM4"
COM_B = "COM5"

print(f"=== {COM_A} -> {COM_B} ===")
resp = send_and_receive(COM_A, COM_B)
print("RX:", resp.hex(" ").upper())

print(f"=== {COM_B} -> {COM_A} ===")
resp = send_and_receive(COM_B, COM_A)
print("RX:", resp.hex(" ").upper())

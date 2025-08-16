from serial.tools import list_ports

# CH340 常见硬件ID：VID_1A86 & PID_7523（也可能是 5523）
CH340_VID = 0x1A86
CH340_PID_SET = {0x7523, 0x5523}

ports = [p for p in list_ports.comports()
         if p.vid == CH340_VID and p.pid in CH340_PID_SET]

print("找到的 CH340 串口：", [p.device for p in ports])
port = ports[0].device if ports else None
print("首选端口：", port)

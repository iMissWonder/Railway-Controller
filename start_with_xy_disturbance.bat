@echo off
echo 启动Railway Controller系统（带XY扰动功能）
echo ===============================================

echo 正在启动模拟设备（带XY扰动）...
echo - 控制端口: COM1
echo - 遥测端口: COM3  
echo - XY扰动幅度: 3.0mm
echo - XY扰动频率: 0.3Hz

start "MockDevice" cmd /k "python -m hardware.mock_serial_device --ctrl-port COM1 --telem-port COM3 --xy-disturbance --disturbance-amplitude 3.0 --disturbance-frequency 0.3"

echo 等待模拟设备启动...
timeout /t 3 /nobreak > nul

echo 正在启动主控制器...
python main.py --driver serial --port COM1 --sensor serial --sensor-port COM3 --log-level INFO

pause

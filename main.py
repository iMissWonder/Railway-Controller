# main.py
import argparse
from core.logger import Logger
from core.main_controller import MainController
from gui.gui_controller import start_gui

def parse_args():
    p = argparse.ArgumentParser(description="道岔定位控制系统 - GUI 启动器")
    # 驱动（执行器）侧
    p.add_argument("--driver", choices=["mock", "serial"], default="mock",
                   help="执行器驱动：mock 或 serial")
    p.add_argument("--port", default='COM4', help="执行器串口号，例如 COM4（serial 模式必填）")
    p.add_argument("--baud", type=int, default=115200, help="执行器串口波特率")
    # 传感器侧（当前先用 mock，后续想从串口读遥测再开）
    p.add_argument("--sensor", choices=["mock", "serial"], default="mock",
                   help="传感器输入来源：mock 或 serial")
    p.add_argument("--sensor-port", default=None, help="传感器串口号，例如 COM6（如用 serial）")
    p.add_argument("--sensor-baud", type=int, default=115200, help="传感器串口波特率")
    # 日志级别
    p.add_argument("--log-level", choices=["DEBUG", "INFO", "WARN", "ERROR"], default="INFO")
    return p.parse_args()

def main():
    args = parse_args()

    # 统一 Logger（带主日志与串口监视器两个通道）
    logger = Logger(level=args.log_level)

    # 主控制器
    controller = MainController(
        logger=logger,
        gui_update_cb=None,
        driver_mode=args.driver,
        serial_port=args.port,
        baudrate=args.baud,
        sensor_mode=args.sensor,
        sensor_port=args.sensor_port,
        sensor_baud=args.sensor_baud,
    )

    # 启动 GUI
    start_gui(controller)

if __name__ == "__main__":
    main()

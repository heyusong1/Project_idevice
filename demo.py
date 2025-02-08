
import time
import logging
import subprocess


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

import subprocess
import logging
import signal
import sys

def check_device_connection():
    try:
        result = subprocess.run(
            ["tidevice", "wait-for-device"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2  # 设置超时时间
        )
        if result.returncode == 0:
            logging.info("设备已连接")
            return True
        else:
            logging.info("设备未连接，输出中未找到连接标志")
            return False
    except subprocess.TimeoutExpired:
        logging.info("设备连接超时，继续尝试...")
        return False
    except Exception as e:
        logging.error(f"发生未知错误: {e}")
        return False

def device_connections(max_retries=3):
    retry_count = 0

    def signal_handler(sig, frame):
        logging.info("收到中断信号，停止等待设备连接")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    while max_retries is None or retry_count < max_retries:
        if check_device_connection():
            return True
        retry_count += 1

    logging.warning("达到最大重试次数，设备仍未连接")
    return False


if __name__ == "__main__":
    device_connections()
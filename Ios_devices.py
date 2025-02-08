import re
import os
import sys
import signal
import queue
import logging
import subprocess
from pathlib import Path
from tidevice import Usbmux
from threading import Thread, Event

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 获取app包名
def pag_name():
    command = ["tidevice", "applist"]
    try:
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
            output, error = process.communicate()
            if error:
                return f"错误输出: {error}"
            packages = [package.strip() for package in output.split('\n') if package.strip()]
            return packages
    except Exception as e:
        return f"发生异常: {str(e)}"

# 获取设备信息
def device_connections():
    try:
        devices = Usbmux().device_list()
        return [
            {
                "udid": re.search(r"udid='([^']*)'", str(device)).group(1),
                "device_id": int(re.search(r"device_id=(\d+)", str(device)).group(1))
            } for device in devices if re.search(r"udid='([^']*)'", str(device)) and re.search(r"device_id=(\d+)", str(device))
        ]
    except Exception as e:
        logging.error(f"获取设备信息失败: {e}")
        return []

def device_connection():
    connected_info_output = False
    try:
        result = subprocess.run(
            ["tidevice", "wait-for-device"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout= 2  # 设置超时时间
        )
        if result.returncode == 0:
            if not connected_info_output:
                connected_info_output = True  # 标记已输出过“设备已连接”
            else:
                logging.info("重试连接已成功")
            return True
        else:
            logging.warning("设备未连接，输出中未找到连接标志")
            return False
    except subprocess.TimeoutExpired:
        logging.error("连接检测中.....")
        return False
    except Exception as e:
        logging.error(f"发生未知错误: {e}")
        return False
# 检查连接心跳
def check_device_connections(max_retries=3):
    retry_count = 0

    def signal_handler(sig, frame):
        logging.info("收到中断信号，停止等待设备连接")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    while max_retries is None or retry_count < max_retries:
        if device_connection():
            return True
        retry_count += 1

    logging.warning("达到最大重试次数，设备仍未连接")
    return False

# 获取设备udid
def device_udid():
    devices = device_connections()
    for data in devices:
        udid = data.get("udid")
        if udid:
            return udid
    return None

# 获取指定应用所有log
def get_app_logs(udid, app_bundle_id, keyword, log_queue, stop_event):
    command = ['tidevice', '-u', udid, 'syslog']
    process = None
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        while not stop_event.is_set():
            line = process.stdout.readline().decode('utf-8')
            if not line:
                break
            if app_bundle_id in line and keyword in line:
                log_queue.put(line.strip())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.error(f"获取日志时发生异常: {e}")
    finally:
        if process:
            process.terminate()
            process.wait()

# 将已获取的文件存储至本地文件
def log_file(udid, app_bundle_id, outwork):
    file_path = Path(os.path.abspath('your_file.txt'))
    log_queue = queue.Queue()
    stop_event = Event()
    writer_thread = None

    def write_logs_to_file():
        with file_path.open('a') as file:
            while not stop_event.is_set() or not log_queue.empty():
                try:
                    line = log_queue.get(timeout=3)
                    file.write(line + '\n')
                except queue.Empty:
                    break
                except Exception as e:
                    return "设备连接失败,请重新启动"

    try:
        if not check_device_connections():
            return "设备连接失败"
        else:
            writer_thread = Thread(target=write_logs_to_file)
            writer_thread.start()
            out_app_logs(udid, app_bundle_id, outwork, log_queue, stop_event)
            writer_thread.join()
    finally:
        stop_event.set()
        if writer_thread and writer_thread.is_alive():
            writer_thread.join()
    return "设备连接失败,请重新启动"

# 获取已过滤后的log
def out_app_logs(udid, app_bundle_id, outwork, log_queue, stop_event):
    log_thread = Thread(target=get_app_logs, args=(udid, app_bundle_id, '', log_queue, stop_event))
    log_thread.start()
    try:
        while not stop_event.is_set():
            if not log_queue.empty():
                line = log_queue.get()
                if outwork in line:
                    logging.info(f" log: {line}")
    except KeyboardInterrupt:
        return "设备连接失败,请重新启动"
    finally:
        stop_event.set()
        log_thread.join()

# 开始运行
def run(package_name, key):
    logging.info("开始运行")
    if check_device_connections():
        udid = device_udid()
        if udid:
            app_bundle_id = package_name
            outwork = key
            logging.info("开始获取日志")
            log_file(udid, app_bundle_id, outwork)
        else:
            logging.error("No device connected or UDID not found.")
    else:
        logging.error("设备连接失败")

if __name__ == "__main__":
    run('com.meevii.bibleConnect', 'user')

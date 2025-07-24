import socket
import os
import struct
import time
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('udp_transfer.log', mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_target_ips_from_file(file_name='ip.txt'):
    """从同文件夹的ip.txt中读取目标IP列表"""
    ips = []
    if not os.path.exists(file_name):
        logger.warning(f"未找到 {file_name} 文件，将使用空IP列表")
        return ips
    
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            for line in f:
                ip = line.strip()
                if ip:
                    ips.append(ip)
        logger.info(f"从 {file_name} 成功读取 {len(ips)} 个目标IP")
    except Exception as e:
        logger.error(f"读取 {file_name} 时出错: {e}")
    return ips

def get_target_port_from_file(file_name='port.txt'):
    """从同文件夹的port.txt中读取端口号"""
    default_port = 6600
    if not os.path.exists(file_name):
        logger.warning(f"未找到 {file_name} 文件，将使用默认端口 {default_port}")
        return default_port
    
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            port_str = f.readline().strip()
            if not port_str:
                logger.warning(f"{file_name} 内容为空，将使用默认端口 {default_port}")
                return default_port
            
            port = int(port_str)
            if 1 <= port <= 65535:
                logger.info(f"从 {file_name} 成功读取端口: {port}")
                return port
            else:
                logger.warning(f"{file_name} 中的端口号无效，将使用默认端口 {default_port}")
                return default_port
    except ValueError:
        logger.warning(f"{file_name} 中的内容不是有效的端口号，将使用默认端口 {default_port}")
    except Exception as e:
        logger.error(f"读取 {file_name} 时出错: {e}，将使用默认端口 {default_port}")
    return default_port

def get_all_files_recursive(root_dir):
    """非递归方式获取目录下所有文件（包括子文件夹中的文件）"""
    all_files = []
    excluded = {'udp_push_v4.exe', 'ip.txt', 'port.txt','udp_transfer.log', os.path.basename(__file__)}
    
    stack = [root_dir]
    while stack:
        current_dir = stack.pop()
        for entry in os.scandir(current_dir):
            if entry.name in excluded:
                continue
            if entry.is_file():
                rel_path = os.path.relpath(entry.path, root_dir)
                all_files.append((entry.path, rel_path))
            elif entry.is_dir():
                stack.append(entry.path)
    
    return all_files

def wait_for_ack(client_socket, expected_ack, timeout=5):
    """等待接收端的ACK消息"""
    client_socket.settimeout(timeout)
    try:
        data, addr = client_socket.recvfrom(1024)
        received_ack = data.decode('utf-8')
        if received_ack.startswith(expected_ack):
            logger.info(f"收到ACK: {received_ack} 从 {addr}")
            return True
        else:
            logger.warning(f"收到意外的ACK: {received_ack}，期望: {expected_ack}")
            return False
    except socket.timeout:
        logger.warning(f"等待 {expected_ack} 超时")
        return False
    except Exception as e:
        logger.error(f"等待ACK时出错: {e}")
        return False
    finally:
        client_socket.settimeout(None)

def send_all_files(save_dir):
    target_ips = get_target_ips_from_file()
    target_port = get_target_port_from_file()
    
    if not target_ips:
        logger.error("没有可用的目标IP，无法发送文件")
        return

    root_dir = os.getcwd()
    all_files = get_all_files_recursive(root_dir)
    
    if not all_files:
        logger.warning("未找到可发送的文件（包括子文件夹）")
        return
    logger.info(f"共发现 {len(all_files)} 个可发送文件（包括子文件夹）")

    total_ips = len(target_ips)
    
    for ip_index, target_ip in enumerate(target_ips, 1):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        addr = (target_ip, target_port)

        logger.info(f"开始给第 {ip_index}/{total_ips} 台电脑发送文件: {target_ip}")

        try:
            # 1. 发送保存根目录并等待ACK
            dir_bytes = save_dir.encode('utf-8')
            dir_header = struct.pack('!I', len(dir_bytes)) + dir_bytes
            client_socket.sendto(dir_header, addr)
            logger.info(f"[{target_ip}:{target_port}] 已发送保存根目录: {save_dir}")
            if not wait_for_ack(client_socket, "DIR_ACK"):
                logger.warning(f"[{target_ip}:{target_port}] 未收到DIR_ACK，终止发送")
                client_socket.close()
                continue

            # 2. 发送文件总数并等待ACK
            file_count = len(all_files)
            client_socket.sendto(struct.pack('!I', file_count), addr)
            logger.info(f"[{target_ip}:{target_port}] 已发送文件总数: {file_count}")
            if not wait_for_ack(client_socket, "COUNT_ACK"):
                logger.warning(f"[{target_ip}:{target_port}] 未收到COUNT_ACK，终止发送")
                client_socket.close()
                continue

            # 3. 逐个发送文件
            total_files = len(all_files)
            for file_index, (file_path, rel_path) in enumerate(all_files, 1):
                logger.info(f"开始给第 {ip_index}/{total_ips} 台电脑发送第 {file_index}/{total_files} 个文件: {rel_path}")
                
                try:
                    file_size = os.path.getsize(file_path)
                    rel_path_bytes = rel_path.encode('utf-8')
                    header = struct.pack('!I', len(rel_path_bytes)) + rel_path_bytes + struct.pack('!Q', file_size)
                    client_socket.sendto(header, addr)
                    logger.info(f"[{target_ip}:{target_port}] 开始发送: {rel_path}（{file_size} 字节）")
                    if not wait_for_ack(client_socket, "HEADER_ACK"):
                        logger.warning(f"[{target_ip}:{target_port}] 未收到HEADER_ACK，跳过文件 {rel_path}")
                        continue

                    # 发送文件内容
                    bytes_sent = 0
                    start_time = time.time()
                    with open(file_path, 'rb') as f:
                        while bytes_sent < file_size:
                            data = f.read(65507)
                            if not data:
                                break
                            client_socket.sendto(data, addr)
                            expected_ack = f"DATA_ACK:{len(data)}"
                            if not wait_for_ack(client_socket, expected_ack):
                                logger.warning(f"[{target_ip}:{target_port}] 未收到DATA_ACK，终止文件 {rel_path}")
                                break
                            bytes_sent += len(data)
                            progress = (bytes_sent / file_size) * 100
                            elapsed = time.time() - start_time
                            speed = bytes_sent / elapsed / 1024 if elapsed > 0 else 0
                            # 进度打印仍使用 print 以支持动态更新
                            print(f"\r第 {ip_index}/{total_ips} 台电脑发送第 {file_index}/{total_files} 个文件 [{target_ip}:{target_port}], 进度: {progress:.2f}%, 速度: {speed:.2f} KB/s", end='')
                    
                    print()  # 换行以结束进度打印
                    logger.info(f"[{target_ip}:{target_port}] 文件内容发送完成: {rel_path}")
                    if bytes_sent < file_size:
                        continue

                    # 等待文件完成ACK
                    if not wait_for_ack(client_socket, "FILE_COMPLETE"):
                        logger.warning(f"[{target_ip}:{target_port}] 未收到FILE_COMPLETE，跳过文件 {rel_path}")
                        continue

                    # 等待处理完成ACK
                    if not wait_for_ack(client_socket, "PROCESS_COMPLETE"):
                        logger.warning(f"[{target_ip}:{target_port}] 未收到PROCESS_COMPLETE，跳过文件 {rel_path}")
                        continue

                    logger.info(f"[{target_ip}:{target_port}] 文件传输完成: {rel_path}")

                except Exception as e:
                    logger.error(f"[{target_ip}:{target_port}] 发送 {rel_path} 失败: {e}")
                    continue

            logger.info(f"第 {ip_index}/{total_ips} 台电脑 {target_ip} 所有文件发送完毕")

        except Exception as e:
            logger.error(f"[{target_ip}:{target_port}] 发送过程中发生错误: {e}")
        finally:
            client_socket.close()

if __name__ == "__main__":
    save_dir = os.path.abspath('.')
    logger.info("开始文件传输程序")
    send_all_files(save_dir)
    logger.info("文件传输程序结束")
    input("按回车键退出...")    
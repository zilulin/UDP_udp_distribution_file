import socket
import os
import struct
import time
import ctypes
import logging

def setup_logger():
    """配置日志记录器"""
    logger = logging.getLogger('file_receiver')
    logger.setLevel(logging.INFO)
    
    file_handler = logging.FileHandler('file_receiver.log', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger()

def hide_console():
    """隐藏当前CMD窗口"""
    try:
        ctypes.windll.user32.ShowWindow(
            ctypes.windll.kernel32.GetConsoleWindow(),
            0
        )
    except Exception as e:
        logger.error(f"隐藏窗口失败: {e}")

def get_target_port_from_file(file_name='port_receive.txt'):
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

def receive_file():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target_port = get_target_port_from_file()
    server_address = ('', target_port)
    server_socket.bind(server_address)
    logger.info(f"正在监听UDP端口 {server_address[1]}...")
    time.sleep(5)  # 等待端口绑定稳定
    hide_console()
    try:
        while True:
            # 1. 接收保存根目录地址
            logger.info("等待接收保存根目录...")
            dir_header, client_address = server_socket.recvfrom(4096)
            if not dir_header or len(dir_header) < 4:
                logger.error("未收到有效目录信息，退出。")
                return
            
            # 发送目录头接收确认
            server_socket.sendto(b"DIR_ACK", client_address)
            logger.info(f"发送目录头接收确认到 {client_address}")

            dir_len = struct.unpack('!I', dir_header[:4])[0]
            root_dir = dir_header[4:4+dir_len].decode('utf-8')
            logger.info(f"保存根目录: {root_dir}")
            os.makedirs(root_dir, exist_ok=True)

            # 2. 接收文件总数
            file_count_data, _ = server_socket.recvfrom(4)
            server_socket.sendto(b"COUNT_ACK", client_address)
            logger.info(f"发送文件总数接收确认到 {client_address}")
            
            total_files = struct.unpack('!I', file_count_data)[0]
            logger.info(f"预计接收 {total_files} 个文件（包括子文件夹）")
            received_count = 0

            # 3. 循环接收所有文件
            while received_count < total_files:
                # 接收文件头
                header_data, _ = server_socket.recvfrom(4096)
                server_socket.sendto(b"HEADER_ACK", client_address)
                logger.info(f"发送文件头接收确认到 {client_address}")

                rel_path_len = struct.unpack('!I', header_data[:4])[0]
                rel_path_bytes = header_data[4:4+rel_path_len]
                rel_path = rel_path_bytes.decode('utf-8')
                file_size = struct.unpack('!Q', header_data[4+rel_path_len:4+rel_path_len+8])[0]

                save_path = os.path.join(root_dir, rel_path)
                save_dir = os.path.dirname(save_path)
                os.makedirs(save_dir, exist_ok=True)

                logger.info(f"接收到文件: {rel_path}, 大小: {file_size} 字节")
                temp_path = save_path + '.part'

                if os.path.exists(save_path):
                    try:
                        os.remove(save_path)
                        logger.info(f"已删除同名文件: {save_path}")
                    except Exception as e:
                        logger.warning(f"删除同名文件失败: {e}，将尝试覆盖")

                # 接收文件内容
                with open(temp_path, 'wb') as file:
                    bytes_received = 0
                    start_time = time.time()
                    while bytes_received < file_size:
                        packet, _ = server_socket.recvfrom(65507)
                        packet_size = len(packet)
                        file.write(packet)
                        bytes_received += len(packet)
                        
                        # 发送数据包大小确认
                        ack_message = f"DATA_ACK:{packet_size}".encode('utf-8')
                        server_socket.sendto(ack_message, client_address)
                        logger.info(f"发送数据包大小确认: {packet_size} 字节到 {client_address}")
                        
                        progress = (bytes_received / file_size) * 100
                        elapsed = time.time() - start_time
                        speed = bytes_received / elapsed / 1024 if elapsed > 0 else 0
                        print(f"\r[{received_count+1}/{total_files}] 进度: {progress:.2f}%, 速度: {speed:.2f} KB/s", end='')

                    print("\n文件接收完成")
                    logger.info(f"文件 {rel_path} 接收完成")

                # 发送文件完成确认
                server_socket.sendto(b"FILE_COMPLETE", client_address)
                logger.info(f"发送文件完成确认到 {client_address}")

                os.rename(temp_path, save_path)
                logger.info(f"文件已保存至: {save_path}")
                received_count += 1

                # 发送处理完成确认
                server_socket.sendto(b"PROCESS_COMPLETE", client_address)
                logger.info(f"发送处理完成确认到 {client_address}")

            logger.info(f"所有 {received_count}/{total_files} 个文件接收完成")

    except KeyboardInterrupt:
        logger.info("\n程序被用户中断")
    except Exception as e:
        logger.error(f"发生未知错误: {e}")
    finally:
        server_socket.close()
        logger.info("服务器已关闭")

if __name__ == "__main__":
    receive_file()
import socket
import os
import struct
import time
import ctypes  # 用于隐藏窗口
import logging  # 导入日志模块

def setup_logger():
    """配置日志记录器"""
    logger = logging.getLogger('file_receiver')
    logger.setLevel(logging.INFO)
    
    # 创建文件处理器
    file_handler = logging.FileHandler('file_receiver.log', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 创建日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器到日志器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 初始化日志器
logger = setup_logger()

def hide_console():
    """隐藏当前CMD窗口"""
    try:
        ctypes.windll.user32.ShowWindow(
            ctypes.windll.kernel32.GetConsoleWindow(),
            0  # 0表示隐藏窗口
        )
    except Exception as e:
        logger.error(f"隐藏窗口失败: {e}")


def get_target_port_from_file(file_name='port_receive.txt'):
    """从同文件夹的port.txt中读取端口号"""
    default_port = 6600  # 默认端口
    if not os.path.exists(file_name):
        logger.warning(f"未找到 {file_name} 文件，将使用默认端口 {default_port}")
        return default_port
    
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            port_str = f.readline().strip()
            if not port_str:  # 空文件
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

    try:
        while True:
            # 1. 接收保存根目录地址
            logger.info("等待接收保存根目录...")
            dir_header, client_address = server_socket.recvfrom(4096)
            if not dir_header or len(dir_header) < 4:
                logger.error("未收到有效目录信息，退出。")
                return
            dir_len = struct.unpack('!I', dir_header[:4])[0]
            root_dir = dir_header[4:4+dir_len].decode('utf-8')
            logger.info(f"保存根目录: {root_dir}")
            os.makedirs(root_dir, exist_ok=True)

            # 2. 接收文件总数（4字节整数）
            file_count_data, _ = server_socket.recvfrom(4)
            total_files = struct.unpack('!I', file_count_data)[0]
            logger.info(f"预计接收 {total_files} 个文件（包括子文件夹）")
            received_count = 0

            # 3. 循环接收所有文件
            while received_count < total_files:
                # 接收文件头（包含相对路径和文件大小）
                header_data, _ = server_socket.recvfrom(4096)

                # 解析文件头：相对路径长度(4字节) + 相对路径 + 文件大小(8字节)
                rel_path_len = struct.unpack('!I', header_data[:4])[0]
                rel_path_bytes = header_data[4:4+rel_path_len]
                rel_path = rel_path_bytes.decode('utf-8')  # 相对路径（含子文件夹）
                file_size = struct.unpack('!Q', header_data[4+rel_path_len:4+rel_path_len+8])[0]

                # 构建完整保存路径
                save_path = os.path.join(root_dir, rel_path)
                # 创建文件所在的子文件夹（如果不存在）
                save_dir = os.path.dirname(save_path)
                os.makedirs(save_dir, exist_ok=True)

                logger.info(f"接收到文件: {rel_path}, 大小: {file_size} 字节")
                temp_path = save_path + '.part'

                # 若存在同名文件则删除
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
                        file.write(packet)
                        bytes_received += len(packet)
                        
                        # 显示进度
                        progress = (bytes_received / file_size) * 100
                        elapsed = time.time() - start_time
                        speed = bytes_received / elapsed / 1024 if elapsed > 0 else 0
                        print(f"\r[{received_count+1}/{total_files}] 进度: {progress:.2f}%, 速度: {speed:.2f} KB/s", end='')
                    print("\n文件接收完成")
                    logger.info(f"文件 {rel_path} 接收完成")

                # 重命名临时文件
                os.rename(temp_path, save_path)
                logger.info(f"文件已保存至: {save_path}")
                received_count += 1

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
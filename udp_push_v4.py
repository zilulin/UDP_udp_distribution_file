import socket
import os
import struct
import time
from pathlib import Path  # 用于便捷处理路径

# 定义分块大小（减去头部开销）
CHUNK_SIZE = 65500  # 留出空间给UDP头部

def get_target_ips_from_file(file_name='ip.txt'):
    """从同文件夹的ip.txt中读取目标IP列表"""
    ips = []
    if not os.path.exists(file_name):
        print(f"警告：未找到 {file_name} 文件，将使用空IP列表")
        return ips
    
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            for line in f:
                ip = line.strip()
                if ip:  # 跳过空行
                    ips.append(ip)
        print(f"从 {file_name} 成功读取 {len(ips)} 个目标IP")
    except Exception as e:
        print(f"读取 {file_name} 时出错: {e}")
    return ips

def get_target_port_from_file(file_name='port.txt'):
    """从同文件夹的port.txt中读取端口号"""
    default_port = 6600  # 默认端口
    if not os.path.exists(file_name):
        print(f"警告：未找到 {file_name} 文件，将使用默认端口 {default_port}")
        return default_port
    
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            port_str = f.readline().strip()
            if not port_str:  # 空文件
                print(f"{file_name} 内容为空，将使用默认端口 {default_port}")
                return default_port
            
            port = int(port_str)
            if 1 <= port <= 65535:
                print(f"从 {file_name} 成功读取端口: {port}")
                return port
            else:
                print(f"{file_name} 中的端口号无效，将使用默认端口 {default_port}")
                return default_port
    except ValueError:
        print(f"{file_name} 中的内容不是有效的端口号，将使用默认端口 {default_port}")
    except Exception as e:
        print(f"读取 {file_name} 时出错: {e}，将使用默认端口 {default_port}")
    return default_port

def get_all_files_recursive(root_dir):
    """非递归方式获取目录下所有文件（包括子文件夹中的文件）"""
    all_files = []
    # 排除的文件和文件夹（可根据需要修改）
    excluded = {'udp_push_v4.exe', 'ip.txt', 'port.txt', os.path.basename(__file__)}
    
    # 用栈存储待处理的目录路径（初始时压入根目录）
    stack = [root_dir]
    
    while stack:
        # 弹出栈顶目录进行处理
        current_dir = stack.pop()
        
        # 遍历当前目录下的所有条目
        for entry in os.scandir(current_dir):
            # 跳过排除项
            if entry.name in excluded:
                continue
            
            if entry.is_file():
                # 计算文件相对根目录的路径
                rel_path = os.path.relpath(entry.path, root_dir)
                all_files.append((entry.path, rel_path))
            elif entry.is_dir():
                # 子文件夹压入栈，后续处理
                stack.append(entry.path)
    
    return all_files

def send_long_path(sock, addr, path_bytes):
    """分块发送长路径（支持超过单个UDP包大小的路径）"""
    total_len = len(path_bytes)
    # 发送总长度（使用8字节无符号整数）
    sock.sendto(struct.pack('!Q', total_len), addr)
    
    # 分块发送路径数据
    chunks_sent = 0
    for i in range(0, total_len, CHUNK_SIZE):
        chunk = path_bytes[i:i+CHUNK_SIZE]
        # 发送块序号和块数据
        chunk_header = struct.pack('!I', chunks_sent)
        sock.sendto(chunk_header + chunk, addr)
        chunks_sent += 1
        # 短暂延时，避免网络拥塞
        time.sleep(0.001)
    
    # 发送结束标记（使用无符号整数最大值表示结束）
    sock.sendto(struct.pack('!I', 0xFFFFFFFF), addr)  # 修改这里
    return chunks_sent

def send_all_files(save_dir):
    # 从文件获取配置
    target_ips = get_target_ips_from_file()
    target_port = get_target_port_from_file()
    
    if not target_ips:
        print("没有可用的目标IP，无法发送文件")
        return

    # 获取当前目录下所有文件（包括子文件夹）
    root_dir = os.getcwd()  # 程序所在目录
    all_files = get_all_files_recursive(root_dir)
    
    if not all_files:
        print("未找到可发送的文件（包括子文件夹）")
        return
    print(f"共发现 {len(all_files)} 个可发送文件（包括子文件夹）")

    for target_ip in target_ips:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        addr = (target_ip, target_port)

        # 1. 发送保存根目录（使用分块发送）
        dir_bytes = save_dir.encode('utf-8')
        print(f"[{target_ip}:{target_port}] 开始发送保存根目录（{len(dir_bytes)} 字节）")
        chunks = send_long_path(client_socket, addr, dir_bytes)
        print(f"[{target_ip}:{target_port}] 保存根目录发送完成，共 {chunks} 块")

        # 2. 发送文件总数（用于接收端确认）
        file_count = len(all_files)
        client_socket.sendto(struct.pack('!I', file_count), addr)
        print(f"[{target_ip}:{target_port}] 已发送文件总数: {file_count}")

        # 3. 逐个发送文件
        for file_path, rel_path in all_files:
            try:
                file_size = os.path.getsize(file_path)
                # 发送文件相对路径（使用分块发送）
                rel_path_bytes = rel_path.encode('utf-8')
                print(f"[{target_ip}:{target_port}] 开始发送文件头: {rel_path}（{file_size} 字节）")
                
                # 先发送文件大小
                client_socket.sendto(struct.pack('!Q', file_size), addr)
                
                # 再发送文件路径
                path_chunks = send_long_path(client_socket, addr, rel_path_bytes)
                print(f"[{target_ip}:{target_port}] 文件路径发送完成，共 {path_chunks} 块")

                # 发送文件内容
                with open(file_path, 'rb') as f:
                    bytes_sent = 0
                    chunks_sent = 0
                    while bytes_sent < file_size:
                        data = f.read(CHUNK_SIZE)
                        if not data:
                            break
                        # 发送块序号和数据
                        chunk_header = struct.pack('!I', chunks_sent)
                        client_socket.sendto(chunk_header + data, addr)
                        bytes_sent += len(data)
                        chunks_sent += 1
                        # 每100个块短暂延时，避免网络拥塞
                        if chunks_sent % 100 == 0:
                            time.sleep(0.01)
                
                print(f"[{target_ip}:{target_port}] 发送完成: {rel_path}（{chunks_sent} 个数据块）")
                # 文件间间隔，避免拥塞
                time.sleep(0.05)

            except Exception as e:
                print(f"[{target_ip}:{target_port}] 发送 {rel_path} 失败: {e}")
                continue

        # 4. 发送结束信号
        client_socket.sendto(b'end_work', addr)
        print(f"[{target_ip}:{target_port}] 所有文件发送完毕")
        client_socket.close()

if __name__ == "__main__":
    save_dir = os.path.abspath('.')
    send_all_files(save_dir)
    input("按回车键退出...")
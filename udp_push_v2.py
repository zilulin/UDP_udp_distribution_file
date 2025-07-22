import socket
import os
import struct
import time

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
            # 读取第一行并转换为整数
            port_str = f.readline().strip()
            if not port_str:  # 空文件
                print(f"{file_name} 内容为空，将使用默认端口 {default_port}")
                return default_port
            
            port = int(port_str)
            # 验证端口有效性（1-65535）
            if 1 <= port <= 65535:
                print(f"从 {file_name} 成功读取端口: {port}")
                return port
            else:
                print(f"{file_name} 中的端口号无效（必须在1-65535之间），将使用默认端口 {default_port}")
                return default_port
    except ValueError:
        print(f"{file_name} 中的内容不是有效的端口号，将使用默认端口 {default_port}")
    except Exception as e:
        print(f"读取 {file_name} 时出错: {e}，将使用默认端口 {default_port}")
    return default_port

def send_all_files(save_dir):
    # 从文件获取配置
    target_ips = get_target_ips_from_file()
    target_port = get_target_port_from_file()
    
    if not target_ips:
        print("没有可用的目标IP，无法发送文件")
        return

    for target_ip in target_ips:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        addr = (target_ip, target_port)

        # 1. 发送保存目录
        dir_bytes = save_dir.encode('utf-8')
        dir_header = struct.pack('!I', len(dir_bytes)) + dir_bytes
        client_socket.sendto(dir_header, addr)
        print(f"[{target_ip}:{target_port}] 已发送保存目录: {save_dir}")

        # 2. 发送当前目录下所有文件
        for file_name in os.listdir('.'):
            if os.path.isfile(file_name) and file_name not in [
                'udp_push_v2.exe', 
                'ip.txt',
                'port.txt',  # 新增排除port.txt
                os.path.basename(__file__)
            ]:
                file_size = os.path.getsize(file_name)
                name_bytes = file_name.encode('utf-8')
                header = struct.pack('!I', len(name_bytes)) + name_bytes + struct.pack('!Q', file_size)
                client_socket.sendto(header, addr)
                print(f"[{target_ip}:{target_port}] 开始发送文件: {file_name} ({file_size} 字节)")

                with open(file_name, 'rb') as f:
                    while True:
                        data = f.read(65507)
                        if not data:
                            break
                        client_socket.sendto(data, addr)
                        time.sleep(0.01)  # 缓解丢包

                print(f"[{target_ip}:{target_port}] 文件发送完成: {file_name}")
                time.sleep(0.1)

        # 3. 发送结束信号
        client_socket.sendto(b'end_work', addr)
        print(f"[{target_ip}:{target_port}] 已发送 end_work，所有文件发送完毕。")
        client_socket.close()

if __name__ == "__main__":
    save_dir = os.path.abspath('.')
    send_all_files(save_dir)
    input("按回车键退出...")
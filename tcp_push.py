import socket
import os
import struct

def send_all_files(target_ips, target_port, save_dir):
    for target_ip in target_ips:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((target_ip, target_port))
            print(f"[{target_ip}] 已连接，准备发送...")

            # 通讯确认
            client_socket.sendall(b'HELLO')
            resp = client_socket.recv(16)
            if resp != b'OK':
                print(f"[{target_ip}] 连接确认失败，终止发送。")
                continue
            print(f"[{target_ip}] 连接确认成功，开始发送数据。")

            # 1. 发送保存目录（4字节长度+utf-8字符串）
            dir_bytes = save_dir.encode('utf-8')
            dir_header = struct.pack('!I', len(dir_bytes)) + dir_bytes
            client_socket.sendall(dir_header)
            print(f"[{target_ip}] 已发送保存目录: {save_dir}")

            # 2. 发送当前目录下所有文件
            for file_name in os.listdir('.'):
                if os.path.isfile(file_name) and file_name != os.path.basename(__file__):
                    file_size = os.path.getsize(file_name)
                    name_bytes = file_name.encode('utf-8')
                    header = struct.pack('!I', len(name_bytes)) + name_bytes + struct.pack('!Q', file_size)
                    client_socket.sendall(header)
                    print(f"[{target_ip}] 开始发送文件: {file_name} ({file_size} 字节)")

                    with open(file_name, 'rb') as f:
                        while True:
                            data = f.read(65536)
                            if not data:
                                break
                            client_socket.sendall(data)
                    print(f"[{target_ip}] 文件发送完成: {file_name}")

            # 3. 发送 end_work
            client_socket.sendall(b'end_work')
            print(f"[{target_ip}] 已发送 end_work，所有文件发送完毕。")

if __name__ == "__main__":
    # 多个目标IP
    target_ips = ['127.0.0.1']  # 这里填写你的目标IP列表
    target_port = 6600
    save_dir = os.path.abspath('.')
    send_all_files(target_ips, target_port, save_dir)
    input("按回车键退出...")
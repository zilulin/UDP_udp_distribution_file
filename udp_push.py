import socket
import os
import struct
import time

def send_all_files(target_ips, target_port, save_dir):
    for target_ip in target_ips:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        addr = (target_ip, target_port)

        # 1. 发送保存目录（4字节长度+utf-8字符串）
        dir_bytes = save_dir.encode('utf-8')
        dir_header = struct.pack('!I', len(dir_bytes)) + dir_bytes
        client_socket.sendto(dir_header, addr)
        print(f"[{target_ip}] 已发送保存目录: {save_dir}")

        # 2. 发送当前目录下所有文件
        for file_name in os.listdir('.'):
            if os.path.isfile(file_name) and file_name not in [
            'udp_push.exe', 
            os.path.basename(__file__)
            ]:
                file_size = os.path.getsize(file_name)
                name_bytes = file_name.encode('utf-8')
                header = struct.pack('!I', len(name_bytes)) + name_bytes + struct.pack('!Q', file_size)
                client_socket.sendto(header, addr)
                print(f"[{target_ip}] 开始发送文件: {file_name} ({file_size} 字节)")

                with open(file_name, 'rb') as f:
                    while True:
                        data = f.read(65507)
                        if not data:
                            break
                        client_socket.sendto(data, addr)
                        time.sleep(0.01)  # 加延时，缓解丢包

                print(f"[{target_ip}] 文件发送完成: {file_name}")
                time.sleep(0.1)

        # 3. 发送 end_work
        client_socket.sendto(b'end_work', addr)
        print(f"[{target_ip}] 已发送 end_work，所有文件发送完毕。")
        client_socket.close()

if __name__ == "__main__":
    # 多个目标IP
    target_ips = ['10.192.100.103']  # 这里填写你的目标IP列表
    target_port = 6600
    save_dir = os.path.abspath('.')
    send_all_files(target_ips, target_port, save_dir)
    input("按回车键退出...")
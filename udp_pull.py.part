import socket
import os
import struct
import time

def receive_file(output_dir='received_files'):
    # 创建UDP套接字
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # 绑定地址和端口
    server_address = ('', 6600)
    server_socket.bind(server_address)
    print(f"正在监听UDP端口 {server_address[1]}...")

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    try:
        while True:
            # 接收文件头
            header_data, client_address = server_socket.recvfrom(1024)
            if not header_data:
                continue

            # 解析文件头 (文件名长度, 文件名, 文件大小)
            file_name_len = struct.unpack('!I', header_data[:4])[0]
            file_name = header_data[4:4+file_name_len].decode('utf-8')
            file_size = struct.unpack('!Q', header_data[4+file_name_len:4+file_name_len+8])[0]

            print(f"接收到文件: {file_name}, 大小: {file_size} 字节")
            
            # 构建保存路径
            save_path = os.path.join(output_dir, file_name)
            temp_path = save_path + '.part'
            
            # 接收文件数据
            with open(temp_path, 'wb') as file:
                bytes_received = 0
                start_time = time.time()
                
                while bytes_received < file_size:
                    packet, _ = server_socket.recvfrom(65507)  # UDP最大包大小
                    file.write(packet)
                    bytes_received += len(packet)
                    
                    # 显示进度
                    progress = (bytes_received / file_size) * 100
                    elapsed = time.time() - start_time
                    speed = bytes_received / elapsed / 1024 if elapsed > 0 else 0
                    print(f"\r进度: {progress:.2f}%, 速度: {speed:.2f} KB/s", end='')
                
                print("\n文件接收完成")
            
            # 重命名临时文件为最终文件名
            os.rename(temp_path, save_path)
            print(f"文件已保存至: {save_path}")

    except KeyboardInterrupt:
        print("\n程序被用户中断")
    finally:
        server_socket.close()

if __name__ == "__main__":
    receive_file()    
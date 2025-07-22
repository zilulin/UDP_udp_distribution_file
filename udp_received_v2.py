#   udp_received_v2.py
#   自启动之后隐藏窗口

import socket
import os
import struct
import time
import ctypes  # 用于隐藏窗口

def hide_console():
    """隐藏当前CMD窗口"""
    try:
        # 获取当前窗口句柄并隐藏
        ctypes.windll.user32.ShowWindow(
            ctypes.windll.kernel32.GetConsoleWindow(),
            0  # 0表示隐藏窗口，1表示显示
        )
    except Exception as e:
        print(f"隐藏窗口失败: {e}")  # 非Windows系统会触发此异常

def receive_file():
    
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = ('', 6600)
    server_socket.bind(server_address)
    # 隐藏窗口后，控制台输出不可见，可注释或保留
    print(f"正在监听UDP端口 {server_address[1]}...")
    time.sleep(5)
    # 启动时隐藏CMD窗口
    hide_console()


    try:
        while True:
            # 1. 接收保存目录地址
            print("等待接收保存目录地址...")
            dir_header, client_address = server_socket.recvfrom(1024)
            if not dir_header or len(dir_header) < 4:
                print("未收到有效目录信息，退出。")
                return
            dir_len = struct.unpack('!I', dir_header[:4])[0]
            output_dir = dir_header[4:4+dir_len].decode('utf-8')
            print(f"保存目录: {output_dir}")
            os.makedirs(output_dir, exist_ok=True)

            while True:
                # 2. 接收文件头或结束信号
                header_data, client_address = server_socket.recvfrom(1024)
                if header_data == b'end_work':
                    print("收到 end_work，准备接收新的保存目录。")
                    break
                if not header_data:
                    continue

                file_name_len = struct.unpack('!I', header_data[:4])[0]
                file_name = header_data[4:4+file_name_len].decode('utf-8')
                file_size = struct.unpack('!Q', header_data[4+file_name_len:4+file_name_len+8])[0]

                print(f"接收到文件: {file_name}, 大小: {file_size} 字节")
                save_path = os.path.join(output_dir, file_name)
                temp_path = save_path + '.part'
                
                if os.path.exists(save_path):
                    try:
                        os.remove(save_path)
                        print(f"已删除同名文件: {save_path}")
                    except Exception as e:
                        print(f"删除同名文件失败: {str(e)}，将尝试覆盖接收")

                with open(temp_path, 'wb') as file:
                    bytes_received = 0
                    start_time = time.time()
                    while bytes_received < file_size:
                        packet, _ = server_socket.recvfrom(65507)
                        file.write(packet)
                        bytes_received += len(packet)
                        progress = (bytes_received / file_size) * 100
                        elapsed = time.time() - start_time
                        speed = bytes_received / elapsed / 1024 if elapsed > 0 else 0
                        print(f"\r进度: {progress:.2f}%, 速度: {speed:.2f} KB/s", end='')
                    print("\n文件接收完成")

                os.rename(temp_path, save_path)
                print(f"文件已保存至: {save_path}")

    except KeyboardInterrupt:
        print("\n程序被用户中断")
    finally:
        server_socket.close()

if __name__ == "__main__":
    receive_file()
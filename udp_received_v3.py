import socket
import os
import struct
import time
import ctypes  # 用于隐藏窗口

def hide_console():
    """隐藏当前CMD窗口"""
    try:
        ctypes.windll.user32.ShowWindow(
            ctypes.windll.kernel32.GetConsoleWindow(),
            0  # 0表示隐藏窗口
        )
    except Exception as e:
        print(f"隐藏窗口失败: {e}")


def get_target_port_from_file(file_name='port_receive.txt'):
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


def receive_file():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # 增大接收缓冲区（例如设置为65535字节，UDP最大理论长度）
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65535)  # 关键设置
    
    target_port = get_target_port_from_file()
    server_address = ('', target_port)
    server_socket.bind(server_address)

    print(f"正在监听UDP端口 {server_address[1]}...")

    #time.sleep(5)  # 等待一秒，确保端口绑定成功

    # 启动时隐藏窗口
    #hide_console()

    try:
        while True:
            # 1. 接收保存根目录地址
            print("等待接收保存根目录...")
            dir_header, client_address = server_socket.recvfrom(16384)
            if not dir_header or len(dir_header) < 4:
                print("未收到有效目录信息，退出。")
                return
            dir_len = struct.unpack('!I', dir_header[:4])[0]
            root_dir = dir_header[4:4+dir_len].decode('utf-8')
            print(f"保存根目录: {root_dir}")
            os.makedirs(root_dir, exist_ok=True)

            # 2. 接收文件总数（4字节整数）
            file_count_data, _ = server_socket.recvfrom(4)
            total_files = struct.unpack('!I', file_count_data)[0]
            print(f"预计接收 {total_files} 个文件（包括子文件夹）")
            received_count = 0

            # 3. 循环接收所有文件
            while received_count < total_files:
                # 接收文件头（包含相对路径和文件大小）
                header_data, _ = server_socket.recvfrom(16384)
                # if header_data == b'end_work':
                #     print("提前收到结束信号，可能文件未接收完整")
                #     break
                # if not header_data:
                #     continue

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

                print(f"接收到文件: {rel_path}, 大小: {file_size} 字节")
                temp_path = save_path + '.part'

                # 若存在同名文件则删除
                if os.path.exists(save_path):
                    try:
                        os.remove(save_path)
                        print(f"已删除同名文件: {save_path}")
                    except Exception as e:
                        print(f"删除同名文件失败: {e}，将尝试覆盖")

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

                # 重命名临时文件
                os.rename(temp_path, save_path)
                print(f"文件已保存至: {save_path}")
                received_count += 1

            print(f"所有 {received_count}/{total_files} 个文件接收完成")

    except KeyboardInterrupt:
        print("\n程序被用户中断")
    finally:
        server_socket.close()

if __name__ == "__main__":
    receive_file()
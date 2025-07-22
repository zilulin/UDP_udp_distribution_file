import socket
import os
import struct

def recvn(sock, n):
    """确保接收n字节"""
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            raise ConnectionError("连接中断")
        data += packet
    return data

def receive_file():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('', 6600))
    server_socket.listen(5)
    print("正在监听TCP端口 6600...")

    try:
        while True:
            conn, addr = server_socket.accept()
            print(f"收到连接来自: {addr}")
            with conn:
                # 在 accept 后、正式接收数据前加如下代码
                hello = conn.recv(16)
                if hello == b'HELLO':
                    conn.sendall(b'OK')
                else:
                    print("未收到HELLO，断开连接。")
                    conn.close()
                    continue

                while True:
                    # 1. 接收保存目录
                    print("等待接收保存目录地址...")
                    dir_header = recvn(conn, 4)
                    dir_len = struct.unpack('!I', dir_header)[0]
                    dir_bytes = recvn(conn, dir_len)
                    output_dir = dir_bytes.decode('utf-8')
                    print(f"保存目录: {output_dir}")
                    os.makedirs(output_dir, exist_ok=True)

                    while True:
                        # 2. 接收文件头或结束信号
                        header_data = recvn(conn, 4)
                        if header_data == b'end_':
                            # 读取剩余部分
                            rest = recvn(conn, 4)
                            if header_data + rest == b'end_work':
                                print("收到 end_work，准备接收新的保存目录。")
                                break
                        file_name_len = struct.unpack('!I', header_data)[0]
                        name_bytes = recvn(conn, file_name_len)
                        file_name = name_bytes.decode('utf-8')
                        file_size = struct.unpack('!Q', recvn(conn, 8))[0]

                        print(f"接收到文件: {file_name}, 大小: {file_size} 字节")
                        save_path = os.path.join(output_dir, file_name)
                        temp_path = save_path + '.part'

                        with open(temp_path, 'wb') as file:
                            bytes_received = 0
                            while bytes_received < file_size:
                                chunk_size = min(65536, file_size - bytes_received)
                                data = recvn(conn, chunk_size)
                                file.write(data)
                                bytes_received += len(data)
                                progress = (bytes_received / file_size) * 100
                                print(f"\r进度: {progress:.2f}%", end='')
                            print("\n文件接收完成")
                        os.rename(temp_path, save_path)
                        print(f"文件已保存至: {save_path}")

    except KeyboardInterrupt:
        print("\n程序被用户中断")
    finally:
        server_socket.close()

if __name__ == "__main__":
    receive_file()
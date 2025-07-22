import socket
import os
import struct
import time
import ctypes
from collections import defaultdict

# 与发送端保持一致的块大小（确保协议匹配）
CHUNK_SIZE = 65500  # 发送端的分块大小
RECV_TIMEOUT = 30  # 超时时间（秒），根据网络情况调整
MAX_RETRY = 3  # 块接收失败的最大重试次数


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
    """从文件读取端口号"""
    default_port = 6600
    if not os.path.exists(file_name):
        print(f"警告：未找到 {file_name}，使用默认端口 {default_port}")
        return default_port
    
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            port_str = f.readline().strip()
            port = int(port_str)
            if 1 <= port <= 65535:
                print(f"读取端口成功: {port}")
                return port
            else:
                print(f"端口无效，使用默认 {default_port}")
    except (ValueError, Exception) as e:
        print(f"读取端口失败: {e}，使用默认 {default_port}")
    return default_port


def receive_long_data(sock, addr, max_wait_sec=RECV_TIMEOUT):
    """接收分块数据（路径/长文本），返回完整字节数据"""
    # 1. 接收总长度（8字节无符号整数）
    try:
        length_data, addr = sock.recvfrom(8)
        total_length = struct.unpack('!Q', length_data)[0]
        print(f"待接收数据总长度: {total_length} 字节")
    except Exception as e:
        raise RuntimeError(f"接收总长度失败: {e}")

    # 2. 分块接收数据
    buffer = bytearray()
    expected_chunk_id = 0
    last_receive_time = time.time()
    missing_chunks = set()  # 记录缺失的块ID

    while len(buffer) < total_length:
        # 超时检查
        if time.time() - last_receive_time > max_wait_sec:
            if missing_chunks:
                raise TimeoutError(f"超时，缺失块: {missing_chunks}，已接收 {len(buffer)}/{total_length} 字节")
            else:
                raise TimeoutError(f"超时，未收到足够数据，已接收 {len(buffer)}/{total_length} 字节")

        # 接收块数据
        sock.settimeout(max_wait_sec)
        try:
            chunk_data, addr = sock.recvfrom(CHUNK_SIZE + 4)  # 4字节块ID + 数据
        except socket.timeout:
            continue  # 超时重试
        except Exception as e:
            print(f"接收块失败: {e}，重试...")
            continue

        last_receive_time = time.time()

        # 解析块ID和内容
        chunk_id = struct.unpack('!I', chunk_data[:4])[0]
        chunk_content = chunk_data[4:]

        # 结束标记（0xFFFFFFFF表示分块结束）
        if chunk_id == 0xFFFFFFFF:
            if len(buffer) != total_length:
                raise RuntimeError(f"分块结束但数据不完整: 接收 {len(buffer)}，预期 {total_length}")
            print(f"分块数据接收完成，总长度: {len(buffer)} 字节")
            return bytes(buffer), addr

        # 处理有效块
        if chunk_id == expected_chunk_id:
            buffer.extend(chunk_content)
            expected_chunk_id += 1
            # 显示进度（每1MB更新一次）
            if len(buffer) % (1024 * 1024) == 0:
                progress = (len(buffer) / total_length) * 100
                print(f"\r接收进度: {progress:.2f}%", end='')
        elif chunk_id > expected_chunk_id:
            # 记录缺失的块
            for id in range(expected_chunk_id, chunk_id):
                missing_chunks.add(id)
            print(f"警告：检测到缺失块 {expected_chunk_id}~{chunk_id-1}，等待重传...")
        else:
            # 忽略已接收的旧块
            print(f"忽略重复块: {chunk_id}（已接收）")

    print()  # 换行
    return bytes(buffer), addr


def receive_file_content(sock, file_size, addr, max_wait_sec=RECV_TIMEOUT):
    """接收文件内容（分块），返回完整字节数据"""
    buffer = bytearray()
    expected_chunk_id = 0
    last_receive_time = time.time()
    missing_chunks = set()

    print(f"开始接收文件内容（大小: {file_size} 字节）")

    while len(buffer) < file_size:
        # 超时检查
        if time.time() - last_receive_time > max_wait_sec:
            if missing_chunks:
                raise TimeoutError(f"文件内容接收超时，缺失块: {missing_chunks}，已接收 {len(buffer)}/{file_size} 字节")
            else:
                raise TimeoutError(f"文件内容接收超时，已接收 {len(buffer)}/{file_size} 字节")

        # 接收块数据
        sock.settimeout(max_wait_sec)
        try:
            chunk_data, addr = sock.recvfrom(CHUNK_SIZE + 4)  # 4字节块ID + 内容
        except socket.timeout:
            continue
        except Exception as e:
            print(f"文件块接收失败: {e}，重试...")
            continue

        last_receive_time = time.time()

        # 解析块ID和内容
        chunk_id = struct.unpack('!I', chunk_data[:4])[0]
        chunk_content = chunk_data[4:]

        # 处理有效块
        if chunk_id == expected_chunk_id:
            buffer.extend(chunk_content)
            expected_chunk_id += 1
            # 显示进度
            progress = (len(buffer) / file_size) * 100
            speed = len(buffer) / (time.time() - last_receive_time + 1e-6) / 1024  # KB/s
            print(f"\r接收进度: {progress:.2f}%，速度: {speed:.2f} KB/s", end='')
        elif chunk_id > expected_chunk_id:
            for id in range(expected_chunk_id, chunk_id):
                missing_chunks.add(id)
            print(f"\n警告：文件内容缺失块 {expected_chunk_id}~{chunk_id-1}，等待重传...")
        else:
            print(f"忽略文件重复块: {chunk_id}")

    print("\n文件内容接收完成")
    if len(buffer) != file_size:
        raise RuntimeError(f"文件内容不完整: 接收 {len(buffer)}，预期 {file_size} 字节")
    return bytes(buffer)


def receive_file():
    # 创建UDP套接字
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)  # 增大缓冲区到1MB
    target_port = get_target_port_from_file()
    server_address = ('', target_port)
    server_socket.bind(server_address)
    print(f"已绑定UDP端口 {target_port}，等待数据...")

    try:
        while True:
            client_address = None  # 记录当前客户端地址，确保数据来自同一发送端

            # 1. 接收保存根目录（分块）
            print("\n===== 等待接收保存根目录 =====")
            try:
                dir_bytes, client_address = receive_long_data(server_socket)
                root_dir = dir_bytes.decode('utf-8', errors='replace')  # 容错解码
                print(f"保存根目录: {root_dir}")
                os.makedirs(root_dir, exist_ok=True)
            except Exception as e:
                print(f"根目录接收失败: {e}，等待下一轮...")
                continue

            # 2. 接收文件总数（4字节）
            print("\n===== 等待接收文件总数 =====")
            try:
                file_count_data, addr = server_socket.recvfrom(4)
                if addr != client_address:
                    raise RuntimeError("文件总数数据来自陌生地址，忽略")
                total_files = struct.unpack('!I', file_count_data)[0]
                print(f"预计接收文件数: {total_files}")
                if total_files <= 0:
                    print("文件数无效，跳过")
                    continue
            except Exception as e:
                print(f"文件总数接收失败: {e}，等待下一轮...")
                continue

            # 3. 接收所有文件
            received_count = 0
            success = True
            while received_count < total_files:
                print(f"\n===== 接收第 {received_count+1}/{total_files} 个文件 =====")
                try:
                    # 3.1 接收文件大小（8字节）
                    size_data, addr = server_socket.recvfrom(8)
                    if addr != client_address:
                        raise RuntimeError("文件大小数据来自陌生地址，忽略")
                    file_size = struct.unpack('!Q', size_data)[0]
                    print(f"文件大小: {file_size} 字节")

                    # 3.2 接收文件相对路径（分块）
                    print("接收文件路径...")
                    rel_path_bytes, addr = receive_long_data(server_socket)
                    if addr != client_address:
                        raise RuntimeError("文件路径数据来自陌生地址，忽略")
                    rel_path = rel_path_bytes.decode('utf-8', errors='replace')
                    print(f"文件相对路径: {rel_path}")

                    # 3.3 构建保存路径
                    save_path = os.path.join(root_dir, rel_path)
                    save_dir = os.path.dirname(save_path)
                    os.makedirs(save_dir, exist_ok=True)
                    print(f"文件保存路径: {save_path}")

                    # 3.4 接收文件内容（分块）
                    print("接收文件内容...")
                    file_content = receive_file_content(server_socket, file_size, client_address)

                    # 3.5 写入文件
                    temp_path = save_path + '.part'
                    with open(temp_path, 'wb') as f:
                        f.write(file_content)
                    # 验证文件大小
                    if os.path.getsize(temp_path) != file_size:
                        raise RuntimeError(f"文件写入大小不匹配（实际: {os.path.getsize(temp_path)}，预期: {file_size}）")
                    # 重命名临时文件
                    os.replace(temp_path, save_path)
                    print(f"文件接收成功: {save_path}")
                    received_count += 1

                except Exception as e:
                    print(f"第 {received_count+1} 个文件接收失败: {e}")
                    success = False
                    break  # 单个文件失败，终止本轮接收

            # 4. 接收结束信号
            if success and received_count == total_files:
                print("\n===== 等待接收结束信号 =====")
                try:
                    server_socket.settimeout(10)
                    end_signal, addr = server_socket.recvfrom(1024)
                    if addr == client_address and end_signal == b'end_work':
                        print("收到结束信号，本轮传输完成！")
                    else:
                        print("未收到有效结束信号，但文件已接收完成")
                except socket.timeout:
                    print("超时未收到结束信号，但文件已接收完成")

            print(f"\n===== 本轮传输结束，成功接收 {received_count}/{total_files} 个文件 =====")

    except KeyboardInterrupt:
        print("\n用户中断程序")
    finally:
        server_socket.close()
        print("套接字已关闭")


if __name__ == "__main__":
    # hide_console()  # 按需启用
    receive_file()
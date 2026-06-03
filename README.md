# UDP 文件分发工具

这个项目用于在局域网内把一个文件夹中的文件批量分发到一台或多台电脑。发送端会读取当前目录下的文件和子目录，按相对路径发送给接收端；接收端在目标机器上按同样的目录结构保存文件。项目同时保留了 TCP 版本和多个 UDP 迭代版本，推荐使用最新的 UDP 版本。

## 实现效果

- 将发送端所在目录下的文件递归发送到多个目标 IP。
- 接收端会在本机创建与发送端相同的根目录路径，并还原子目录结构。
- 同名文件会被覆盖；接收过程中先写入 `.part` 临时文件，完成后再重命名为正式文件。
- UDP 传输加入 ACK 确认机制，减少无确认 UDP 传输造成的丢包风险。
- 支持通过配置文件设置目标 IP 和端口。
- 接收端支持日志记录，日志文件为 `file_receiver.log`，按天轮转并保留 7 天。
- 发送端支持日志记录，日志文件为 `udp_transfer.log`。
- `dist/` 目录中包含已经用 PyInstaller 打包生成的 Windows 可执行文件。

## 推荐版本

推荐使用：

- 发送端：`udp_push_v4.py` 或 `dist/udp_push_v4.exe`
- 接收端：`udp_received_v5.py` 或 `dist/udp_received_v5.exe`

其他文件主要是历史版本或对照实现：

| 文件 | 作用 |
| --- | --- |
| `udp_push.py` | 最早的 UDP 发送端，目标 IP 写死在代码中，只发送当前目录文件。 |
| `udp_push_v2.py` | 从 `ip.txt`、`port.txt` 读取配置，只发送当前目录文件。 |
| `udp_push_v3.py` | 支持递归发送子目录，但缺少完整 ACK 流程。 |
| `udp_push_v4.py` | 推荐 UDP 发送端，支持递归、多目标、端口配置、日志和 ACK。 |
| `udp_received.py`、`udp_received_v2.py`、`udp_received_v3.py`、`udp_received_v4.py` | UDP 接收端历史版本。 |
| `udp_received_v5.py` | 推荐 UDP 接收端，支持超时恢复、日志轮转、临时文件清理和 ACK。 |
| `udp_pull.py` | 简单 UDP 接收示例，固定监听 `6600` 并保存到代码指定目录。 |
| `tcp_push.py`、`tcp_received.py` | TCP 发送/接收版本，使用长连接和 `HELLO/OK` 握手。 |
| `*.spec` | PyInstaller 打包配置文件。 |
| `build/` | PyInstaller 构建中间文件。 |
| `dist/` | 打包后的 `.exe` 文件和运行日志。 |

## 配置文件

### 发送端配置

发送端读取当前运行目录下的 `ip.txt` 和 `port.txt`。

`ip.txt`：每行一个接收端 IP，例如：

```text
192.168.1.101
192.168.1.102
```

`port.txt`：第一行写接收端 UDP 端口，例如：

```text
6600
```

如果没有 `port.txt`，发送端默认使用 `6600`。

### 接收端配置

接收端读取当前运行目录下的 `port_receive.txt`。

```text
6600
```

如果没有 `port_receive.txt`，接收端默认监听 `6600`。

注意：发送端 `port.txt` 和接收端 `port_receive.txt` 必须保持一致。

## 使用方式

### 1. 在接收端电脑启动接收程序

方式一：运行源码：

```powershell
python udp_received_v5.py
```

方式二：运行已打包程序：

```powershell
.\dist\udp_received_v5.exe
```

接收端启动后会监听 UDP 端口。`udp_received_v5.py` 会在启动后短暂等待并尝试隐藏控制台窗口，适合后台常驻接收。

### 2. 在发送端准备要分发的文件夹

把发送端程序和配置文件放到要发送的文件夹中，例如：

```text
待发送文件夹/
  udp_push_v4.exe
  ip.txt
  port.txt
  file1.txt
  subdir/
    file2.txt
```

发送端会发送当前文件夹及子文件夹中的文件，但会自动排除：

- `udp_push_v4.exe`
- `udp_push_v4.py`
- `ip.txt`
- `port.txt`
- `udp_transfer.log`

### 3. 运行发送端

方式一：运行源码：

```powershell
python udp_push_v4.py
```

方式二：运行已打包程序：

```powershell
.\udp_push_v4.exe
```

程序会依次向 `ip.txt` 中的每个 IP 发送全部文件，并在控制台显示进度和速度。

## 保存路径规则

发送端会把“发送端当前目录的绝对路径”发送给接收端。接收端收到后，会在本机创建同样的目录路径，并把文件保存进去。

例如发送端目录是：

```text
D:\deploy\files
```

接收端也会尝试保存到：

```text
D:\deploy\files
```

如果接收端没有这个目录，会自动创建；如果已有同名文件，会先删除再覆盖。

## UDP 协议流程

`udp_push_v4.py` 和 `udp_received_v5.py` 的传输流程如下：

1. 发送端发送保存根目录：`目录长度 + 目录字符串`。
2. 接收端回复 `DIR_ACK`。
3. 发送端发送文件总数。
4. 接收端回复 `COUNT_ACK`。
5. 每个文件开始前，发送端发送文件头：`相对路径长度 + 相对路径 + 文件大小`。
6. 接收端回复 `HEADER_ACK`。
7. 发送端分包发送文件内容，单包最大读取 `65507` 字节。
8. 接收端每收到一个数据包，回复 `DATA_ACK:<包大小>`。
9. 文件数据接收完毕后，接收端回复 `FILE_COMPLETE`。
10. 接收端将 `.part` 文件重命名为正式文件后，回复 `PROCESS_COMPLETE`。

如果发送端等待 ACK 超时，会跳过当前目标或当前文件。接收端遇到超时或异常时，会清理临时文件并回到等待新传输的状态。

## 打包方式

项目已经包含 PyInstaller 的 `.spec` 文件。安装 PyInstaller 后可重新打包：

```powershell
pyinstaller udp_push_v4.spec
pyinstaller udp_received_v5.spec
```

生成的可执行文件会放在 `dist/` 目录。

也可以直接打包源码：

```powershell
pyinstaller --onefile udp_push_v4.py
pyinstaller --onefile udp_received_v5.py
```

## 注意事项

- 发送端和接收端必须在网络上互通，防火墙需要允许对应 UDP 端口。
- UDP 本身不保证可靠传输，本项目通过 ACK 做了基础确认，但仍不适合跨公网或极不稳定网络的大文件传输。
- 保存路径来自发送端的绝对路径；如果不同电脑磁盘结构不同，接收端可能会创建新的盘符路径失败或保存到非预期位置。
- 同名文件会被覆盖，运行前请确认目标目录中没有需要保留的同名文件。
- 如果文件正在被其他程序占用，接收端会尝试删除或覆盖，失败时会保留 `.part` 临时文件并记录日志。
- 运行打包后的 `.exe` 时，配置文件需要与 `.exe` 放在同一工作目录中。

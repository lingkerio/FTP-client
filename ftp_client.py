import socket
import zlib
import os


class FTPClient:
    """
    FTP客户端类，用于管理与FTP服务器的连接和交互。

    属性:
    ip (str): FTP服务器的IP地址。
    port (int): FTP服务器的端口号。
    mode (str): 数据传输模式（'active'或'passive'）。
    s (socket.socket): 用于与FTP服务器通信的套接字。

    方法:
    __init__(self, ip: str, port: int, mode="passive"): 初始化FTP客户端。
    initialize_data_socket(self): 初始化数据传输套接字，基于模式（主动或被动）。
    initialize_passive_socket(self): 初始化被动模式数据传输套接字。
    initialize_active_socket(self): 初始化主动模式数据传输套接字。
    control_recv_all(self): 接收服务器发送的所有数据。
    send_cmd(self, cmd: str): 向FTP服务器发送命令并接收响应。
    login(self, username: str = "anonymous", password: str = "anonymous@"): 使用用户名和密码登录FTP服务器。
    set_transfer_mode(self, mode: str): 设置传输模式（ASCII或Binary）。
    list(self): 请求FTP服务器列出当前目录中的文件和目录。
    quit(self): 断开与FTP服务器的连接。
    upload(self, file_path: str, mode: str = "Binary", compressed: bool = False): 上传文件或目录到FTP服务器。
    upload_directory(self, directory_path: str, mode: str, compressed: bool): 递归上传目录到FTP服务器。
    upload_file(self, file_path: str, mode: str, compressed: bool): 上传单个文件到FTP服务器。
    download(self, remote_path: str, local_path: str): 从FTP服务器下载文件或目录。
    download_file(self, remote_filename: str, local_path: str): 从FTP服务器下载单个文件。
    resume_upload(self, file_path: str, start_position: int): 从特定字节偏移处恢复上传文件。
    resume_download(self, filename: str, local_path: str, start_position: int): 从特定字节偏移处恢复下载文件。
    change_directory(self, directory: str): 更改FTP服务器上的当前目录。
    """

    def __init__(self, ip: str, port: int, mode="passive"):
        """
        初始化FTP客户端。

        参数:
        ip (str): FTP服务器的IP地址。
        port (int): FTP服务器的端口号。
        mode (str): 数据传输模式（'active'或'passive'）。
        """
        self.ip = ip
        self.port = port
        self.mode = mode
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((ip, port))
        print(self.control_recv_all())

    def initialize_data_socket(self) -> socket.socket:
        """
        初始化数据传输套接字，基于模式（主动或被动）。
        """
        if self.mode == "passive":
            return self.initialize_passive_socket()
        elif self.mode == "active":
            return self.initialize_active_socket()
        else:
            raise Exception("Invalid mode")

    def initialize_passive_socket(self) -> socket.socket:
        """
        初始化被动模式数据传输套接字。
        """
        max_retries = 5  # 设置最大重试次数
        retries = 0
        while retries < max_retries:
            response = self.send_cmd("PASV")
            print(response)
            if "(" in response and ")" in response:
                start = response.index("(") + 1
                end = response.index(")", start)
                pasv_info = response[start:end].split(",")
                data_ip = self.ip
                data_port = (int(pasv_info[4]) << 8) + int(pasv_info[5])
                data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                data_socket.connect((data_ip, data_port))
                return data_socket
            else:
                retries += 1
                print(
                    f"Invalid PASV response received. Retrying... ({retries}/{max_retries})"
                )
        raise Exception("Failed to initialize passive socket after maximum retries.")

    def initialize_active_socket(self) -> socket.socket:
        """
        初始化主动模式数据传输套接字。
        """

        def _find_free_port():
            """
            查找一个空闲端口。
            """
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", 0))
                return s.getsockname()[1]

        def _ip_to_port():
            """
            将IP地址转换为PORT命令的参数格式。
            """
            ip_parts = self.ip.split(".")
            return (
                ",".join(ip_parts) + f",{self.data_port >> 8},{self.data_port & 0xFF}"
            )

        self.data_port = _find_free_port()
        self.s.send(f"PORT {_ip_to_port()}\r\n".encode())
        response = self.control_recv_all()
        if not response.startswith("200"):
            raise Exception("Failed to enter Active Mode")
        data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        data_socket.bind(("", self.data_port))
        data_socket.listen(1)
        return data_socket

    def control_recv_all(self) -> str:
        """
        接收服务器发送的所有数据，直到没有更多数据为止。
        """
        data = b""
        while True:
            part = self.s.recv(1024)
            data += part
            if len(part) < 1024:
                break
        return data.decode()

    def send_cmd(self, cmd: str) -> str:
        """
        向FTP服务器发送命令并接收响应。

        参数:
        cmd (str): 要发送的命令。

        返回:
        str: 服务器的响应。
        """
        self.s.send(cmd.encode() + b"\r\n")
        return self.control_recv_all()

    def login(self, username: str = "anonymous", password: str = "anonymous@"):
        """
        使用用户名和密码登录FTP服务器。

        参数:
        username (str): 用户名。
        password (str): 密码。
        """
        print(self.send_cmd("USER " + username))
        print(self.send_cmd("PASS " + password))

    def list(self):
        """
        请求FTP服务器列出当前目录中的文件和目录。
        """
        data_socket = self.initialize_data_socket()

        self.send_cmd("LIST")
        print(self.control_recv_all())
        data = b""
        while True:
            part = data_socket.recv(1024)
            data += part
            if not part:
                data_socket.close()
                break
        print(data.decode())
        print("Listing complete")

    def quit(self):
        """
        断开与FTP服务器的连接。
        """
        print(self.send_cmd("QUIT"))
        print(self.control_recv_all())
        self.s.close()

    def upload(self, file_path: str, mode: str = "Binary", compressed: bool = False):
        """
        上传文件或目录到FTP服务器。
        """
        if os.path.isdir(file_path):
            self.upload_directory(file_path, mode, compressed)
        else:
            self.upload_file(file_path, mode, compressed)

    def upload_directory(self, directory_path: str, mode: str, compressed: bool):
        """
        递归上传目录到FTP服务器。
        """
        for item in os.listdir(directory_path):
            local_path = os.path.join(directory_path, item)
            if os.path.isdir(local_path):
                self.send_cmd(f"MKD {item}")
                self.send_cmd(f"CWD {item}")
                self.upload_directory(local_path, mode, compressed)
                self.send_cmd("CDUP")
            else:
                self.upload_file(local_path, mode, compressed)

    def upload_file(self, file_path: str, mode: str, compressed: bool):
        """
        上传单个文件到FTP服务器。
        """
        data_socket = self.initialize_data_socket()

        filename = os.path.basename(file_path)
        self.send_cmd(f"STOR {filename}")

        with open(file_path, "rb") as file:
            if compressed:
                data = zlib.compress(file.read())
            else:
                data = file.read()
            data_socket.sendall(data)
        data_socket.close()
        print(f"Uploaded {file_path}")

    def download(self, remote_path: str, local_path: str):
        """
        下载文件或目录从FTP服务器。
        """
        self.send_cmd(f"CWD {remote_path}")  # Change directory remotely
        listing = self.send_cmd("LIST")  # List items in the directory
        lines = listing.splitlines()
        for line in lines:
            parts = line.split()
            name = parts[-1]
            if line.startswith("d"):  # Directory
                new_local_path = os.path.join(local_path, name)
                os.makedirs(new_local_path, exist_ok=True)
                self.download(name, new_local_path)  # Recursively download
            else:  # File
                self.download_file(name, os.path.join(local_path, name))
        self.send_cmd("CDUP")  # Go back to the parent directory

    def download_file(self, remote_filename: str, local_path: str):
        """
        从FTP服务器下载单个文件。
        """
        # 确保已经进入被动模式并且数据连接已经建立
        data_socket = self.initialize_data_socket()

        # 发送下载文件的命令
        self.send_cmd(f"RETR {remote_filename}")

        # 从数据套接字接收文件内容并写入本地文件

        with open(local_path, "wb") as file:
            while True:
                data = data_socket.recv(1024)
                if not data:
                    data_socket.close()
                    break
                file.write(data)

        # 检查传输是否成功完成
        transfer_complete_response = self.control_recv_all()
        print(transfer_complete_response)  # 打印传输完成后的响应，以便于调试
        print(f"Downloaded {remote_filename} to {local_path}")

    def resume_upload(self, file_path: str, start_position: int):
        """
        从特定字节偏移处恢复上传文件。
        """
        data_socket = self.initialize_data_socket()

        filename = os.path.basename(file_path)
        self.send_cmd(f"REST {start_position}")
        self.send_cmd(f"STOR {filename}")

        with open(file_path, "rb") as file:
            file.seek(start_position)
            while True:
                data = file.read(1024)
                if not data:
                    data_socket.close()
                    break
                data_socket.sendall(data)

        print(f"Resumed upload of {file_path}")

    def resume_download(self, filename: str, local_path: str, start_position: int):
        """
        从特定字节偏移处恢复下载文件。
        """
        self.send_cmd(f"REST {start_position}")
        self.send_cmd(f"RETR {filename}")
        data_socket = self.initialize_data_socket()

        with open(local_path, "ab") as file:
            while True:
                data = data_socket.recv(1024)
                if not data:
                    data_socket.close()
                    break
                file.write(data)

        print(f"Resumed download of {filename} to {local_path}")

    def change_directory(self, directory: str):
        """
        更改FTP服务器上的当前目录。

        参数:
        directory (str): 目标目录。
        """
        print(self.send_cmd(f"CWD {directory}"))


# Example usage of the FTPClient
ftp_client = FTPClient("127.0.0.1", 21, mode="passive")
ftp_client.login('test','123456')
ftp_client.list()
ftp_client.change_directory("set")
ftp_client.list()
ftp_client.download_file("a.txt", "./a.txt")
ftp_client.quit()

import socket

class FTPClient:
    """
    FTP客户端类，用于管理与FTP服务器的连接和交互。
    """

    def __init__(self, ip:str, port:int):
        """
        初始化FTP客户端。

        参数:
        ip: str - FTP服务器的IP地址。
        port: int - FTP服务器的端口号。
        """
        self.ip = ip
        self.port = port
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((ip, port))
        self.recv_all()

    def recv_all(self):
        """
        接收从服务器发送的所有数据，直到没有更多数据为止。

        返回:
        接收到的数据。
        """
        data = b""
        while True:
            part = self.s.recv(1024)
            data += part
            if len(part) < 1024:
                break
        return data

    def send_cmd(self, cmd:str):
        """
        向FTP服务器发送命令并接收响应。

        参数:
        cmd: str - 要发送的命令。

        返回:
        服务器的响应。
        """
        self.s.send(cmd.encode() + b"\r\n")
        return self.recv_all().decode()

    def login(self, username:str, password:str):
        """
        使用用户名和密码登录FTP服务器。

        参数:
        username: str - 用户名。
        password: str - 密码。
        """
        print(self.send_cmd("USER " + username))
        print(self.send_cmd("PASS " + password))

    def pasv(self):
        """
        向FTP服务器发送PASV命令，准备进行被动模式数据传输。

        返回:
        数据连接的IP地址和端口号。
        """
        response = self.send_cmd("PASV")
        print(response)
        start = response.index("(") + 1
        end = response.index(")", start)
        pasv_info = response[start:end].split(",")
        data_ip = ".".join(pasv_info[:4])
        data_port = (int(pasv_info[4]) << 8) + int(pasv_info[5])
        return data_ip, data_port

    def list(self):
        """
        请求FTP服务器列出当前目录下的文件和目录。
        """
        data_ip, data_port = self.pasv()
        data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        data_socket.connect((data_ip, data_port))
        print(self.send_cmd("LIST"))
        print(data_socket.recv(1024).decode())
        data_socket.close()

    def quit(self):
        """
        断开与FTP服务器的连接。
        """
        print(self.send_cmd("QUIT"))
        self.s.close()

    def upload(self, file_path: str) -> None:
        """
        将本地文件上传到FTP服务器。

        参数:
        file_path: str - 本地文件的路径。
        """
        filename = file_path.split("/")[-1]
        data_ip, data_port = self.pasv()
        self.send_cmd(f"STOR {filename}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as data_socket:
            data_socket.connect((data_ip, data_port))
            with open(file_path, "rb") as file:
                data_socket.sendfile(file)
        print(f"Uploaded {file_path}")

    def download(self, filename: str, local_path: str) -> None:
        """
        从FTP服务器下载文件到本地。

        参数:
        filename: str - 要下载的文件名。
        local_path: str - 文件下载到本地的路径。
        """
        data_ip, data_port = self.pasv()
        self.send_cmd(f"RETR {filename}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as data_socket:
            data_socket.connect((data_ip, data_port))
            with open(local_path, "wb") as file:
                while True:
                    data = data_socket.recv(1024)
                    if not data:
                        break
                    file.write(data)
        print(f"Downloaded {filename} to {local_path}")

    def resume_upload(self, file_path: str, start_position: int) -> None:
        """
        从上次中断的位置继续上传文件。

        参数:
        file_path: str - 本地文件的路径。
        start_position: int - 从文件的这个位置开始上传。
        """
        filename = file_path.split("/")[-1]
        data_ip, data_port = self.pasv()
        self.send_cmd(f"REST {start_position}")
        self.send_cmd(f"STOR {filename}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as data_socket:
            data_socket.connect((data_ip, data_port))
            with open(file_path, "rb") as file:
                file.seek(start_position)
                data_socket.sendfile(file)
        print(f"Resumed upload of {file_path} from {start_position}")

    def resume_download(
        self, filename: str, local_path: str, start_position: int
    ) -> None:
        """
        从上次中断的位置继续下载文件。

        参数:
        filename: str - 要下载的文件名。
        local_path: str - 文件下载到本地的路径。
        start_position: int - 从文件的这个位置开始下载。
        """
        data_ip, data_port = self.pasv()
        self.send_cmd(f"REST {start_position}")
        self.send_cmd(f"RETR {filename}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as data_socket:
            data_socket.connect((data_ip, data_port))
            with open(local_path, "ab") as file:  # Append mode for resuming
                file.seek(start_position)
                while True:
                    data = data_socket.recv(1024)
                    if not data:
                        break
                    file.write(data)
        print(f"Resumed download of {filename} to {local_path} from {start_position}")

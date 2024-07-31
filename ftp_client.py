import socket
import time
import os
import traceback


class FTPClient:
    def __init__(
        self,
        ip: str,
        port: int,
        mode="passive",
        transfer_mode="ascii",
        transfer_method="stream",
    ):
        self.ip = ip
        self.port = port
        self.mode = mode
        self.transfer_mode = transfer_mode
        self.transfer_method = transfer_method
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((ip, port))
        print(self.control_recv_all())

    def initialize_data_socket(self) -> socket.socket:
        if self.mode == "passive":
            return self.initialize_passive_socket()
        elif self.mode == "active":
            return self.initialize_active_socket()
        else:
            raise Exception("Invalid mode")

    def initialize_passive_socket(self) -> socket.socket:
        max_retries = 5
        retries = 0
        while retries < max_retries:
            self.send_cmd("PASV")
            response = self.control_recv_all()
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
        def _find_free_port():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", 0))
                return s.getsockname()[1]

        def _ip_to_port():
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
        data = b""
        while True:
            part = self.s.recv(1024)
            data += part
            if len(part) < 1024:
                break
        return data.decode()

    def send_cmd(self, cmd: str):
        self.s.send(cmd.encode() + b"\r\n")
        time.sleep(0.1)
        return

    def login(self, username: str = "anonymous", password: str = "anonymous@"):
        self.send_cmd("USER " + username)
        print(self.control_recv_all())
        self.send_cmd("PASS " + password)
        print(self.control_recv_all())

    def list(self):
        try:
            data_socket = self.initialize_data_socket()
            self.send_cmd("LIST")

            response = self.control_recv_all().split("\r\n")
            print(response[0])

            data = b""
            while True:
                part = data_socket.recv(1024)
                data += part
                if len(part) < 1024:
                    data_socket.close()
                    break
            print(data.decode())
            print("Listing complete")
            if len(response) == 2:
                print(self.control_recv_all())
            else:
                print(response[1])
        except socket.error as e:
            print(f"Socket error: {e}")
            data_socket.close()

    def list_content(self):
        try:
            data_socket = self.initialize_data_socket()
            self.send_cmd("LIST")

            response = self.control_recv_all().split("\r\n")
            print(response[0])

            data = b""
            while True:
                part = data_socket.recv(1024)
                data += part
                if len(part) < 1024:
                    data_socket.close()
                    break
            print("Listing complete")
            if len(response) == 2:
                print(self.control_recv_all())
            else:
                print(response[1])
                
            return data.decode()
        except socket.error as e:
            print(f"Socket error: {e}")
            data_socket.close()

    def change_dir(self, path: str):
        self.send_cmd("CWD " + path)
        response = self.control_recv_all()
        if not response.startswith("250"):
            raise Exception(
                f"Failed to change directory to {path}. Server response: {response}"
            )
        print(response)

    def set_transfer_mode(self, transfer_mode: str):
        if transfer_mode not in ["binary", "text"]:
            raise ValueError("Invalid transfer mode. Use 'binary' or 'text'.")
        self.transfer_mode = transfer_mode
        cmd = "TYPE I" if transfer_mode == "binary" else "TYPE A"
        self.send_cmd(cmd)
        response = self.control_recv_all()
        if not response.startswith("200"):
            raise Exception(
                f"Failed to set transfer mode to {transfer_mode}. Server response: {response}"
            )
        print(response)

    def set_transfer_method(self, transfer_method: str):
        if transfer_method not in ["stream", "block", "compressed"]:
            raise ValueError(
                "Invalid transfer method. Use 'stream', 'block', or 'compressed'."
            )
        self.transfer_method = transfer_method
        cmd = None
        if transfer_method == "stream":
            cmd = "MODE S"
        elif transfer_method == "block":
            cmd = "MODE B"
        else:
            cmd = "MODE C"
        self.send_cmd(cmd)
        response = self.control_recv_all()
        if not response.startswith("200"):
            raise Exception(
                f"Failed to set transfer method to {transfer_method}. Server response: {response}"
            )
        print(response)

    def recv_all_from_data_socket(self, data_socket):
        data = []
        while True:
            part = data_socket.recv(1024)
            if not part:
                break
            data.append(part.decode("utf-8"))
        return "".join(data)

    def download(self, remote_filename: str, local_filename: str | None = None):
        if local_filename is None:
            local_filename = remote_filename

        try:
            # 记录当前目录
            self.send_cmd("PWD")
            dir_response = self.control_recv_all().split('"')
            print(dir_response)
            current_directory = dir_response[1]
            print(current_directory)

            # 使用CWD命令检查远程文件是否是目录
            self.send_cmd(f"CWD {remote_filename}")
            response = self.control_recv_all()

            if response.startswith("250"):
                # 如果是目录，创建本地目录并返回上一级目录
                self.send_cmd(f"CWD {current_directory}")
                self.control_recv_all()
                if not os.path.exists(local_filename):
                    os.makedirs(local_filename)

                # 使用LIST命令列出目录内容
                data_socket = self.initialize_data_socket()
                self.send_cmd(f"LIST {remote_filename}")
                self.control_recv_all()
                response = self.recv_all_from_data_socket(data_socket).split("\r\n")
                data_socket.close()

                for line in response:
                    if line and not line.startswith("total"):
                        parts = line.split()
                        name = parts[-1]
                        if line.startswith("d"):
                            self.download(
                                f"{remote_filename}/{name}", f"{local_filename}/{name}"
                            )
                        else:
                            self._download_file(
                                f"{remote_filename}/{name}", f"{local_filename}/{name}"
                            )
            else:
                # 如果是文件，直接下载文件
                self._download_file(remote_filename, local_filename)
        except Exception as e:
            print(f"Download error: {e}")
            traceback.print_exc()

    def _download_file(self, remote_filename: str, local_filename: str):
        local_file_size = 0
        if os.path.exists(local_filename):
            local_file_size = os.path.getsize(local_filename)
        else:
            local_file_size = -1  # 本地文件不存在

        try:
            data_socket = self.initialize_data_socket()

            if local_file_size == 0:
                print(f"{local_filename} exists but is empty. Downloading from the beginning.")
            elif local_file_size > 0:
                self.send_cmd(f"REST {local_file_size}")
                print(self.control_recv_all())

            self.send_cmd("RETR " + remote_filename)
            response = self.control_recv_all().split("\r\n")

            print(response[0])
            if response[0].startswith("550"):
                print(
                    f"Failed to retrieve {remote_filename}. Server response: {response[0]}"
                )
                return

            mode = "ab" if local_file_size > 0 else "wb"
            with open(local_filename, mode) as f:
                while True:
                    part = data_socket.recv(1024)
                    if not part:
                        break
                    f.write(part)
            print(f"Downloaded {local_filename}")
            if len(response) == 2:
                print(self.control_recv_all())
            else:
                print(response[1])
        except socket.error as e:
            print(f"Socket error: {e}")
        finally:
            data_socket.close()

    def upload(self, local_filename: str, remote_filename: str | None = None):
        if remote_filename is None:
            remote_filename = local_filename

        try:
            if os.path.isdir(local_filename):
                self.send_cmd(f"MKD {remote_filename}")
                response = self.control_recv_all()
                if not response.startswith("257"):
                    print(
                        f"Failed to create directory {remote_filename}. Server response: {response}"
                    )
                for item in os.listdir(local_filename):
                    local_path = os.path.join(local_filename, item)
                    remote_path = f"{remote_filename}/{item}"
                    self.upload(local_path, remote_path)
            else:
                self._upload_file(local_filename, remote_filename)
        except Exception as e:
            print(f"Upload error: {e}")

    def _upload_file(self, local_filename: str, remote_filename: str):
        local_file_size = os.path.getsize(local_filename)
        remote_file_size = 0
        data_socket = None

        try:
            self.send_cmd(f"SIZE {remote_filename}")
            response = self.control_recv_all()

            if response.startswith("213"):
                remote_file_size = int(response.split()[1])
            elif response.startswith("550"):
                # 远程文件不存在
                remote_file_size = -1

            # 如果远程文件大小为0，说明文件存在但为空
            if remote_file_size == 0:
                print(f"{remote_filename} exists on the server but is empty. Uploading from the beginning.")
                remote_file_size = 0

            # 如果远程文件大小与本地文件大小相同，跳过上传
            if remote_file_size == local_file_size:
                print(
                    f"{remote_filename} already exists on the server with the same size. Skipping upload."
                )
                return

            # 初始化数据通道
            data_socket = self.initialize_data_socket()

            # 如果远程文件大小小于本地文件大小，进行断点续传
            if remote_file_size > 0 and remote_file_size < local_file_size:
                self.send_cmd(f"REST {remote_file_size}")
                print(self.control_recv_all())

            self.send_cmd("STOR " + remote_filename)
            response = self.control_recv_all()
            if response.startswith("550"):
                print(
                    f"Failed to upload {remote_filename}. Server response: {response}"
                )
                return

            with open(local_filename, "rb") as f:
                f.seek(remote_file_size)
                while True:
                    chunk = f.read(1024)
                    if not chunk:
                        break
                    data_socket.send(chunk)
            print(f"Uploaded {local_filename} to {remote_filename}")
        except socket.error as e:
            print(f"Socket error: {e}")
        finally:
            if data_socket:
                data_socket.close()

    def quit(self):
        self.send_cmd("QUIT")
        self.s.close()


# def test_resume_download():
#     # Step 1: Connect and login to the FTP server
#     client = FTPClient(ip="127.0.0.1", port=21)
#     client.login(username="anonymous", password="anonymous@")
#     client.list()


#     client.download("src", "srctest")

#     client.quit()

#     print("Download resumed and completed successfully.")


# def test_resume_upload():
#     # Step 1: Connect and login to the FTP server
#     client = FTPClient(ip="127.0.0.1", port=21)
#     client.login(username="anonymous", password="anonymous@")
#     client.change_dir("账单")

#     # Create a test file to upload
#     test_filename = "src"

#     client.upload(test_filename, "src_test")

#     client.quit()

#     print("Upload resumed and completed successfully.")


# # Run the test
# test_resume_download()
# # test_resume_upload()
client = FTPClient(ip="jyywiki.cn", port=21)
client.login(username="anonymous", password="anonymous@")
client.list()
client.change_dir("os")
client.list()

client.upload("pdm.lock")

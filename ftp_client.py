import socket
import time
import zlib
import os
import pdb


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
        time.sleep(0.01)
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

    def change_dir(self, path: str):
        self.send_cmd("CWD " + path)
        print(self.control_recv_all())

    def set_transfer_mode(self, transfer_mode: str):
        if transfer_mode not in ["binary", "text"]:
            raise ValueError("Invalid transfer mode. Use 'binary' or 'text'.")
        self.transfer_mode = transfer_mode
        cmd = "TYPE I" if transfer_mode == "binary" else "TYPE A"
        self.send_cmd(cmd)
        print(self.control_recv_all())

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
        print(self.control_recv_all())

    def download(self, filename: str):
        try:
            data_socket = self.initialize_data_socket()
            self.send_cmd("RETR " + filename)
            response = self.control_recv_all().split("\r\n")

            print(response[0])
            if response[0].startswith("550"):
                return

            with open(filename, "wb") as f:
                data = b""
                while True:
                    part = data_socket.recv(1024)
                    data += part
                    if len(part) < 1024:
                        data_socket.close()
                        break
                f.write(data)
            print(f"Downloaded {filename}")
            if len(response) == 2:
                print(self.control_recv_all())
            else:
                print(response[1])
        except socket.error as e:
            print(f"Socket error: {e}")
            data_socket.close()

    def upload(self, filename: str):
        """
        上传文件到服务器，支持分片上传。

        Args:
            filename: 要上传的文件名。
            chunk_size: 每次上传的块大小，默认1024字节。
        """
        try:
            data_socket = self.initialize_data_socket()
            self.send_cmd("STOR " + filename)
            response = self.control_recv_all()
            if response.startswith("550"):
                return
            with open(filename, "rb") as f:
                file_content = f.read()
                data_socket.send(file_content)
            print(f"Uploaded {filename}")
        except socket.error as e:
            print(f"Socket error: {e}")
        finally:
            data_socket.close()

    def quit(self):
        self.send_cmd("QUIT")
        self.s.close()


ftp_client = FTPClient("127.0.0.1", 21)
ftp_client.login()
ftp_client.change_dir("os")
ftp_client.list()
ftp_client.upload("base.py")
ftp_client.quit()

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

    def download(self, remote_filename: str, local_filename: str | None = None):
        if local_filename is None:
            local_filename = remote_filename

        local_file_size = 0
        if os.path.exists(local_filename):
            local_file_size = os.path.getsize(local_filename)

        try:
            data_socket = self.initialize_data_socket()

            if local_file_size > 0:
                self.send_cmd(f"REST {local_file_size}")
                print(self.control_recv_all())

            self.send_cmd("RETR " + remote_filename)
            response = self.control_recv_all().split("\r\n")

            print(response[0])
            if response[0].startswith("550"):
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

        local_file_size = os.path.getsize(local_filename)
        remote_file_size = 0
        data_socket = None

        try:
            self.send_cmd(f"SIZE {remote_filename}")
            response = self.control_recv_all()

            if response.startswith("213"):
                remote_file_size = int(response.split()[1])

            # If the remote file size matches the local file size, skip uploading
            if remote_file_size == local_file_size:
                print(
                    f"{remote_filename} already exists on the server with the same size. Skipping upload."
                )
                return

            # If the remote file size is less than the local file size, resume uploading
            data_socket = self.initialize_data_socket()

            if remote_file_size < local_file_size:
                self.send_cmd(f"REST {remote_file_size}")
                print(self.control_recv_all())

            self.send_cmd("STOR " + remote_filename)
            response = self.control_recv_all()
            if response.startswith("550"):
                print(f"Failed to upload {remote_filename}. Server response: {response}")
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


def test_resume_download():
    # Step 1: Connect and login to the FTP server
    client = FTPClient(ip="127.0.0.1", port=21)
    client.login(username="anonymous", password="anonymous@")
    client.change_dir("账单")
    client.list()

    # Step 2: Initiate the download of alipay_record_20240707_202209.csv
    try:
        # pdb.set_trace()
        print("Starting download of alipay_record_20240707_202209.csv...")
        data_socket = client.initialize_data_socket()
        client.send_cmd("RETR alipay_record_20240707_202209.csv")

        with open("alipay_record_20240707_202209.csv", "wb") as f:
            for _ in range(5):  # Intentionally download only a part of the file
                part = data_socket.recv(1024)
                if not part:
                    break
                f.write(part)
        print("Intentional disconnection to simulate interruption.")
        data_socket.close()  # Close the socket to simulate an interruption

    except Exception as e:
        print(f"Error during initial download: {e}")

    finally:
        client.quit()  # Disconnect from the server

    # Step 3: Reconnect and resume the download
    print("Reconnecting to resume download...")
    client = FTPClient(ip="127.0.0.1", port=21)
    client.login(username="anonymous", password="anonymous@")
    client.change_dir("账单")
    client.download("alipay_record_20240707_202209.csv", "alipay_record_resume.csv")

    client.quit()

    print("Download resumed and completed successfully.")


def test_resume_upload():
    # Step 1: Connect and login to the FTP server
    client = FTPClient(ip="127.0.0.1", port=21)
    client.login(username="anonymous", password="anonymous@")
    client.change_dir("账单")

    # Create a test file to upload
    test_filename = "Utility.code-workspace"

    try:
        # Step 2: Initiate the upload of Utility.code-workspace
        print(f"Starting upload of {test_filename}...")
        data_socket = client.initialize_data_socket()
        client.send_cmd("STOR " + test_filename)

        with open(test_filename, "rb") as f:
            for _ in range(5):  # Intentionally upload only a part of the file
                part = f.read(1024)
                if not part:
                    break
                data_socket.send(part)
        print("Intentional disconnection to simulate interruption.")
        data_socket.close()  # Close the socket to simulate an interruption

    except Exception as e:
        print(f"Error during initial upload: {e}")

    finally:
        client.quit()  # Disconnect from the server

    # Step 3: Reconnect and resume the upload
    print("Reconnecting to resume upload...")
    client = FTPClient(ip="127.0.0.1", port=21)
    client.login(username="anonymous", password="anonymous@")
    client.change_dir("账单")
    client.upload(test_filename, "upload_test_resume.txt")

    client.quit()

    print("Upload resumed and completed successfully.")


# Run the test
test_resume_download()
test_resume_upload()

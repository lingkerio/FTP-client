from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QListWidgetItem, QMessageBox
from PyQt5.QtCore import Qt,QDateTime

class RemoteFileDialog(QDialog):
    def __init__(self, ftp_client, parent=None):
        super().__init__(parent)
        self.ftp_client = ftp_client
        self.selected_file = None
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("选择远程文件")
        self.setGeometry(100, 100, 600, 400)
        
        layout = QVBoxLayout()
        
        # 文件列表视图
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.list_widget.itemClicked.connect(self.on_file_selected)
        
        # 刷新按钮
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.refresh_files)
        
        # 确定按钮
        self.ok_button = QPushButton("确定")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setEnabled(False)
        
        layout.addWidget(self.list_widget)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.ok_button)
        
        self.setLayout(layout)
        self.refresh_files()
        
    def refresh_files(self):
        try:
            # 列出当前目录下的文件
            raw_data = self.ftp_client.list()
            if raw_data:
                lines = raw_data.splitlines()
                self.list_widget.clear()
                for line in lines:
                    file_info = self.parse_ftp_list_line(line)
                    if file_info:
                        name = file_info[-1]  # 文件名是最后一项
                        item = QListWidgetItem(name)
                        self.list_widget.addItem(item)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法获取远程文件列表: {e}")

    def parse_ftp_list_line(self, line):
        # 解析FTP LIST命令的单行响应
        parts = line.split(maxsplit=8)
        if len(parts) < 9:
            return None
        permissions = parts[0]
        num_links = int(parts[1])
        owner = parts[2]
        group = parts[3]
        size = int(parts[4])
        mod_time_str = f"{parts[5]} {parts[6]} {QDateTime.currentDateTime().toString('yyyy')}"
        name = parts[-1]
        return permissions, num_links, owner, group, size, mod_time_str, name

    def on_file_selected(self, item):
        self.selected_file = item.text()
        self.ok_button.setEnabled(True)
        
    def get_selected_file(self):
        return self.selected_file


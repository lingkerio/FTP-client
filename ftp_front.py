import sys
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTreeView,
    QFileSystemModel,
    QSplitter,
    QStatusBar,
    QToolBar,
    QAction,
    QLabel,
    QHeaderView,
    QCheckBox,
    QMessageBox,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem
import os

# 导入后端 FTP 客户端
from backend import FTPClient as BackendFTPClient


class FTPClient(QWidget):
    # 定义信号，用于在连接成功或失败时通知界面更新
    connection_status_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.initUI()
        self.backend_ftp_client = None  # 后端 FTP 客户端实例
        self.remote_files_info = []  # 存储远程文件的信息

    def initUI(self):
        self.setWindowTitle("FTP 客户端")
        self.setGeometry(100, 100, 900, 600)

        # 顶部连接栏
        self.host_input = QLineEdit(self)
        self.host_input.setPlaceholderText("FTP 服务器地址")
        self.port_input = QLineEdit(self)
        self.port_input.setPlaceholderText("端口")
        self.port_input.setText("21")  # 默认 FTP 端口

        # 用户名相关输入
        self.username_layout = QHBoxLayout()
        self.user_input = QLineEdit(self)
        self.user_input.setPlaceholderText("用户名")
        self.anonymous_checkbox = QCheckBox("匿名", self)
        self.anonymous_checkbox.stateChanged.connect(self.toggle_anonymous)
        self.username_layout.addWidget(self.user_input)
        self.username_layout.addWidget(self.anonymous_checkbox)

        self.pass_input = QLineEdit(self)
        self.pass_input.setPlaceholderText("密码")
        self.pass_input.setEchoMode(QLineEdit.Password)

        self.show_password_checkbox = QCheckBox("显示密码", self)
        self.show_password_checkbox.stateChanged.connect(self.toggle_password_visibility)

        self.connect_btn = QPushButton("连接", self)
        self.connect_btn.setIcon(QIcon("C:\\Users\\86151\\Desktop\\icons\\connect.png"))  # 添加图标

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.host_input)
        top_layout.addWidget(self.port_input)
        top_layout.addLayout(self.username_layout)
        top_layout.addWidget(self.pass_input)
        top_layout.addWidget(self.show_password_checkbox)
        top_layout.addWidget(self.connect_btn)

        # 文件搜索栏
        self.search_label = QLabel("搜索: ", self)
        self.search_input = QLineEdit(self)
        self.search_button = QPushButton("搜索", self)
        self.search_button.setIcon(QIcon("C:\\Users\\86151\\Desktop\\icons\\search.png"))

        search_layout = QHBoxLayout()
        search_layout.addWidget(self.search_label)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)

        # 文件浏览区域
        self.local_model = QFileSystemModel()
        self.local_model.setRootPath("")
        self.local_view = QTreeView()
        self.local_view.setModel(self.local_model)
        self.local_view.setRootIndex(self.local_model.index(""))

        self.remote_view = QTreeView()
        self.model = QStandardItemModel()
        self.remote_view.setModel(self.model)
        self.model.setHorizontalHeaderLabels(["名称", "大小", "类型", "修改日期"])

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.local_view)
        splitter.addWidget(self.remote_view)

        # 工具栏
        self.toolbar = QToolBar()
        self.add_tool_actions()

        # 状态栏
        self.status_bar = QStatusBar()

        # 主布局
        main_layout = QVBoxLayout()
        main_layout.addLayout(top_layout)
        main_layout.addLayout(search_layout)
        main_layout.addWidget(self.toolbar)
        main_layout.addWidget(splitter)
        main_layout.addWidget(self.status_bar)

        self.setLayout(main_layout)
        self.setStyleSheet(self.get_stylesheet())

        # 连接按钮点击事件
        self.connect_btn.clicked.connect(self.connect_to_ftp)

        # 搜索按钮点击事件，搜索本地文件
        self.search_button.clicked.connect(self.search_local_files)

        # 表头点击事件，用于排序
        self.remote_view.header().sectionClicked.connect(self.sort_files)

        # 信号连接到状态栏更新函数
        self.connection_status_signal.connect(self.update_status_bar)

    def add_tool_actions(self):
        upload_action = QAction(QIcon("C:\\Users\\86151\\Desktop\\icons\\upload.png"), "上传", self)
        upload_action.triggered.connect(self.upload_file)

        download_action = QAction(QIcon("C:\\Users\\86151\\Desktop\\icons\\download.png"), "下载", self)
        download_action.triggered.connect(self.download_file)

        refresh_action = QAction(QIcon("C:\\Users\\86151\\Desktop\\icons\\refresh.png"), "刷新", self)
        refresh_action.triggered.connect(self.refresh_remote_files)

        delete_action = QAction(QIcon('C:\\Users\\86151\\Desktop\\icons\\delete.png'), '删除', self)
        delete_action.triggered.connect(self.delete_file)

        self.toolbar.addAction(upload_action)
        self.toolbar.addAction(download_action)
        self.toolbar.addAction(refresh_action)
        self.toolbar.addAction(delete_action)


    def connect_to_ftp(self):
        host = self.host_input.text()
        port = int(self.port_input.text())
        username = self.user_input.text()
        password = self.pass_input.text()

        try:
            # 创建后端 FTP 客户端实例
            self.backend_ftp_client = BackendFTPClient(ip=host, port=port)
            # 执行连接和登录
            self.backend_ftp_client.connect()
            self.backend_ftp_client.login(username=username, password=password)
            # 发出连接成功信号
            self.connection_status_signal.emit("连接成功")
            self.refresh_remote_files()  # 刷新远程文件列表
        except Exception as e:
            # 发出连接失败信号
            self.connection_status_signal.emit(f"连接失败: {str(e)}")

    def refresh_remote_files(self):
        if not self.backend_ftp_client:
            QMessageBox.warning(self, "错误", "未连接到任何 FTP 服务器")
            return

        try:
            files_info = self.backend_ftp_client.list()  # 获取远程文件列表
            self.model.removeRows(0, self.model.rowCount())
            
            # 遍历并显示远程文件信息
            for file_info in files_info:
                name_item = QStandardItem(file_info['name'])
                size_item = QStandardItem(str(file_info['size']))
                type_item = QStandardItem(file_info['type'])
                date_item = QStandardItem(file_info['date_modified'])

                self.model.appendRow([name_item, size_item, type_item, date_item])
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法刷新远程文件列表: {str(e)}")

    def download_file(self):
        if not self.backend_ftp_client:
            QMessageBox.warning(self, "错误", "未连接到任何 FTP 服务器")
            return

        selected_indexes = self.remote_view.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.warning(self, "错误", "未选择任何要下载的文件")
            return

        for index in selected_indexes:
            file_name = self.model.itemFromIndex(index).text()
            local_path = os.path.join(self.local_model.rootPath(), file_name)

            try:
                self.backend_ftp_client.download(remote_path=file_name, local_path=local_path)
                QMessageBox.information(self, "成功", f"成功下载 {file_name}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"下载 {file_name} 失败: {str(e)}")


    def delete_file(self):
        if not self.backend_ftp_client:
            QMessageBox.warning(self, "错误", "未连接到任何 FTP 服务器")
            return

        selected_indexes = self.remote_view.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.warning(self, "错误", "未选择任何要删除的文件")
            return

        for index in selected_indexes:
            file_name = self.model.itemFromIndex(index).text()

            try:
                self.backend_ftp_client.delete(file_name)
                self.model.removeRow(index.row())
                QMessageBox.information(self, "成功", f"成功删除 {file_name}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除 {file_name} 失败: {str(e)}")


    def upload_file(self):
        if not self.backend_ftp_client:
            QMessageBox.warning(self, "错误", "未连接到任何 FTP 服务器")
            return

        selected_indexes = self.local_view.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.warning(self, "错误", "未选择任何要上传的文件")
            return

        for index in selected_indexes:
            file_path = self.local_model.filePath(index)
            file_name = os.path.basename(file_path)

            try:
                self.backend_ftp_client.upload(local_path=file_path, remote_path=file_name)
                QMessageBox.information(self, "成功", f"成功上传 {file_name}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"上传 {file_name} 失败: {str(e)}")

    def search_local_files(self):
        search_term = self.search_input.text().lower()
        self.local_view.setRootIndex(self.local_model.index(""))
        self.local_view.setCurrentIndex(self.local_model.index(""))

        def search_recursively(index):
            if not index.isValid():
                return

            file_name = self.local_model.fileName(index).lower()
            if search_term in file_name:
                self.local_view.expand(index)

            for row in range(self.local_model.rowCount(index)):
                child_index = self.local_model.index(row, 0, index)
                search_recursively(child_index)

        search_recursively(self.local_model.index(""))

    def sort_files(self, logical_index):
        self.remote_view.sortByColumn(logical_index, Qt.AscendingOrder)

    def toggle_anonymous(self, state):
        if state == Qt.Checked:
            self.user_input.setText("anonymous")
            self.pass_input.setEnabled(False)
        else:
            self.user_input.clear()
            self.pass_input.setEnabled(True)

    def toggle_password_visibility(self, state):
        if state == Qt.Checked:
            self.pass_input.setEchoMode(QLineEdit.Normal)
        else:
            self.pass_input.setEchoMode(QLineEdit.Password)

    def update_status_bar(self, message):
        self.status_bar.showMessage(message)

    def get_stylesheet(self):
        return """
        QWidget {
            font-size: 14px;
        }
        QPushButton {
            background-color: #0099FF;
            color: white;
            border-radius: 5px;
            padding: 5px;
        }
        QPushButton:hover {
            background-color: #003d80;
        }
        QLineEdit, QCheckBox, QLabel {
            padding: 2px;
        }
        QStatusBar {
            background-color: #f0f0f0;
            border-top: 1px solid #ccc;

        }
        """

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ftp_client = FTPClient()
    ftp_client.show()
    sys.exit(app.exec_())

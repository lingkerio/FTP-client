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
    QFileDialog,
    QMenu,
    QTextEdit,
    QDialog,
)
from PyQt5.QtCore import Qt, pyqtSignal, QDir, QModelIndex, QDateTime,QUrl
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem,QDesktopServices
import os
import sys
import calendar


# 导入后端 FTP 客户端
from back import FTPClient as BackendFTPClient

def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


class FTPClient(QWidget):
    # 定义信号，用于在连接成功或失败时通知界面更新
    connection_status_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.initUI()
        self.backend_ftp_client = None  # 后端 FTP 客户端实例
        self.remote_files_info = []  # 存储远程文件的信息
        self.is_connected = False  # 连接状态
        self.setWindowIcon(QIcon(resource_path("icons\\ftp.ico")))


    def initUI(self):
        self.setWindowTitle("FTP 客户端")
        self.setGeometry(400, 100, 1200, 900)  # 增大窗口尺寸以显示日志

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
        self.connect_btn.setIcon(QIcon(resource_path('icons\\connect.png')))  # 添加图标

        self.quit_btn = QPushButton("断开", self)
        self.quit_btn.setIcon(QIcon(resource_path('icons\\quit.png')))

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.host_input)
        top_layout.addWidget(self.port_input)
        top_layout.addLayout(self.username_layout)
        top_layout.addWidget(self.pass_input)
        top_layout.addWidget(self.show_password_checkbox)
        top_layout.addWidget(self.connect_btn)
        top_layout.addWidget(self.quit_btn)

        # 文件搜索栏
        self.search_label = QLabel("搜索: ", self)
        self.search_input = QLineEdit(self)
        self.search_button = QPushButton("搜索", self)
        self.search_button.setIcon(QIcon(resource_path('icons\\search.png')))

        search_layout = QHBoxLayout()
        search_layout.addWidget(self.search_label)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)

        
        # 文件浏览区域
        self.local_model = QFileSystemModel()
        # 空字符串表示根路径，展示整个文件系统
        self.local_model.setRootPath("")
        self.local_view = QTreeView()
        self.local_view.setModel(self.local_model)
        # 不需要手动设置根索引，以下行应该被移除或注释掉
        # self.local_view.setRootIndex(self.local_model.index(QDir.rootPath()))
        self.local_view.setSortingEnabled(True)  # 启用排序功能

        self.remote_view = QTreeView()
        self.model = QStandardItemModel()
        self.remote_view.setModel(self.model)
        self.model.setHorizontalHeaderLabels([
            "名称", "大小" ,"修改日期和时间","类型和权限", "硬链接数", "所有者", "所有组"
        ])
        self.remote_view.setSortingEnabled(True)  # 启用排序功能

        splitter = QSplitter(Qt.Horizontal)
        splitter.setSizes([400, 400]) 
        splitter.addWidget(self.local_view)
        splitter.addWidget(self.remote_view)
        

        # 工具栏
        self.toolbar = QToolBar()
        self.add_tool_actions()

        # 状态栏
        self.status_bar = QStatusBar()

        # 日志输出区域
        self.log_output = QTextEdit(self)
        self.log_output.setReadOnly(True)  # 日志只读
        self.log_output.setStyleSheet("background-color: #f5f5f5;")  # 设置背景色

        # 主布局
        main_layout = QVBoxLayout()
        main_layout.addLayout(top_layout)
        main_layout.addLayout(search_layout)
        main_layout.addWidget(self.toolbar)
        main_layout.addWidget(splitter)
        main_layout.addWidget(self.log_output)  # 添加日志区域
        main_layout.addWidget(self.status_bar)

        self.setLayout(main_layout)
        self.setStyleSheet(self.get_stylesheet())

        # 连接按钮点击事件
        self.connect_btn.clicked.connect(self.connect_to_ftp)

        #断开按钮点击事件
        self.quit_btn.clicked.connect(self.quit_ftp)

        # 搜索按钮点击事件，搜索本地文件
        self.search_button.clicked.connect(self.search_local_files)

        # 表头点击事件，用于排序
        self.remote_view.header().sectionClicked.connect(self.sort_files)

        # 信号连接到状态栏更新函数
        self.connection_status_signal.connect(self.update_status_bar)

        # 添加右键菜单
        self.remote_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.remote_view.customContextMenuRequested.connect(self.open_context_menu)
        self.remote_view.doubleClicked.connect(self.on_remote_view_double_clicked)

        # 为左侧文件视图添加鼠标点击事件
        self.local_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.local_view.customContextMenuRequested.connect(self.open_local_context_menu)


    def add_tool_actions(self):
        upload_action = QAction(QIcon(resource_path('icons\\upload.png')), "上传", self)
        upload_action.triggered.connect(self.upload_file)

        download_action = QAction(QIcon(resource_path('icons\\download.png')), "下载", self)
        download_action.triggered.connect(self.download_file)

        refresh_action = QAction(QIcon(resource_path('icons\\refresh.png')), "刷新", self)
        refresh_action.triggered.connect(self.refresh_remote_files)


        self.toolbar.addAction(upload_action)
        self.toolbar.addAction(download_action)
        self.toolbar.addAction(refresh_action)
        

        # 在工具栏中添加记录日志的操作
        log_action = QAction(QIcon(resource_path('icons\\log.png')), '查看日志', self)
        log_action.triggered.connect(self.show_log)
        self.toolbar.addAction(log_action)

        return_action=QAction(QIcon(resource_path('icons\\return.png')), '返回上一级', self)
        return_action.triggered.connect(self.navigate_to_parent_directory)
        self.toolbar.addAction(return_action)

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
        self.log(message)  # 在日志中记录状态更新

    def log(self, message):
        # 日志消息格式化，添加时间戳
        log_message = f"[{QDateTime.currentDateTime().toString('yyyy-MM-dd HH:mm:ss')}] {message}"
        self.log_output.append(log_message)
        print(log_message)  # 在控制台输出日志（可选）

    def get_stylesheet(self):
        return """
        QWidget {
            font-size: 18px;
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
        QTextEdit {
            border: 1px solid #ccc;
            background-color: #f5f5f5;
        }
        """

    def connect_to_ftp(self):
        host = self.host_input.text()
        port = int(self.port_input.text())
        username = self.user_input.text()
        password = self.pass_input.text()
        anonymous = self.anonymous_checkbox.isChecked()

        if anonymous:
            username = "anonymous"
            password = "anonymous@"

        try:
            self.backend_ftp_client = BackendFTPClient(host, port)
            self.backend_ftp_client.login(username, password)
            self.connection_status_signal.emit("连接成功")
            self.is_connected = True
            self.refresh_remote_files()
            self.log(f"连接到FTP服务器 {host}:{port} 成功。")  # 记录连接成功日志
        except Exception as e:
            self.connection_status_signal.emit(f"连接失败: {str(e)}")
            self.log(f"连接失败: {str(e)}")  # 记录连接失败日志



    def quit_ftp(self):
        try:
            self.backend_ftp_client.quit()
            self.model.clear()
            self.log(f"断开FTP服务器成功。")  # 记录断开成功日志
        except Exception as e:
            self.connection_status_signal.emit(f"断开失败: {str(e)}")
            self.log(f"断开失败: {str(e)}")  # 记录断开失败日志


    def refresh_remote_files(self):
        if self.backend_ftp_client and self.is_connected:
            try:
                # 从后端FTP客户端获取远程文件列表数据
                raw_data = self.backend_ftp_client.list_content()
                # 检查返回的数据是否为None或空字符串
                if raw_data is None or raw_data.strip() == '':
                    self.log("从FTP服务器接收到的数据为空。")
                    self.connection_status_signal.emit("从FTP服务器接收到的数据为空。")
                    return

                # 清空当前模型以准备更新
                self.model.clear()
                self.model.setHorizontalHeaderLabels([
            "名称", "大小" ,"修改日期和时间","类型和权限", "硬链接数", "所有者", "所有组"
        ])
                # 解析每行数据
                lines = raw_data.splitlines()
                self.parse_ftp_list_line(lines[0])
                for line in lines:
                    file_info = self.parse_ftp_list_line(line)
                    if file_info:
                        # 使用文件信息创建QStandardItem并添加到模型
                        permissions, num_links, owner, group, size, mod_time_str, name = file_info
                        name_item = QStandardItem(name)
                        mod_time = QDateTime.fromString(f"{mod_time_str} {QDateTime.currentDateTime().toString('yyyy')}", '/MMM/dd HH:mm')
                        permissions_item = QStandardItem(permissions)
                        permissions_item = QStandardItem(f"File Folder") if permissions_item.text().startswith('d') else QStandardItem(f"{self.get_file_type(name)}")
                        num_links_item = QStandardItem(str(num_links))
                        owner_item = QStandardItem(owner)
                        group_item = QStandardItem(group)
                        size_item = QStandardItem(f"{size} B") if size!=4096 else QStandardItem(str(size))
                        mod_time_item = QStandardItem(mod_time_str)

                        # 根据权限字段的开头判断是文件还是文件夹，并设置相应图标
                        icon = QIcon(resource_path('icons\\folder.png')) if permissions.startswith('d') else QIcon(resource_path('icons\\file.png'))
                        name_item.setIcon(icon)

                        # 将文件信息作为一行添加到模型
                        self.model.appendRow([name_item, size_item, mod_time_item,permissions_item,num_links_item, owner_item, group_item])

                self.connection_status_signal.emit("远程文件列表刷新成功。")
                self.log("远程文件列表刷新成功。")

            except Exception as e:
                # 记录异常信息
                error_message = f"刷新远程文件失败: {str(e)}"
                self.connection_status_signal.emit(error_message)
                self.log(error_message)
                # 如果可能，打印异常的堆栈跟踪
                import traceback
                self.log(traceback.format_exc())



    def parse_ftp_list_line(self,line):  
    # 解析从FTP服务器接收到的单行文件列表信息  
        parts = line.split() 
        if len(parts) < 9:  
            return None  # 跳过格式不正确的行  
        permissions = parts[0]  
        num_links = int(parts[1])  
        owner = parts[2]  
        group = parts[3]  
        size = int(parts[4])  
        month= parts[5]  # 月份和日期可能在一起  
        day= parts[6]  # 时间  
        time=parts[7]
        name = ' '.join(parts[8:])  # 文件名可能是多个单词  
        month=self.convert_month_to_number(month)
        # 格式化时间戳  
        mod_time_str = f"2024/{month}/{day} {time}"  
        return permissions, num_links, owner, group, size, mod_time_str, name

    
    def upload_file(self):
        if self.backend_ftp_client and self.is_connected:
            local_file_path = QFileDialog.getOpenFileName(self, "选择要上传的文件")[0]
            if local_file_path:
                print(local_file_path)
                file_name = os.path.basename(local_file_path)
                try:
                    self.backend_ftp_client.upload(local_file_path, file_name)
                    self.connection_status_signal.emit(f"上传成功: {file_name}")
                    self.refresh_remote_files()  # 上传成功后刷新远程文件列表
                except Exception as e:
                    self.connection_status_signal.emit(f"上传失败: {str(e)}")

        

    def download_file(self):
        if self.backend_ftp_client and self.is_connected:
            # 获取远程视图中选中的文件
            selected_indexes = self.remote_view.selectedIndexes()
            if not selected_indexes:
                # 如果没有选中的远程文件，显示提示信息并返回
                QMessageBox.information(self, "提示", "请在远程文件列表中选择一个文件。")
                return

            # 获取远程文件名
            name_item = self.model.itemFromIndex(selected_indexes[0])
            remote_file_name = name_item.text()

            # 使用QFileDialog弹出保存文件的对话框
            save_path = QFileDialog.getSaveFileName(self, "选择保存位置", remote_file_name)
            if not save_path[0]:  # 用户取消操作或未输入文件名
             return

            # save_path[0] 已经是用户选择的完整本地路径（包括文件名和扩展名）
            local_file_name = save_path[0]

        try:
                # 执行下载操作，传入远程文件名和本地文件名
                print(remote_file_name)
                print("hello world")
                self.backend_ftp_client.download(remote_file_name, local_file_name)
                self.connection_status_signal.emit(f"下载成功: {remote_file_name}")
                self.refresh_remote_files()# 下载成功后刷新远程文件列表
                self.log(f"文件 '{remote_file_name}' 下载成功，保存为 '{local_file_name}'")
        except Exception as e:
                error_message = f"下载失败: {str(e)}"
                self.connection_status_signal.emit(error_message)
                self.log(error_message)
                # 显示错误信息
                QMessageBox.critical(self, "下载失败", f"文件 '{remote_file_name}' 下载失败。\n错误: {error_message}")



    def search_local_files(self):
            search_text = self.search_input.text().strip()
            if search_text:
                root_index = self.local_model.index(QDir.rootPath())
                self.local_view.setRootIndex(root_index)
                for row in range(self.local_model.rowCount(root_index)):
                    index = self.local_model.index(row, 0, root_index)
                    file_name = self.local_model.fileName(index)
                    if search_text.lower() in file_name.lower():
                        self.local_view.setCurrentIndex(index)
                        self.local_view.scrollTo(index)
                        self.log(f"本地文件搜索匹配成功: {file_name}")  # 记录搜索日志
                        break
                else:
                    QMessageBox.information(self, "提示", "未找到匹配的本地文件。")
                    self.log("本地文件搜索无匹配项。")  # 记录无匹配日志

    def delete_file(self):
        if self.backend_ftp_client and self.is_connected:
            selected_indexes = self.remote_view.selectedIndexes()
            if selected_indexes:
                name_item = self.model.itemFromIndex(selected_indexes[0])
                file_name = name_item.text()
                confirm = QMessageBox.question(self, "确认删除", f"确定要删除文件 {file_name} 吗？", QMessageBox.Yes | QMessageBox.No)
                if confirm == QMessageBox.Yes:
                    try:
                        self.backend_ftp_client.send_cmd(f"DELE {file_name}")
                        self.connection_status_signal.emit(f"删除成功: {file_name}")
                        self.refresh_remote_files()  # 删除成功后刷新远程文件列表
                        self.log(f"文件删除成功: {file_name}")  # 记录删除日志
                    except Exception as e:
                        error_message = f"删除失败: {str(e)}"
                        self.connection_status_signal.emit(error_message)
                        self.log(error_message)  # 记录删除失败日志

    def sort_files(self, logicalIndex):
        if self.remote_files_info:
            self.remote_files_info.sort(key=lambda x: x[logicalIndex])
            self.refresh_remote_files()
            self.log("远程文件排序成功。")  # 记录排序日志

    def open_context_menu(self, position):
     if self.is_connected:
        indexes = self.remote_view.selectedIndexes()
        if indexes:
            menu = QMenu()
            download_action = menu.addAction("下载")
            transfer_mode_menu = menu.addMenu("选择传输模式")
            binary_action = transfer_mode_menu.addAction("二进制")
            text_action = transfer_mode_menu.addAction("文本")
            transfer_method_menu = menu.addMenu("选择传输方法")
            stream_action=transfer_method_menu.addAction("流摸式")
            block_action=transfer_method_menu.addAction("块模式")
            compressed_action=transfer_method_menu.addAction("压缩模式")

            action = menu.exec_(self.remote_view.viewport().mapToGlobal(position))
            if action == download_action:
                # 获取选中的远程文件路径
                selected_indexes = self.remote_view.selectedIndexes()
                if selected_indexes:
                    name_item = self.model.itemFromIndex(selected_indexes[0])
                    file_name = name_item.text()
                    # 弹出文件选择对话框让用户选择保存位置
                    save_path = QFileDialog.getSaveFileName(self, "选择保存位置", file_name)[0]
                    if save_path:
                        try:
                            self.backend_ftp_client.download(file_name, file_name)
                            self.connection_status_signal.emit(f"下载成功: {file_name}")
                            self.log(f"文件下载成功: {file_name}")  # 记录下载日志
                        except Exception as e:
                            error_message = f"下载失败: {str(e)}"
                            self.connection_status_signal.emit(error_message)
                            self.log(error_message)  # 记录下载失败日志
            elif action == binary_action:
                self.backend_ftp_client.set_transfer_mode("binary")
                self.log("传输模式设置为二进制。")  # 记录传输模式日志
            elif action == text_action:
                self.backend_ftp_client.set_transfer_mode("text")
                self.log("传输模式设置为文本。")  # 记录传输模式日志
            elif action ==stream_action:
                self.backend_ftp_client.set_transfer_method("stream")
                self.log("传输方式设置为流模式。")  # 记录传输方式日志
            elif action ==block_action:
                self.backend_ftp_client.set_transfer_method("block")
                self.log("传输方式设置为块模式。")  # 记录传输方式日志
            elif action ==compressed_action:
                self.backend_ftp_client.set_transfer_method("compressed")
                self.log("传输方式设置为压缩模式。")  # 记录传输方式日志

    
    def open_local_context_menu(self, position):
        if self.is_connected:
            indexes = self.local_view.selectedIndexes()
            if indexes:
                menu = QMenu()
                upload_action = menu.addAction("上传")
                transfer_mode_menu = menu.addMenu("选择传输模式")
                binary_action = transfer_mode_menu.addAction("二进制")
                text_action = transfer_mode_menu.addAction("文本")
                transfer_method_menu = menu.addMenu("选择传输方法")
                stream_action = transfer_method_menu.addAction("流模式")
                block_action = transfer_method_menu.addAction("块模式")
                compressed_action = transfer_method_menu.addAction("压缩模式")

                action = menu.exec_(self.local_view.viewport().mapToGlobal(position))
                if action == upload_action:
                # 获取选中的本地文件路径
                    selected_index = indexes[0]
                    file_path = self.local_model.filePath(selected_index)
                    file_name = os.path.basename(file_path)
                # 弹出文件选择对话框让用户选择保存位置（此处可根据实际需求决定是否保留）
                # save_path = QFileDialog.getSaveFileName(self, "选择位置", file_name)[0]
                        # 弹出文件选择对话框让用户选择保存位置（此处可根据实际需求决定是否保留）
                        # save_path = QFileDialog.getSaveFileName(self, "选择位置", file_name)[0]
                    if file_path:
                            try:
                                self.backend_ftp_client.upload(file_path, file_name)  # 使用本地文件路径作为第一个参数
                                self.connection_status_signal.emit(f"上传成功: {file_name}")
                                self.log(f"文件上传成功: {file_name}")  # 记录上传日志
                            except Exception as e:
                                error_message = f"上传失败: {str(e)}"
                                self.connection_status_signal.emit(error_message)
                                self.log(error_message)  # 记录上传失败日志
                elif action == binary_action:
                    self.backend_ftp_client.set_transfer_mode("binary")
                    self.log("传输模式设置为二进制。")  # 记录传输模式日志
                elif action == text_action:
                    self.backend_ftp_client.set_transfer_mode("text")
                    self.log("传输模式设置为文本。")  # 记录传输模式日志
                elif action == stream_action:
                    self.backend_ftp_client.set_transfer_method("stream")
                    self.log("传输方式设置为流模式。")  # 记录传输方式日志
                elif action == block_action:
                    self.backend_ftp_client.set_transfer_method("block")
                    self.log("传输方式设置为块模式。")  # 记录传输方式日志
                elif action == compressed_action:
                    self.backend_ftp_client.set_transfer_method("compressed")
                    self.log("传输方式设置为压缩模式。")





    def show_log(self):
        # 显示日志窗口
        log_dialog = QMessageBox(self)
        log_dialog.setWindowTitle("操作日志")
        log_dialog.setText("\n".join(self.log_output.toPlainText().splitlines()))
        log_dialog.exec_()

    def closeEvent(self, event):
        if self.backend_ftp_client and self.is_connected:
            self.backend_ftp_client.quit()
        event.accept()
    

    def on_remote_view_double_clicked(self, index):
        if not self.is_connected:
            return

        try:
            # 假设 self.backend_ftp_client.list_content() 返回当前目录的文件列表
            raw_data = self.backend_ftp_client.list_content()
            lines = raw_data.splitlines()
            index = index.row()  # 从 QModelIndex 中提取行索引
            # 获取双击的文件对应的行
            double_clicked_line = lines[index]
            file_info = self.parse_ftp_list_line(double_clicked_line)
            if file_info:
                permissions, num_links, owner, group, size, mod_time_str, name = file_info
                permissions_item = QStandardItem(permissions)
                name_item = QStandardItem(name)

                # 检查权限字段的第一个字符是否是 'd'
                if permissions_item.text().startswith('d'):
                    directory_name = name_item.text()  # 获取目录名称
                    try:
                        # 使用后端方法切换到远程目录
                        self.backend_ftp_client.change_dir(directory_name)
                        # 刷新视图以显示新目录的内容
                        self.refresh_remote_files()
                        self.log(f"成功切换到远程目录：{directory_name}")
                    except Exception as e:
                        # 处理切换目录时的异常
                        self.log(f"切换目录失败：{str(e)}")
                        self.connection_status_signal.emit(f"切换目录失败：{str(e)}")
        except Exception as e:
            # 处理获取文件列表时的异常
            self.log(f"获取文件列表失败：{str(e)}")
            self.connection_status_signal.emit(f"获取文件列表失败：{str(e)}")

    def show_upload_dialog(self, position=None):
        # 弹出文件选择对话框让用户选择要上传的文件
        local_file_path, _ = QFileDialog.getOpenFileName(self, "选择要上传的文件")
        if local_file_path:
            file_name = os.path.basename(local_file_path)
            try:
                # 执行上传操作
                self.backend_ftp_client.upload(local_file_path, file_name)
                self.connection_status_signal.emit(f"上传成功: {file_name}")
                self.refresh_remote_files()  # 刷新远程文件列表
                self.log(f"文件上传成功: {file_name}")  # 记录上传日志
            except Exception as e:
                error_message = f"上传失败: {str(e)}"
                self.connection_status_signal.emit(error_message)
                self.log(error_message)  # 记录上传失败日志

    def navigate_to_parent_directory(self):
        if not self.is_connected:
            return
        # 切换到父目录
        self.backend_ftp_client.change_dir("..")
        self.refresh_remote_files()
        self.log("已返回上一级目录。")

    def convert_month_to_number(self,month_name):
        month_name = month_name.title()  # 确保输入的月份名称首字母大写
        for month_num, month_abbr in enumerate(calendar.month_abbr[1:], 1):
            if month_abbr == month_name:
                return month_num
        raise ValueError(f"无效的月份名称: {month_name}")
    

    if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the PyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app 
    # path into variable _MEIPASS'.
        application_path = sys._MEIPASS
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))

    def get_file_type(self,name):
            file_types = {
                'txt': 'Text File',
        'pdf': 'PDF Document',
        'docx': 'Word Document',
        'xlsx': 'Excel Spreadsheet',
        'pptx': 'PowerPoint Presentation',
        'jpg': 'JPEG Image',
        'jpeg': 'JPEG Image',
        'png': 'PNG Image',
        'gif': 'GIF Image',
        'bmp': 'Bitmap Image',
        'tiff': 'TIFF Image',
        'svg': 'Scalable Vector Graphics',
        'log': 'Log File',
        'xml': 'XML File',
        'html': 'HTML Document',
        'css': 'CSS File',
        'js': 'JavaScript File',
        'json': 'JSON File',
        'zip': 'ZIP Archive',
        'rar': 'RAR Archive',
        '7z': '7z Archive',
        'tar': 'TAR Archive',
        'wav': 'WAV Audio',
        'mp3': 'MP3 Audio',
        'avi': 'AVI Video',
        'mp4': 'MP4 Video',
        'mov': 'QuickTime Video',
        'exe': 'Executable File',
        'dll': 'Dynamic Link Library',
        'iso': 'ISO Disk Image',
        'bak': 'Backup File',
        'sln': 'Solution File',
        'csv': 'Comma-Separated Values',
        'yml': 'YAML File',
        'py': 'Python Script',
        'c': 'C Source File',
        'md': 'Markdown Document',
        'sh': 'Shell Script',
        'gdb': 'GDB Script',
        'h': 'C/C++ Header File',
        'S': 'Assembly Source File',
                # 可以继续添加更多的文件类型和扩展名
            }
            
            name_item = QStandardItem(name)
            name = name_item.text()
            # 然后获取文件的扩展名
            extension = (name.split('.')[-1] if '.' in name else 'unknown').lower()
            return file_types.get(extension, 'Unknown File Type')

if __name__ == "__main__":
    app = QApplication(sys.argv)
    client = FTPClient()
    client.show()
    sys.exit(app.exec_())

import sys
import serial.tools.list_ports
from PyQt5 import QtWidgets,QtCore
from main_window import Ui_MainWindow  # 假设生成的文件名为 main_window_ui.py
from matplotlib import rcParams
from matplotlib.figure import Figure 
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

type_name_mapping = {
    "F-H": "前后",
    "L-R": "左右",
    "ZBL1": "指拨轮1",
    "ZBL2": "指拨轮2"
}



class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        # 添加调试模式开关
        self.debug_mode = True  # 设置为 True 启用调试模式

        # 设置和串口之间的波特率
        self.baud_rate = 9600

        # 设置固定大小
        self.setFixedSize(960, 500)  

        # 初始化点的坐标
        self.curves = []
        self.serial_port = None

        # 设置 QGraphicsView 场景
        self.scene = QtWidgets.QGraphicsScene(self)
        self.graphicsView.setScene(self.scene)
        self.current_limit = 1050

        # 显示点列表和初始化图表
        self.setup_table_widget()

        # 禁用按钮
        self.set_button_state(False)
        self.connectRadioButton.setEnabled(False)
        self.set_radioButton_state(0)

        self.populate_com_ports()  # 自动填充串口
        self.connectButton.clicked.connect(self.connect_to_serial_port)  # 连接按钮点击
        self.sendDataButton.clicked.connect(self.send_points_to_serial) # 发送消息按钮点击
        self.serial_comboBox.currentIndexChanged.connect(self.on_serial_comboBox_change) # serial_comboBox内容控制
        self.curves_comboBox.currentIndexChanged.connect(self.on_curves_comboBox_change) # serial_comboBox内容控制
        self.receiveDataButton.clicked.connect(self.request_data_from_serial) # 点击读取数据
        self.disconnectButton.clicked.connect(self.disconnect) # 点击断开按钮
        self.sendAllDataButton.clicked.connect(self.send_all_points_to_serial) # 点击全部发送
        self.receiveAllDataButton.clicked.connect(self.request_all_data_from_serial) # 点击全部读取
        self.editAllButton.clicked.connect(self.edit_all_curves) # 点击编辑全部

        # 连接表格项更改信号以更新图表
        self.tableWidget.itemChanged.connect(self.update_point_from_table)
         # 连接电流最大值变化事件
        self.currentTypeComboBox.currentIndexChanged.connect(self.update_current_limits) 
        self.saved_curves = {}  # 用于存储曲线数据

    def update_current_limits(self):
        """根据选择的最大电流更新表格限制和图像显示"""
        current_type = self.currentTypeComboBox.currentText()
        if current_type == "最大电流 1050mA":
            self.current_limit = 1050
        elif current_type == "最大电流 2000mA":
            self.current_limit = 2000

        # 更新表格的限制值
        for row in range(self.tableWidget.rowCount()):
            item = self.tableWidget.item(row, 1)  # 获取电流值列
            if item:
                value = float(item.text())
                if value > self.current_limit:
                    item.setText(str(self.current_limit))  # 限制电流值不超过最大值


    def on_serial_comboBox_change(self):
        if self.serial_comboBox.currentText() == "刷新":
            self.populate_com_ports()  # 选择刷新时更新串口列表
    
    def on_curves_comboBox_change(self):
        """当曲线选择变化时，更新表格和折线图"""
        self.populate_table_widget()
        self.draw_plot()
    
    def populate_com_ports(self):
        """控制serial_comboBox状态"""
        self.serial_comboBox.clear()         # 清空 serial_comboBox 的内容
        ports = serial.tools.list_ports.comports()         # 获取所有可用的串口
        for port in ports:
            self.serial_comboBox.addItem(port.device) # 添加串口名称到 serial_comboBox
        self.serial_comboBox.addItem("刷新")  # 添加刷新选项

    def populate_curves_com_ports(self):
        self.curves_comboBox.clear()
        for curve in self.curves:
            self.curves_comboBox.addItem(curve['cname'])
        if self.curves_comboBox.count() > 0:
            self.curves_comboBox.setCurrentIndex(0)  # 默认选择第一个曲线
        self.populate_table_widget()
        self.draw_plot()

    def set_button_state(self,state = False):
        """控制按钮的禁用状态"""
        self.receiveDataButton.setEnabled(state)
        self.sendDataButton.setEnabled(state)
        self.sendAllDataButton.setEnabled(state)
        self.receiveAllDataButton.setEnabled(state)
        self.curves_comboBox.setEnabled(state)
        self.editAllButton.setEnabled(state)
        self.tableWidget.setEnabled(state)
        self.currentTypeComboBox.setEnabled(state)

    def set_radioButton_state(self,state=0):
        """控制radioButton的状态"""
        match state:
            case 0:#未连接状态
                self.connectRadioButton.setChecked(False)
                self.connectButton.setEnabled(True)
                self.connectRadioButton.setText("未连接")
            case 1:#连接失败状态
                self.connectRadioButton.setChecked(False)
                self.connectButton.setEnabled(True)
                self.connectRadioButton.setText("连接失败")
            case 2:#连接成功状态
                self.connectRadioButton.setChecked(True)
                self.connectButton.setEnabled(False)
                self.connectRadioButton.setText("连接成功")

    def connect_to_serial_port(self):
        """点击连接按钮"""
        response = self.send_data("FS connect")
        if response is None:
            self.set_radioButton_state(1)
            self.set_button_state(False)
            self.serial_comboBox.setEnabled(True)
            return 
        if response.startswith("connect success:"):
            data = response[len("connect success:"):]
            type_group = data.split(',')
            self.curves = []
            for type_name in type_group:
                # 如果映射表中有对应的中文名称，就使用它，否则使用 name 作为中文名称
                cname = type_name_mapping.get(type_name, type_name)
                points_for_curve = self.saved_curves.get(type_name, [(0, 0), (25, 250), (50, 500), (75, 750), (100, 1000)])  # 使用保存的数据
                curve = {
                    "name": type_name,
                    "cname": cname,
                    "points": points_for_curve
                }
                self.curves.append(curve)  # 将曲线添加到曲线列表中
            self.populate_curves_com_ports()

            self.set_radioButton_state(2)
            self.set_button_state(True)
            self.serial_comboBox.setEnabled(False)
        else:
            self.set_radioButton_state(1)
            self.set_button_state(False)
            self.serial_comboBox.setEnabled(True)

    def disconnect(self):
        """点击断开按钮"""
        # 存储当前曲线的数据
        self.save_curves_data()
        self.set_radioButton_state(0)
        self.set_button_state(False)
        self.serial_comboBox.setEnabled(True)

    def save_curves_data(self):
        """保存当前曲线的数据"""
        self.saved_curves = {curve["name"]: curve["points"] for curve in self.curves}

    def send_data(self,data):
        """发送数据"""
        selected_port = self.serial_comboBox.currentText()
        if selected_port == "刷新" or selected_port == "":
            QtWidgets.QMessageBox.warning(self, "错误", "请选择有效的串口！")
            return "未选择串口"
        
        try:
            self.serial_port = serial.Serial(selected_port, baudrate=self.baud_rate, timeout=1)  # 1秒超时
            if self.debug_mode:
                print(f"打开串口: {selected_port}")

            # 检查串口是否成功打开
            if not self.serial_port.is_open:
                QtWidgets.QMessageBox.warning(self, "错误", f"无法打开串口 {selected_port},请选择正确串口")
                return "串口无法打开"
            
            # 尝试发送数据
            try:
                if self.debug_mode:
                    print(f"发送数据: {data}")  # 打印发送的数据
                self.serial_port.write(data.encode())
            except serial.SerialTimeoutException:
                QtWidgets.QMessageBox.warning(self, "错误", "串口写入超时")
                self.serial_port.close()
                return "串口写入超时"
            except serial.SerialException as e:
                QtWidgets.QMessageBox.warning(self, "错误", f"串口写入失败: {str(e)}")
                self.serial_port.close()
                return f"串口写入失败: {str(e)}"       
            except Exception as e:
                # 捕获其他未知错误
                QtWidgets.QMessageBox.warning(self, "错误", f"发生未知错误: {str(e)}")
                return "未知错误"     

            # 等待回应
            response = self.wait_for_response()

            # 关闭串口
            if self.serial_port.is_open:
                self.serial_port.close()
                if self.debug_mode:
                    print("关闭串口")

            if self.debug_mode and response is not None:
                print(f"接收到回应: {response}")  # 打印接收到的回应
            return response 

        except serial.SerialException as e:
            QtWidgets.QMessageBox.warning(self, "错误", f"串口错误: {str(e)}")
            return "串口错误"
        except Exception as e:
            # 捕获其他未知错误
            QtWidgets.QMessageBox.warning(self, "错误", f"发生未知错误: {str(e)}")
            return "未知错误"
        finally:
            # 确保串口关闭
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
                print("关闭串口")
        
    def wait_for_response(self):
        """等待回应并处理"""
        self.response = None

        # 设置计时器超时为3秒
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.on_timeout)
        self.timer.start(3000)  # 3秒等待时间

        while self.response is None:
            QtWidgets.QApplication.processEvents()  # 保持应用响应，等待接收数据
            if self.serial_port.in_waiting > 0:  # 检查是否有可用数据
                response_data = self.serial_port.readline().decode('utf-8').strip()  # 读取一行数据并解码

                if response_data:
                    self.response = response_data  # 存储收到的响应
                    if self.debug_mode:
                        print(f"接收到数据: {response_data}")  # 打印接收到的数据
                    break
        # 停止计时器
        self.timer.stop()
        
        return response_data
    
    def on_timeout(self):
        """超时处理"""
        if self.response is None:
            self.response = "超时"  # 设置回应为超时

    def request_data_from_serial(self):
        """发送读取数据的请求"""
        # 获取曲线名称
        selected_curve_name = next((curve["name"] for curve in self.curves if curve["cname"] == self.curves_comboBox.currentText()), None)

        if selected_curve_name:
            # 拼接请求数据
            response = self.send_data("FS request points:" + selected_curve_name)
            if(self.check_data_format(response,selected_curve_name)):
                QtWidgets.QMessageBox.information(self, "成功", "数据读取成功！")
        else:
            QtWidgets.QMessageBox.warning(self, "错误", "没有找到对应的曲线！")

    def check_data_format(self, data,curve_name):
        if data is None:
            QtWidgets.QMessageBox.warning(self, "未接收到数据", "未能接收到数据，请检查连接。")
            return
        
        if data.startswith("Controller send points:"):
            # 提取坐标数据部分
            points_data = data[len("Controller send points:"):].strip()
            point_values = points_data.split(",")  # 按逗号分割坐标值

            # 调试：打印分割后的点值
            print(f"分割后的点值: {point_values}")
            # 检查数据格式是否正确并更新 points
            valid_data = True
            new_points = []
            for i in range(0, len(point_values), 2):  # 每两个值为一对坐标
                try:
                    x_value = float(point_values[i])  # x 坐标
                    y_value = float(point_values[i + 1])  # y 坐标

                    # 检查 x 和 y 坐标的范围
                    if 0 <= x_value <= 100 and 0 <= y_value <= self.current_limit:
                        new_points.append((x_value, y_value))
                    else:
                        valid_data = False
                        break
                except (ValueError, IndexError):
                    valid_data = False
                    break

            if valid_data and len(new_points) == 5:  # 确保有 5 对坐标
                # 获取当前选中的曲线的 cname
                selected_curve = next((curve for curve in self.curves if curve["name"] == curve_name), None)

                if selected_curve:
                    # 更新选中曲线的数据
                    selected_curve["points"] = new_points
                    self.populate_table_widget()  # 更新表格
                    self.draw_plot()  # 重绘图形
                    return True
                else:
                    QtWidgets.QMessageBox.warning(self, "数据错误", "未找到对应的曲线数据！")
            else:
                QtWidgets.QMessageBox.warning(self, "数据错误", "接收到的数据格式不正确或超出范围！")
        else:
            QtWidgets.QMessageBox.warning(self, "数据错误", "接收到的响应格式不正确，请检查设备。")
        return False

    def send_points_to_serial(self):
        """向选中的串口发送 points 数据"""
        selected_curve_name = self.curves_comboBox.currentText()
        selected_curve = next((curve for curve in self.curves if curve["cname"] == selected_curve_name), None)

        if selected_curve:
            # 获取当前曲线的 points
            points_to_send = selected_curve["points"]
            # 将 points 转换为字符串
            points_str = ",".join([f"{x},{y}" for x, y in points_to_send])
            # 将数据格式化并发送
            data_to_send = f"FS:{selected_curve['name']}/{points_str}\n"
            response = self.send_data(data_to_send)  # 发送数据并等待响应
            if response == "data send success":
                QtWidgets.QMessageBox.information(self, "成功", "数据写入成功！")
            else:
                QtWidgets.QMessageBox.warning(self, "失败", "数据写入失败！")

    def send_all_points_to_serial(self):
        """向选中的串口发送所有曲线的 points 数据"""
        all_data_sent = True  # 用来标记是否所有数据都成功发送

        for curve in self.curves:
            # 获取当前曲线的 points
            points_to_send = curve["points"]
            # 将 points 转换为字符串
            points_str = ",".join([f"{x},{y}" for x, y in points_to_send])
            # 将数据格式化并发送
            data_to_send = f"FS:{curve['name']}/{points_str}\n"
            response = self.send_data(data_to_send)  # 发送数据并等待响应

            if response != "data send success":
                all_data_sent = False  # 标记如果某个曲线数据发送失败

        # 在所有曲线数据发送完成后显示总结弹窗
        if all_data_sent:
            QtWidgets.QMessageBox.information(self, "成功", "所有曲线数据写入成功！")
        else:
            QtWidgets.QMessageBox.warning(self, "失败", "某些曲线数据写入失败，请检查连接。")
    
    def request_all_data_from_serial(self):
        """读取所有曲线数据"""
        all_data_receive = True
        for curve in self.curves:
            # 获取每个曲线的名称
            selected_curve_name = curve["name"]

            # 拼接请求数据
            response = self.send_data(f"FS request points:{selected_curve_name}")
            
            # 检查返回的数据格式并更新数据
            if self.check_data_format(response,selected_curve_name) is False:
                all_data_receive = False
                # 在所有曲线数据发送完成后显示总结弹窗
        if all_data_receive:
            QtWidgets.QMessageBox.information(self, "成功", "所有曲线数据读取成功！")
        else:
            QtWidgets.QMessageBox.warning(self, "失败", "某些曲线数据读取失败，请检查连接。")

    def setup_table_widget(self):
        """设置表格的行和列标题"""
        self.tableWidget.setRowCount(5)
        self.tableWidget.setColumnCount(2)
        self.tableWidget.setHorizontalHeaderLabels(["行程", "电流值"])
        
        # 设置行标题
        for i in range(5):
            self.tableWidget.setVerticalHeaderItem(i, QtWidgets.QTableWidgetItem(f"第{i + 1}点"))

        # 获取表格的宽度和高度
        table_width = self.tableWidget.width()-30
        table_height = self.tableWidget.height()-100

        # 获取标题的高度
        header_height = self.tableWidget.horizontalHeader().height()
        header_width = self.tableWidget.verticalHeader().width()
  
        # 计算可用高宽
        available_height = table_height - header_height
        available_width = table_width - header_width

        # 设置列宽（平均分配）
        self.tableWidget.setColumnWidth(0, available_width // 2)  # 行程列宽
        self.tableWidget.setColumnWidth(1, available_width // 2)  # 电流值列宽

        # 计算行高（根据可用高度和行数平均分配）
        row_height = available_height // self.tableWidget.rowCount()
        for i in range(self.tableWidget.rowCount()):
            self.tableWidget.setRowHeight(i, row_height)

        # 确保只自动调整已填充的行
        self.tableWidget.resizeRowsToContents()

    def populate_table_widget(self):
        """在 QTableWidget 中填充坐标点"""
        # 获取当前选中的曲线
        selected_curve_name = self.curves_comboBox.currentText()

        # 查找对应的曲线数据
        selected_curve = None
        for curve in self.curves:
            if curve["cname"] == selected_curve_name:
                selected_curve = curve
                break

        if selected_curve:
            points_for_curve = selected_curve["points"]

            for i in range(0, len(points_for_curve), 1):
                x = points_for_curve[i][0]
                y = points_for_curve[i][1]
                row = i  # 对应的行
                # 填入 x 坐标
                x_item = QtWidgets.QTableWidgetItem(str(x))
                x_item.setTextAlignment(QtCore.Qt.AlignCenter)  # 设置居中
                self.tableWidget.setItem(row, 0, x_item)
                # 填入 y 坐标
                y_item = QtWidgets.QTableWidgetItem(str(y))
                y_item.setTextAlignment(QtCore.Qt.AlignCenter)  # 设置居中
                self.tableWidget.setItem(row, 1, y_item)

    def update_point_from_table(self, item):
        """当 QTableWidget 中的点被编辑后更新 self.points 列表"""
        row = item.row()
        col = item.column()

        # 获取当前选中的曲线
        selected_curve_name = self.curves_comboBox.currentText()

        # 查找对应的曲线数据
        selected_curve = None
        for curve in self.curves:
            if curve["cname"] == selected_curve_name:
                selected_curve = curve
                break

        if selected_curve:
            try:
                # 读取更新后的值
                value = float(item.text())
                # 检查输入的值是否在 0 到 最大电流值 之间
                if 0 <= value <= self.current_limit:
                    # 更新 points 列表
                    if col == 0:  # 更新 x 坐标
                        selected_curve["points"][row] = (value, selected_curve["points"][row][1])
                    elif col == 1:  # 更新 y 坐标
                        selected_curve["points"][row] = (selected_curve["points"][row][0], value)

                    # 重新绘制图表
                    self.draw_plot()
                else:
                    QtWidgets.QMessageBox.warning(self, "输入错误", f"坐标值必须在 0 到 {self.current_limit} 之间")
                    # 恢复到原值
                    self.populate_table_widget()
            except ValueError:
                QtWidgets.QMessageBox.warning(self, "输入错误", "请输入有效的坐标")
                # 恢复到原值
                self.populate_table_widget()

    def draw_plot(self):
        """根据选中的曲线绘制折线图"""
        # 获取当前选中的曲线
        selected_curve_name = self.curves_comboBox.currentText()

        # 查找对应的曲线数据
        selected_curve = None
        for curve in self.curves:
            if curve["cname"] == selected_curve_name:
                selected_curve = curve
                break
        if selected_curve:
            # 获取当前曲线的点数据
            points_for_curve = selected_curve["points"]

            # 创建 Matplotlib 图形
            self.figure = Figure(figsize=(5, 4))
            self.canvas = FigureCanvas(self.figure)

            # 清除之前的绘图
            self.graphicsView.setScene(QtWidgets.QGraphicsScene(self))
            self.graphicsView.scene().addWidget(self.canvas)

            # 设置字体为支持中文的字体
            from matplotlib import rcParams
            rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体
            rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

            # 绘制折线图
            ax = self.figure.add_subplot(111)
            x_values = [point[0] for point in points_for_curve]  # x 坐标
            y_values = [point[1] for point in points_for_curve]  # y 坐标
            ax.set_title(f"曲线：{selected_curve['cname']}")  # 使用 cname 作为标题
            ax.plot(x_values, y_values, marker='o')
            ax.set_xlabel("行程 (%)")  # x 轴标题
            ax.set_ylabel("电流值 (mA)")  # y 轴标题
            ax.set_xlim(0, 100)
            ax.set_ylim(0, self.current_limit)

            self.canvas.draw()

    def edit_all_curves(self):
        """根据现有表格修改所有曲线的值"""
        for curve in self.curves:
            for row in range(self.tableWidget.rowCount()):
                try:
                    x_value = float(self.tableWidget.item(row, 0).text())  # 获取 x 坐标
                    y_value = float(self.tableWidget.item(row, 1).text())  # 获取 y 坐标
                    if 0 <= x_value <= 100 and 0 <= y_value <= self.current_limit:
                        curve["points"][row] = (x_value, y_value)  # 更新曲线的点
                    else:
                        QtWidgets.QMessageBox.warning(self, "输入错误", f"坐标值必须在 0 到 {self.current_limit} 之间")
                        return
                except ValueError:
                    QtWidgets.QMessageBox.warning(self, "输入错误", "请输入有效的坐标")
                    return
                
        QtWidgets.QMessageBox.information(self, "成功", "所有曲线的点已更新！")
                       
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
import sys
import numpy as np
from collections import deque
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QMessageBox, QDialog, QTableWidget, 
                             QTableWidgetItem, QGroupBox, QScrollArea, QLabel, QLineEdit, QPushButton, QComboBox,QHeaderView)
from PyQt5.QtGui import QColor, QIntValidator, QDoubleValidator
from PyQt5.QtCore import QTimer
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from current_reader import DataReader
from datetime import datetime
import os

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("压力检测系统")
        self.setGeometry(100, 100, 1200, 800)
        self.channel_num = 4
        self.data_reader = None
        self._init_ui()
        self._init_data_structures()

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        main_layout.addWidget(top_widget)

        self._init_left_panel(top_layout)
        self._init_right_panel(top_layout)
        self._init_control_panel(main_layout)

    def _init_left_panel(self, main_layout):
        left_panel = QScrollArea()
        left_content = QWidget()
        self.channel_layout = QVBoxLayout(left_content)
        self.channels = {}
        for i in range(1, self.channel_num+1):
            channel_box = QGroupBox(f"通道 {i}")
            layout = QVBoxLayout()
            self.channels[i] = QLabel("当前值: --\n初始值: --\n")
            layout.addWidget(self.channels[i])
            channel_box.setLayout(layout)
            channel_box.setFixedWidth(200)
            self.channel_layout.addWidget(channel_box)
        
        left_panel.setWidget(left_content)
        main_layout.addWidget(left_panel, stretch=2)

    def _init_right_panel(self, main_layout):
        matplotlib.rcParams['font.sans-serif'] = ['SimHei']
        matplotlib.rcParams['axes.unicode_minus'] = False

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        self.figure = Figure(figsize=(8, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("实时压力曲线")
        self.ax.set_xlabel("时间 (秒)")
        self.ax.set_ylabel("压力值")
        self.lines = [self.ax.plot([], [], label=f'通道 {i}')[0] for i in range(1, self.channel_num+1)]
        self.ax.legend()
        
        right_layout.addWidget(self.canvas)
        main_layout.addWidget(right_panel, stretch=5)

    def _init_control_panel(self, main_layout):
        control_container = QWidget()
        control_layout = QHBoxLayout(control_container)

        serial_group = QGroupBox("串口设置")
        serial_layout = QVBoxLayout(serial_group)
        
        self.serial_combo = QComboBox()
        self.refresh_serial_ports()
        
        serial_combo_layout = QHBoxLayout()
        serial_combo_layout.addWidget(self.serial_combo)
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_serial_ports)
        serial_combo_layout.addWidget(refresh_btn)
        serial_layout.addLayout(serial_combo_layout)
        
        self.connect_btn = QPushButton("连接")
        self.disconnect_btn = QPushButton("断开")
        self.connect_btn.clicked.connect(self.connect_serial)
        self.disconnect_btn.clicked.connect(self.disconnect_serial)
        self.disconnect_btn.setEnabled(False)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.connect_btn)
        btn_layout.addWidget(self.disconnect_btn)
        serial_layout.addLayout(btn_layout)

        time_group = QGroupBox("时间设置")
        time_layout = QHBoxLayout(time_group)
        self.time_input = QLineEdit("60")
        self.time_input.setValidator(QIntValidator(1, 999))
        time_layout.addWidget(QLabel("检测时长(s):"))
        time_layout.addWidget(self.time_input)

        threshold_group = QGroupBox("阈值设置")
        threshold_layout = QHBoxLayout(threshold_group)
        self.threshold_input = QLineEdit("5.0")
        self.threshold_input.setValidator(QDoubleValidator(0.0, 40.0, 2))
        threshold_layout.addWidget(QLabel("检测阈值(MPa):"))
        threshold_layout.addWidget(self.threshold_input)

        btn_group = QGroupBox("控制")
        btn_layout = QHBoxLayout(btn_group)
        self.calibrate_btn = QPushButton("调零", self)
        self.start_btn = QPushButton("启动", self)
        self.stop_btn = QPushButton("停止", self)
        self.calibrate_btn.clicked.connect(self.calibrate_channels)
        self.start_btn.clicked.connect(self.start_detection)
        self.stop_btn.clicked.connect(self.stop_detection)
        self.calibrate_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.calibrate_btn)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        
        self.time_display = QLabel("还剩-秒")

        control_layout.addWidget(serial_group)
        control_layout.addWidget(time_group)
        control_layout.addWidget(self.time_display)
        control_layout.addWidget(threshold_group)
        control_layout.addWidget(btn_group)
        
        main_layout.addWidget(control_container)

    def _init_data_structures(self):
        self.history_data = {i: deque() for i in range(1, self.channel_num + 1)}
        self.timer = None
        self.total_time = 0
        self.remaining_time = 0
        self.dir_name = "000"
        self.file_name = "000"
        self.begin_to_record = False
        self.calibrate_data = [0] * self.channel_num  # 调零数据

    def calibrate_channels(self):
        if self.data_reader:
            # self.data_reader.calibrate()
            results = self.data_reader.process_batch(batch_size=10)
            if results and len(results) == self.channel_num:
                self.calibrate_data = results
                self.calibrate_data = [float(x) for x in self.calibrate_data]
                # self.log(f"调零数据: {self.calibrate_data}")
                # self.log("已完成调零")
                QMessageBox.information(self, "调零完成", "已完成调零\n"+"调零数据: "+str(self.calibrate_data))
            else:
                QMessageBox.warning(self, "调零失败", "调零数据格式错误")
        else:
            QMessageBox.warning(self, "调零失败", "请先连接设备")

    def start_detection(self):
        if self.timer and self.timer.isActive():
            return
        try:
            self.remaining_time = int(self.time_input.text())
            self.total_time = self.remaining_time
        except ValueError:
            self.remaining_time = 0
        # self.dir_name = os.path.join("rec", self.get_time_stamp())
        self.dir_name = self.resource_path(os.path.join('rec', self.get_time_stamp()))
        self.file_name = self.get_time_stamp()
        os.mkdir(self.resource_path(self.dir_name))
        self.log(f"检测启动，持续时间: {self.remaining_time}秒")
        self.log(f"检测阈值: {self.threshold_input.text()} MPa")
        self.log(f"调零数据: {self.calibrate_data}")
        self.button_state("检测中")
        self.time_display.setText(f"剩余时间: {self.remaining_time}s")
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timer)
        self.timer.start(1000)

    def button_state(self, state):
        if state == "检测中":
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.threshold_input.setEnabled(False)
            self.time_input.setEnabled(False)
            self.calibrate_btn.setEnabled(False)
        elif state == "检测完成":
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.threshold_input.setEnabled(True)
            self.time_input.setEnabled(True)
            self.calibrate_btn.setEnabled(True)

    def stop_detection(self):
        if self.timer:
            self.timer.stop()
        self.button_state("检测完成")
        self.time_display.setText("已停止")
        self.log(f"{self.get_time_stamp()} 检测已停止")
        self.clear_data()

    def finish_detection(self):
        # 停止计时器（增加存在性检查）
        if hasattr(self, 'timer') and self.timer and self.timer.isActive():
            self.timer.stop()

        if not self.begin_to_record:
            QMessageBox.warning(self, "未检测到任何数据", "请检查设备")
            self.clear_data()
            self.button_state("检测完成")
            return 
        
        self.save_data()
        # self.save_pic()
        self.log("检测完成")
        self.time_display.setText("检测完成")
        self.button_state("检测完成")

        result_dialog = QDialog(self)
        result_dialog.setWindowTitle("检测结果")
        # result_dialog.resize(800, 600)  # Set a larger window size
        result_dialog.setMinimumSize(600, 400)  # 设置最小尺寸而非固定尺寸

        layout = QVBoxLayout(result_dialog)
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["通道", "初始值", "结束值", "差值", "状态"])
        table.setRowCount(self.channel_num)

        # table.setColumnWidth(result_dialog.width() // 5)  # Set equal width for all columns
        # table.setRowHeight(result_dialog.height() // self.channel_num)  # Set equal height for all rows
        threshold = float(self.threshold_input.text())

        # Set larger font for the table
        font = table.font()
        font.setPointSize(12)  # Increase font size
        table.setFont(font)

        # Set row height and column width to fill the window uniformly
        table.verticalHeader().setDefaultSectionSize(int(result_dialog.height() / self.channel_num))  # Equal height for all rows
        table.horizontalHeader().setDefaultSectionSize(int(result_dialog.width() * 0.2))  # 20% of window width per column

        for channel_index in range(1, self.channel_num+1):
            initial = self.history_data[channel_index][0]
            final = self.history_data[channel_index][-1] if self.history_data[channel_index] else 0
            delta = final - initial
            abs_delta = abs(delta)

            table.setItem(channel_index-1, 0, QTableWidgetItem(f"通道 {channel_index}"))
            table.setItem(channel_index-1, 1, QTableWidgetItem(f"{initial:.2f}"))
            table.setItem(channel_index-1, 2, QTableWidgetItem(f"{final:.2f}"))
            table.setItem(channel_index-1, 3, QTableWidgetItem(f"{delta:+.3f}"))

            status_item = QTableWidgetItem("不合格!" if abs_delta > threshold else "合格")
            status_item.setForeground(QColor(255,0,0) if abs_delta > threshold else QColor(0,128,0))
            status_item.setBackground(QColor(255, 200, 200) if abs_delta > threshold else QColor(255,255,255))  # Set background color to white
            table.setItem(channel_index-1, 4, status_item)
        
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)  # Stretch the last column
        
        # 自适应列宽和行高
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)  # 均匀拉伸列宽
        table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)  # 均匀拉伸行高
        
        btn_ok = QPushButton("确定")
        btn_ok.clicked.connect(result_dialog.accept)
        
        layout.addWidget(table)
        layout.addWidget(btn_ok)
        result_dialog.exec_()
        self.clear_data()

    def update_timer(self):
        self.remaining_time -= 1
        self.time_display.setText(f"剩余时间 {self.remaining_time}s")
        self.process_data()
        if self.remaining_time <= 0:
            self.finish_detection()

    def resource_path(self, relative_path):
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def log(self, message):
        """记录日志"""
        log_file = os.path.join(self.dir_name, f"{self.file_name}.log")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(log_file, 'a') as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            print(f"无法写入日志: {str(e)}")

    def get_time_stamp(self):
        now = datetime.now()
        return now.strftime("%Y%m%d_%H%M%S%f")[:-3]

    def save_data(self):
        if not self.history_data:
            return
        file_path = os.path.join(self.dir_name, f"{self.file_name}.txt")
        try:
            with open(file_path, 'w') as f:
                f.write("Time(s)\t" + "\t".join([f"Channel {i}" for i in range(1, self.channel_num+1)]) + "\n")
                
                max_length = max(len(data) for data in self.history_data.values())
                for i in range(max_length):
                    line = [str(i)]
                    for ch in range(1, self.channel_num+1):
                        value = self.history_data[ch][i] if i < len(self.history_data[ch]) else "NaN"
                        line.append(str(value))
                    f.write("\t".join(line) + "\n")
            self.log(f"数据已保存到 {file_path}")
        except Exception as e:
            QMessageBox.warning(self, "保存错误", f"保存数据时发生错误: {str(e)}")

    def update_data(self, results_per_second):
        for channel_index in range(1, self.channel_num + 1):
            value = results_per_second[channel_index - 1]
            self.history_data[channel_index].append(value)

            self.channels[channel_index].setText(
                f"当前值: {value:.2f}\n"
                f"初始值: {self.history_data[channel_index][0]:.2f}\n"
            )
        self.update_chart()

    def process_data(self):
        if not hasattr(self, 'data_reader') or not self.data_reader:
            return

        try:
            batch_size = 10
            # if self.remaining_time <= 1:
                # batch_size = 10
            results = self.data_reader.process_batch(batch_size=batch_size)
            if results and len(results) == self.channel_num:
                results = [r - c for r, c in zip(results, self.calibrate_data)]
                if not self.begin_to_record:
                    self.begin_to_record = True
                    self.remaining_time = self.total_time
                self.update_data(results)
                formatted_results = [round(float(x), 3) for x in results]
                self.log(f"获取数据: {formatted_results}")
                # self.log(f"获取数据: {formatted_results}")
            else:
                if not self.begin_to_record:
                    # self.remaining_time += 1
                    self.log("尚未收到有效数据")
                    for channel_index in range(1, self.channel_num + 1):
                        self.channels[channel_index].setText(
                            f"当前值: 暂无数据\n"
                            f"初始值: 暂无数据\n"
                        )
                else:
                    self.log(f"数据格式错误: {results}")
        except Exception as e:
            error_msg = f"数据处理时发生错误: {str(e)}"
            self.log(error_msg)

    def update_chart(self):
        if not self.history_data:
            return
            
        x = np.arange(len(next(iter(self.history_data.values()))))
        for i, (ch, data) in enumerate(self.history_data.items(), 1):
            if len(data) > 0:
                self.lines[i-1].set_data(x, data)
        
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()

    def clear_data(self):
        for channel in self.history_data:
            self.history_data[channel].clear()
        self.begin_to_record = False
        self.log("数据已清除，准备下一次检测")

    def connect_serial(self):
        selected_port = self.serial_combo.currentText()
        try:
            self.data_reader = DataReader(selected_port)
            if self.data_reader.test_connection():
                self.serial_combo.setEnabled(False)
                self.connect_btn.setEnabled(False)
                self.disconnect_btn.setEnabled(True)
                # self.start_btn.setEnabled(True)
                self.button_state("检测完成")
                QMessageBox.information(self, "连接成功", f"成功连接到串口 {selected_port}")
            else:
                self.data_reader = None
                QMessageBox.warning(self, "连接失败", "无法连接到设备")
        except Exception as e:
            QMessageBox.critical(self, "连接错误", f"连接时发生错误: {str(e)}")
            self.data_reader = None

    def disconnect_serial(self):
        if self.data_reader:
            self.data_reader.stop()
            self.data_reader = None
        self.button_state("检测中")
        self.serial_combo.setEnabled(True)
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        # self.start_btn.setEnabled(False)
        # self.stop_btn.setEnabled(False)
        QMessageBox.information(self, "断开连接", "已断开串口连接")

    def refresh_serial_ports(self):
        current_selection = self.serial_combo.currentText()
        self.serial_combo.clear()
        self.serial_combo.addItems(self.get_available_ports())
        if current_selection in [self.serial_combo.itemText(i) for i in range(self.serial_combo.count())]:
            self.serial_combo.setCurrentText(current_selection)

    def get_available_ports(self):
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports] or [f"COM{i}" for i in range(1, 9)]

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
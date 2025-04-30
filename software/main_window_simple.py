import sys
# import random
import numpy as np
# import time
from collections import deque
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,QMessageBox,QDialog,QTableWidget,
                             QTableWidgetItem,QGroupBox, QScrollArea, QLabel, QLineEdit, QPushButton)
from PyQt5.QtGui import QIntValidator,QDoubleValidator,QColor
# from PyQt5.QtCore import QObject, pyqtSignal, QThread
from PyQt5.QtCore import QTimer
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from ocr_capture_worker import CurrentMeterReader
from datetime import datetime
import os
import cv2

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("压力检测系统")
        self.setGeometry(100, 100, 800, 600)
        self.channel_num = 4  # 通道数

        try:
            self.ocr_worker = CurrentMeterReader()
        except Exception as e:
            QMessageBox.critical(self, "初始化错误", f"无法初始化OCR工作线程: {str(e)}")
            self.close()

        self._init_ui()
        self._init_data_structures()

    def _init_ui(self):
        """初始化界面组件"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # Create a horizontal layout for the main content
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)

        # 左侧通道面板
        self._init_left_panel(content_layout)
        
        # 右侧控制面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 时间设置组件
        time_group = QGroupBox("时间设置")
        time_layout = QHBoxLayout(time_group)
        self.time_input = QLineEdit("60")
        self.time_input.setValidator(QIntValidator(1, 999))
        time_layout.addWidget(QLabel("检测时长(s):"))
        time_layout.addWidget(self.time_input)
        right_layout.addWidget(time_group)

        # 检查阈值组件
        threshold_group = QGroupBox("阈值设置")
        threshold_layout = QHBoxLayout(threshold_group)
        self.threshold_input = QLineEdit("5.0")
        self.threshold_input.setValidator(QDoubleValidator(0.0, 40.0, 2))
        threshold_layout.addWidget(QLabel("检测阈值(MPa):"))
        threshold_layout.addWidget(self.threshold_input)
        right_layout.addWidget(threshold_group)

        # 按钮组
        btn_group = QGroupBox("控制")
        btn_layout = QHBoxLayout(btn_group)
        self.calibrate_btn = QPushButton("调零", self)
        self.calibrate_btn.clicked.connect(self.calibrate_channels)
        self.check_btn = QPushButton("检查", self)
        self.check_btn.clicked.connect(self.check_camera_alignment)
        self.start_btn = QPushButton("启动", self)
        self.stop_btn = QPushButton("停止", self)
        self.start_btn.clicked.connect(self.start_detection)
        self.stop_btn.clicked.connect(self.stop_detection)
        self.stop_btn.setEnabled(False)  # 初始不可用
        btn_layout.addWidget(self.calibrate_btn)
        btn_layout.addWidget(self.check_btn)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        right_layout.addWidget(btn_group)

        # 倒计时显示
        self.time_display = QLabel("还剩-秒")
        right_layout.addWidget(self.time_display)

        content_layout.addWidget(right_panel)

    def _init_left_panel(self, main_layout):
        """初始化左侧通道面板"""
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

    def check_camera_alignment(self):
        """Capture and display a single frame to check camera alignment"""
        ret, frame = self.ocr_worker.cap.read()
        if ret:
            cv2.imshow("Camera Alignment Check", frame)
        else:
            QMessageBox.warning(self, "Camera Error", "无法读取摄像头画面")

    def _init_data_structures(self):
        """初始化数据结构"""
        # self.channel_num = 4
        self.history_data = {i: deque() for i in range(1, self.channel_num + 1)}
        self.timer = None
        self.remaining_time = 0
        self.total_time = 0
        self.dir_name = "000"
        self.file_name = "000"
        self.begin_to_record = False
        self.calibrate_data = [2] * self.channel_num
        return 
    def start_detection(self):
        """启动检测"""
        if self.timer and self.timer.isActive():
            return
        try:
            self.remaining_time = int(self.time_input.text())
            self.total_time = self.remaining_time
        except ValueError:
            self.remaining_time = 0
        # self.dir_name = self.get_time_stamp()
        self.dir_name = self.resource_path(os.path.join('rec', self.get_time_stamp()))
        os.mkdir(self.dir_name)
        self.ocr_worker.set_dir_name(self.dir_name)
        self.ocr_worker.set_file_name(self.file_name)
        # 记录启动信息
        self.log(f"检测启动，持续时间: {self.remaining_time}秒")
        self.log(f"检测阈值: {self.threshold_input.text()} MPa")

        self.button_state("检测中")
        self.time_display.setText(f"剩余时间: {self.remaining_time}s")
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timer)
        self.timer.start(1000)

    def button_state(self,state):
        """按钮状态"""
        if state == "检测中":
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.threshold_input.setEnabled(False)
            self.time_input.setEnabled(False)
            self.check_btn.setEnabled(False)
            self.calibrate_btn.setEnabled(False)
        elif state == "检测完成":
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.threshold_input.setEnabled(True)
            self.time_input.setEnabled(True)
            self.check_btn.setEnabled(True)
            self.calibrate_btn.setEnabled(True)

    def stop_detection(self):
        """停止检测"""
        if self.timer:
            self.timer.stop()
        self.button_state("检测完成")
        self.time_display.setText("已停止")
        self.log(f"{self.get_time_stamp()} 检测已停止")
        self.clear_data()
    
    def calibrate_channels(self):
        if self.ocr_worker:
            results = self.ocr_worker.process_batch(batch_size=10)
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

    def finish_detection(self):
        """检测完成并展示结果"""
        if self.timer:
            self.timer.stop()
            
        self.start_recording()

        if not self.begin_to_record:
            QMessageBox.warning(self, "未检测到任何数据", "请检查设备")
            self.clear_data()
            self.button_state("检测完成")
            return 
        
        # 保存数据并记录日志
        self.save_data()
        # self.save_pic()
        self.log("检测完成")
        
        self.time_display.setText("检测完成")
        self.button_state("检测完成")

        result_dialog = QDialog(self)
        result_dialog.setWindowTitle("检测结果")
        layout = QVBoxLayout(result_dialog)

        # 创建表格
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["通道", "初始值", "结束值", "差值", "状态"])
    
        # 填充数据
        table.setRowCount(8)
        threshold = float(self.threshold_input.text())

        for channel_index in range(1, self.channel_num+1):
            initial = self.history_data[channel_index][0]
            final = self.history_data[channel_index][-1] if self.history_data[channel_index] else 0
            delta = final - initial
            abs_delta = abs(delta)

            # 设置表格项
            table.setItem(channel_index-1, 0, QTableWidgetItem(f"通道 {channel_index}"))
            table.setItem(channel_index-1, 1, QTableWidgetItem(f"{initial:.2f}"))
            table.setItem(channel_index-1, 2, QTableWidgetItem(f"{final:.2f}"))
            table.setItem(channel_index-1, 3, QTableWidgetItem(f"{delta:+.3f}"))

            # 状态项
            status_item = QTableWidgetItem("不合格!" if abs_delta > threshold else "合格")
            status_item.setForeground(QColor(255,0,0) if abs_delta > threshold else QColor(0,128,0))
            table.setItem(channel_index-1, 4, status_item)
        
        # 调整表格
        table.resizeColumnsToContents()
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # 添加确定按钮
        btn_ok = QPushButton("确定")
        btn_ok.clicked.connect(result_dialog.accept)
        
        layout.addWidget(table)
        layout.addWidget(btn_ok)
        result_dialog.exec_()
        self.clear_data()

    def update_timer(self):
        """更新倒计时和图表"""
        self.remaining_time -= 1
        self.time_display.setText(f"剩余时间 {self.remaining_time}s")
        self.process_data()
        if self.remaining_time <= 0:
            self.finish_detection()

    def resource_path(self,relative_path):
        """ 获取资源的绝对路径，兼容开发模式和 PyInstaller 打包模式 """
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
        """保存历史数据到txt文件"""
        if not self.history_data:
            return
            
        file_path = os.path.join(self.dir_name, f"{self.file_name}.txt")
        try:
            with open(file_path, 'w') as f:
                # 写入表头
                f.write("Time(s)\t" + "\t".join([f"Channel {i}" for i in range(1, self.channel_num+1)]) + "\n")
                
                # 写入数据
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

    def save_pic(self):
        """"保存图片"""
        ret,frame = self.ocr_worker.cap.read()
        time_stamp = self.get_time_stamp()
        if not ret:
            self.log(f"{time_stamp}无法获取图像")
            return 
        file_name = os.path.join(self.dir_name,f"{time_stamp}.jpg")
        cv2.imwrite(file_name,frame)
        self.log(f"保存图像到{file_name}")
        

    def update_data(self, results_per_second):
        """更新数据"""
        # 更新通道信息
        for channel_index in range(1, self.channel_num + 1):
            value = results_per_second[channel_index - 1]
            self.history_data[channel_index].append(value)

            # 显示文字
            self.channels[channel_index].setText(
                # f"当前值: {value:.2f}\n"
                f"初始值: {self.history_data[channel_index][0]:.2f}\n"
            )
        # self.update_chart()
    def process_data(self):
        """处理数据"""
        if not hasattr(self, 'ocr_worker') or not self.ocr_worker:
            return
        
        try:                    
            if not self.begin_to_record:
                results = self.ocr_worker.process_batch(batch_size=3)
                if results and len(results) == self.channel_num:
                    if results and len(results) == self.channel_num:
                        self.begin_to_record = True
                        self.log("首次收到数据，等待2秒稳定时间...")
                        # self.delay_timer = QTimer()
                        # self.delay_timer.setSingleShot(True)
                        # self.delay_timer.timeout.connect(self.start_recording)
                        # self.delay_timer.start(2000)  # 1秒延迟
                        time.sleep(2)  # 2秒延迟
                        self.start_recording()
            else:
                pass

        except Exception as e:
            error_msg = f"数据处理时发生错误: {str(e)}"
            self.log(error_msg)

    # def process_data(self):
    #     """Simplified data processing without threading"""
    #     if not hasattr(self, 'ocr_worker') or not self.ocr_worker:
    #         return

    #     try:
    #         retry_count = 3
    #         for i in range(retry_count):
    #             results = self.ocr_worker.process_batch(batch_size=10)
    #             if results and len(results) == self.channel_num:
    #                 results = [r - c for r, c in zip(results, self.calibrate_data)]
    #                 if not self.begin_to_record:
    #                     self.begin_to_record = True
    #                     self.log("开始记录数据")
    #                     self.log("首次收到数据，等待1秒稳定时间...")
    #                     self.delay_timer = QTimer()
    #                     self.delay_timer.setSingleShot(True)
    #                     self.delay_timer.timeout.connect(self.start_recording)
    #                     self.delay_timer.start(1000)  # 1秒延迟
    #                 else:
    #                     self.update_data(results)
    #                     self.log(f"获取数据: {results}")
    #                 break

    #     except Exception as e:
    #         error_msg = f"数据处理时发生错误: {str(e)}"
    #         self.log(error_msg)

    def start_recording(self):
        """开始记录数据和计时"""
        self.log("1秒稳定时间结束，开始记录数据")
        # self.timer.start(1000)
        results = self.ocr_worker.process_batch(batch_size=10)
        if results and len(results) == self.channel_num:
            results = [r - c for r, c in zip(results, self.calibrate_data)]
            self.remaining_time = self.total_time
            self.save_pic()
            self.update_data(results)
            self.log(f"获取数据: {results}")
        else:
            # self.remaining_time += 1
            self.log("数据格式错误或通道数不匹配")
            self.begin_to_record = False

    def clear_data(self):
        """清除历史数据"""
        for channel in self.history_data:
            self.history_data[channel].clear()
        self.begin_to_record = False
        self.log("数据已清除，准备下一次检测")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
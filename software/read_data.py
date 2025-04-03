import sys
import random
import numpy as np
import time
from collections import deque
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,QMessageBox,QDialog,QTableWidget,
                             QTableWidgetItem,QGroupBox, QScrollArea, QLabel, QLineEdit, QPushButton)
from PyQt5.QtGui import QIntValidator,QDoubleValidator,QColor
from PyQt5.QtCore import QObject, pyqtSignal, QThread
from PyQt5.QtCore import QTimer
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class DataSimulator(QObject):
    data_ready = pyqtSignal(dict)  # 定义数据就绪信号

    def __init__(self, num_channels=8):
        super().__init__()
        self.num_channels = num_channels
        self._is_running = False
        self.base_pressures = {i: random.uniform(0,40) for i in range(1, num_channels+1)}

    def start_simulation(self):
        """启动数据模拟"""
        self._is_running = True
        self.thread = QThread()
        self.moveToThread(self.thread)
        self.thread.started.connect(self._generate_data)
        self.thread.start()

    def stop_simulation(self):
        """停止数据模拟"""
        self._is_running = False
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()

    def _generate_data(self):
        """生成模拟数据"""
        while self._is_running:
            # 生成各通道数据
            raw_data = {}
            for ch in range(1, self.num_channels+1):
                # 生成10-15个数据点
                # num_samples = random.randint(10, 15)
                # 均值使用基准压力，方差=通道号
                data = np.random.normal(
                    loc=self.base_pressures[ch],
                    scale=np.sqrt(ch),  # 标准差=sqrt(方差)
                    size=1
                )
                raw_data[ch] = data.tolist()
            
            # 发送数据
            self.data_ready.emit(raw_data)
            
            # 模拟采样间隔（100ms）
            time.sleep(0.1)

class DataProcessor:
    def __init__(self, num_channels=8):
        self.num_channels = num_channels
        self.data_buffer = {i: [] for i in range(1, num_channels+1)}
        self.frame_counter = 0

    def ingest_data(self, raw_data):
        """接收原始数据（非线程安全，需在主线程调用）"""
        for ch, values in raw_data.items():
            if 1 <= ch <= self.num_channels:
                self.data_buffer[ch].extend(values)
        self.frame_counter += 1
        
    def process(self):
        """处理当前秒数据（需每秒调用一次）"""
        result_data = {}
        for channel_index in range(1, self.num_channels+1):
            data_per_channel = self.data_buffer[channel_index]
            if data_per_channel:
                result_data[channel_index] = {
                    'median':np.median(data_per_channel),
                    # 'max':max(data_per_channel)
                }
            else:
                result_data[channel_index] = {
                    'median':0.0,
                    # 'max':0.0
                }

        # 清空当前秒数据
        for ch in self.data_buffer:
            self.data_buffer[ch].clear()
        current_frame_counter = self.frame_counter
        self.frame_counter = 0
            
        return result_data,current_frame_counter

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("压力检测系统")
        self.setGeometry(100, 100, 1200, 800)

        # 添加数据模拟器
        self.simulator = DataSimulator()
        self.simulator.data_ready.connect(self.update_data)
        self.simulator.start_simulation()

        # 初始化组件
        self._init_ui()
        self._init_data_structures()

    def closeEvent(self, event):
        """窗口关闭时停止模拟"""
        self.simulator.stop_simulation()
        super().closeEvent(event)

    def _init_ui(self):
        """初始化界面组件"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        main_layout.addWidget(top_widget)

        # 左侧通道面板
        self._init_left_panel(top_layout)
        # 右侧图表面板
        self._init_right_panel(top_layout)
        # 底部控制面板
        self._init_control_panel(main_layout)
        
        # self.setCentralWidget(main_layout)

    def _init_left_panel(self, main_layout):
        """初始化左侧通道面板"""
        left_panel = QScrollArea()
        left_content = QWidget()
        self.channel_layout = QVBoxLayout(left_content)
        
        self.channels = {}
        for i in range(1, 9):
            channel_box = QGroupBox(f"通道 {i}")
            layout = QVBoxLayout()
            self.channels[i] = QLabel("当前值: --\n初始值: --\n状态:--")
            layout.addWidget(self.channels[i])
            channel_box.setLayout(layout)
            self.channel_layout.addWidget(channel_box)
        
        left_panel.setWidget(left_content)
        main_layout.addWidget(left_panel, stretch=2)

    def _init_right_panel(self, main_layout):
        """初始化右侧图表面板"""
        # 设置全局字体
        matplotlib.rcParams['font.sans-serif'] = ['SimHei']  # 黑体
        matplotlib.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        self.figure = Figure(figsize=(8, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("实时压力曲线")
        self.ax.set_xlabel("时间 (秒)")
        self.ax.set_ylabel("压力值")
        self.lines = [self.ax.plot([], [], label=f'通道 {i}')[0] for i in range(1, 9)]
        self.ax.legend()
        
        right_layout.addWidget(self.canvas)
        main_layout.addWidget(right_panel, stretch=5)

    def _init_control_panel(self, main_layout):
        """初始化控制面板"""
        # 主控制容器
        control_container = QWidget()
        # 主水平布局
        control_layout = QHBoxLayout(control_container)

        # 时间设置组件
        time_group = QGroupBox("时间设置")
        time_layout = QHBoxLayout(time_group)
        self.time_input = QLineEdit("60")
        self.time_input.setValidator(QIntValidator(1, 999))
        time_layout.addWidget(QLabel("检测时长(s):"))
        time_layout.addWidget(self.time_input)

        # 检查阈值组件
        threshold_group = QGroupBox("阈值设置")
        threshold_layout = QHBoxLayout(threshold_group)
        self.threshold_input = QLineEdit("5.0")
        self.threshold_input.setValidator(QDoubleValidator(0.0, 40.0, 2))
        threshold_layout.addWidget(QLabel("检测阈值(MPa):"))
        threshold_layout.addWidget(self.threshold_input)

        # 按钮组
        btn_group = QGroupBox("控制")
        btn_layout = QHBoxLayout(btn_group)
        self.start_btn = QPushButton("启动", self)
        self.stop_btn = QPushButton("停止", self)
        self.start_btn.clicked.connect(self.start_detection)
        self.stop_btn.clicked.connect(self.stop_detection)
        self.stop_btn.setEnabled(False)  # 初始不可用
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        
        # 倒计时显示
        self.time_display = QLabel("还剩-秒")

        # 帧率显示
        self.fps_label = QLabel("帧率: 0 fps")

        # 整合布局
        control_layout.addWidget(time_group)
        control_layout.addWidget(self.time_display)
        control_layout.addWidget(threshold_group)
        control_layout.addWidget(btn_group)
        control_layout.addWidget(self.fps_label)
        
        # 添加到主布局
        main_layout.addWidget(control_container)
         
    def _init_data_structures(self):
        """初始化数据结构"""
        self.processor = DataProcessor()
        self.history_data = {i: deque() for i in range(1, 9)}
        self.timer = None
        self.time_count = 0
        self.remaining_time = 0

    def start_detection(self):
        """启动检测"""
        if self.timer and self.timer.isActive():
            return
        try:
            self.remaining_time = int(self.time_input.text())
            self.time_count = self.remaining_time
        except ValueError:
            self.remaining_time = 0

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.time_display.setText(f"剩余时间: {self.remaining_time}s")
        # self.start_btn.setText(f"剩余时间 {self.remaining_time}s")
        # 初始化定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timer)
        self.timer.start(1000)  # 精确1秒间隔
        # 重置历史数据
        for ch in self.history_data:
            self.history_data[ch].clear()

    def stop_detection(self):
        """停止检测"""
        if self.timer:
            self.timer.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.time_display.setText("已停止")

    def finish_detection(self):
        """检测完成并展示结果"""
        # 停止检测
        if self.timer:
            self.timer.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

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

        for channel_index in range(1, 9):
            initial = self.history_data[channel_index][0]
            final = self.history_data[channel_index][-1] if self.history_data[channel_index] else 0
            delta = final - initial
            abs_delta = abs(delta)

            # 设置表格项
            table.setItem(channel_index-1, 0, QTableWidgetItem(f"通道 {channel_index}"))
            table.setItem(channel_index-1, 1, QTableWidgetItem(f"{initial:.2f}"))
            table.setItem(channel_index-1, 2, QTableWidgetItem(f"{final:.2f}"))
            table.setItem(channel_index-1, 3, QTableWidgetItem(f"{delta:+.2f}"))

            # 状态项
            status_item = QTableWidgetItem("超限!" if abs_delta > threshold else "正常")
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
    

    def update_timer(self):
        """更新倒计时和图表"""
        self.remaining_time -= 1
        self.time_display.setText(f"剩余时间 {self.remaining_time}s")
        self.process_data()
        if self.remaining_time <= 0:
            self.finish_detection()
    
    def process_data(self):
        """创建新的秒处理器并处理上一秒数据"""
        if self.processor:
            # 处理上一秒数据
            processed, fps = self.processor.process()
            self.fps_label.setText(f"帧率: {fps} fps")

            # 更新通道信息
            for channel_index in range(1, 9):
                data = processed[channel_index]
                self.history_data[channel_index].append(processed[channel_index]['median'])
                pressure_delta = abs(data['median'] - self.history_data[channel_index][0])
                context = "正常" if pressure_delta < float(self.threshold_input.text()) else "超限！"
                self.channels[channel_index].setText(
                    f"当前值: {data['median']:.2f}\n"
                    f"初始值: {self.history_data[channel_index][0]:.2f}\n"
                    f"状态: {context}"
                )

            self.update_chart()
            
    def update_chart(self):
        """优化图表更新"""
        x = np.arange(len(next(iter(self.history_data.values()))))
        for i, (ch, data) in enumerate(self.history_data.items(), 1):
            self.lines[i-1].set_data(x, data)
        
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()

    def update_data(self, raw_data):
        """对外数据接口"""
        # 打印调试信息（正式使用时可以移除）
        print(f"收到数据: { {k: v for k, v in raw_data.items()} }")
        
        # 传递数据给处理器
        self.processor.ingest_data(raw_data)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
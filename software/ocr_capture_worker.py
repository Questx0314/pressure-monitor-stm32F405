import cv2
import numpy as np
from paddleocr import PaddleOCR
import re
import sys
from threading import Lock
from collections import Counter
from datetime import datetime
import os


class CurrentMeterReader():
    def __init__(self):
        try:
            self.ocr = PaddleOCR(
                use_angle_cls=False, 
                lang='en', 
                det_model_dir=self.resource_path('model/det/en_PP-OCRv3_det_infer'),
                rec_algorithm='SVTR_LCNet', 
                rec_model_dir=self.resource_path('model/rec/en_PP-OCRv4_rec_infer'),
                rec_char_dict_path=self.resource_path('model/dict/en_dict.txt'),
                use_gpu=False
                )
            self.cap = self._open_camera()
            self.frame_count = 5
            self.float_pattern = re.compile(r'^-?\d+\.?\d*$')
            self.dir_name = "000"  # Add this line to store the directory name for logging
            self.file_name = "000"  # Add this line to store the file name for logging
        except Exception as e:
            print(f"[ERROR] 初始化失败: {e}")
            raise
    def resource_path(self,relative_path):
        """ 获取资源的绝对路径，兼容开发模式和 PyInstaller 打包模式 """
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)
    def __del__(self):
        """资源清理"""
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()

    def set_file_name(self, file_name):
        """设置文件名称"""
        self.file_name = file_name
    def set_dir_name(self, dir_name):
        """设置目录名称"""
        self.dir_name = dir_name
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
    def process_frame(self, frame):
        """优化单帧处理"""
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            filtered_frame = self.filter_red_channel(rgb_frame)
            gray = cv2.cvtColor(filtered_frame, cv2.COLOR_RGB2GRAY)
            _, binary = cv2.threshold(gray, 40, 255, cv2.THRESH_BINARY)

            result = self.ocr.ocr(binary, cls=False)
            if not result or not result[0]:
                return []

            boxes = [line[0] for line in result[0]]
            texts = [line[1][0] for line in result[0]]
            self.log(f"[DEBUG] 处理前识别结果: {texts}")
            valid_boxes = []
            for box, text in zip(boxes, texts):
                parsed = self.parse_reading(text)
                # self.float_pattern
                self.log(f"[DEBUG] 处理后识别结果: {parsed}")
                if parsed is not None:
                    valid_boxes.append((box, parsed))
            
            sorted_boxes = self.sort_boxes([b[0] for b in valid_boxes])
            current_readings = [vb[1] for sb in sorted_boxes 
                              for vb in valid_boxes if np.array_equal(sb, vb[0])]
                
            return current_readings
        except Exception as e:
            self.log(f"[ERROR] 帧处理失败: {e}")
            return []

    def log(self, text):
        """记录日志"""
        if not hasattr(self, 'dir_name'):
            return
        log_file = os.path.join(self.dir_name, f"{self.file_name}.log")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(log_file, 'a') as f:
                f.write(f"[{timestamp}] {text}\n")
        except Exception as e:
            print(f"无法写入日志: {str(e)}")

    def _open_camera(self):
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                return cap
        raise RuntimeError("No available camera.")

    def sharpen_image(self, image):
        """对图像进行锐化处理"""
        kernel = np.array([[0, -1, 0],
                        [-1, 5,-1],
                        [0, -1, 0]])
        sharpened = cv2.filter2D(image, -1, kernel)
        return sharpened

    def filter_red_channel(self,rgb_frame):
        """保留红色区域并滤除白色噪声"""
        hsv = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2HSV)
        # 红色 HSV 区间
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 100, 100])
        upper_red2 = np.array([180, 255, 255])
        red_mask = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2)

        # 去除白色区域：R、G、B都大且差值小
        rgb_array = rgb_frame.astype(np.int16)
        r, g, b = rgb_array[..., 0], rgb_array[..., 1], rgb_array[..., 2]
        white_mask = ((np.abs(r - g) < 20) & (np.abs(r - b) < 20) & (r > 200)).astype(np.uint8) * 255

        # 从红色掩码中去除白色部分
        red_mask_no_white = cv2.bitwise_and(red_mask, cv2.bitwise_not(white_mask))

        # 应用掩码获取最终图像
        red_filtered = cv2.bitwise_and(rgb_frame, rgb_frame, mask=red_mask_no_white)

        return red_filtered

    def sort_boxes(self, boxes):
        """按从上到下、从左到右排序，带动态行列判断"""
        if not boxes:
            return []
        
        # 计算所有框的统计特征
        heights = [abs(box[2][1] - box[0][1]) for box in boxes]
        widths = [abs(box[2][0] - box[0][0]) for box in boxes]
        median_height = sorted(heights)[len(heights)//2]
        median_width = sorted(widths)[len(widths)//2]
        
        # 动态阈值（基于中位数）
        row_thresh = median_height * 0.6  # 经验值
        col_thresh = median_width * 0.8
        
        # 获取中心坐标并带原始索引
        centers = [(
            (box[0][0]+box[2][0])/2, 
            (box[0][1]+box[2][1])/2,
            i
        ) for i, box in enumerate(boxes)]
        
        # 先按Y轴粗排序
        centers_sorted = sorted(centers, key=lambda x: x[1])
        
        # 动态行分组（改进算法）
        rows = []
        current_row = [centers_sorted[0]]
        for point in centers_sorted[1:]:
            # 动态计算当前行基准Y（取当前行中点）
            base_y = np.mean([p[1] for p in current_row])
            if abs(point[1] - base_y) > row_thresh:
                rows.append(current_row)
                current_row = [point]
            else:
                current_row.append(point)
        rows.append(current_row)
        
        # 行内处理：先分列再排序
        sorted_boxes = []
        for row in rows:
            # 按X坐标排序
            row_sorted = sorted(row, key=lambda x: x[0])
            
            # 列分组
            columns = []
            current_col = [row_sorted[0]]
            for point in row_sorted[1:]:
                base_x = np.mean([p[0] for p in current_col])
                if abs(point[0] - base_x) > col_thresh:
                    columns.append(current_col)
                    current_col = [point]
                else:
                    current_col.append(point)
            columns.append(current_col)
            
            # 列内按Y微调（处理垂直排列）
            for col in columns:
                col_sorted = sorted(col, key=lambda x: x[1])
                sorted_boxes.extend([boxes[p[2]] for p in col_sorted])
        
        return sorted_boxes
    def parse_reading(self, text):
        text = text.replace(',', '').replace('.', '').replace(" ","")
        text = text.replace('o', '0').replace('O', '0').replace('Q', '0').replace('D', '0') 
        text = text.replace('l', '1').replace('I', '1').replace('i', '1').replace('L', '1').replace('J', '1')
        text = text.replace('z', '2').replace('Z', '2')
        text = text.replace('s', '5').replace('S', '5')
        text = text.replace('G', '6')
        text = text.replace('t', '7').replace('T', '7')
        text = text.replace('B', '8')
        text = text.replace('q', '9')
        if len(text) == 3:
            text = text[0] + '.' + text[1:]
        elif len(text) == 4:
            text = text[:2] + '.' + text[2:]
        # self.log(f"[DEBUG] 解析结果: {text}")
        if self.float_pattern.match(text):
            return float(text)
        return None

    def filter_frame_by_channel(self, current_readings):
        """按众数滤波"""
        lengths = [len(frame) for frame in current_readings]
        if not lengths:
            return []
        most_common_length = Counter(lengths).most_common(1)[0][0]
        return [frame for frame in current_readings if len(frame) == most_common_length]

    def median_filter(self, current_readings):
        """中值滤波处理"""
        if not current_readings:
            return []
        data_by_channel = np.array(current_readings, dtype=np.float32).T
        medians = [float(np.median(channel)) for channel in data_by_channel]
        return medians
    def process_data(self,results):
        """处理数据"""
        if not results:
            return []
        try:
            return results
        except Exception as e:
            self.log(f"[EXCEPTION] 后处理时出错: {e}")
            return []
    def process_batch(self, batch_size=5):
        """处理一秒内的图像"""
        frames_data_reading = []
        for index in range(batch_size):
            ret, frame = self.cap.read()
            if not ret:
                self.log(f"[ERROR] 第{index+1}帧无法读取摄像头画面")
                break

            readings = self.process_frame(frame)
            self.log(f"[DEBUG] 第{index+1}帧识别结果：{readings}")
            if readings:
                frames_data_reading.append(readings)

        if not frames_data_reading:
            print("暂无数据")
            return []

        try:
            filtered = self.filter_frame_by_channel(frames_data_reading)
            results = self.median_filter(filtered)
            return results
        except Exception as e:
            self.log(f"[EXCEPTION] 后处理时出错: {e}")
            return []

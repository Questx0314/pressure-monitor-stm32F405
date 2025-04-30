import cv2
import os
import time
from datetime import datetime

def get_first_available_camera():
    for i in range(5):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            print(f"[INFO] 使用摄像头：{i}")
            return cap
        cap.release()
    raise RuntimeError("未找到可用的摄像头")

def get_timestamp():
    now = datetime.now()
    return now.strftime("%Y%m%d_%H%M%S")

def create_output_folder(base_path="captures"):
    timestamp = get_timestamp()
    folder_path = os.path.join(base_path, timestamp)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path

def main():
    cap = get_first_available_camera()
    base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")
    os.makedirs(base_path, exist_ok=True)

    is_capturing = False
    save_folder = None
    last_capture_time = 0
    capture_interval = 0.1  # 秒

    print("按 's' 开始拍照，'e' 停止拍照，'q' 退出程序。")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] 无法读取摄像头画面")
            break

        # 显示提示
        status_text = "拍照中..." if is_capturing else "等待开始 (按s开始)"
        cv2.putText(frame, status_text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255) if is_capturing else (0, 255, 0), 2)

        cv2.imshow("Camera", frame)

        key = cv2.waitKey(1) & 0xFF

        # 开始拍照
        if key == ord('s') and not is_capturing:
            save_folder = create_output_folder(base_path)
            print(f"[START] 开始拍照，保存路径：{save_folder}")
            is_capturing = True
            last_capture_time = time.time()

        # 停止拍照
        elif key == ord('e') and is_capturing:
            print("[END] 停止拍照")
            is_capturing = False

        # 退出程序
        elif key == ord('q'):
            print("[QUIT] 退出程序")
            break

        # 如果正在拍照，定时保存图像
        if is_capturing:
            now = time.time()
            if now - last_capture_time >= capture_interval:
                timestamp = get_timestamp()
                filename = os.path.join(save_folder, f"{timestamp}.jpg")
                cv2.imwrite(filename, frame)
                print(f"保存：{filename}")
                last_capture_time = now

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

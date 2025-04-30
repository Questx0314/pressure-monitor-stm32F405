import os
import time
from paddleocr import PaddleOCR, draw_ocr
from PIL import Image, ImageDraw, ImageFont


# 初始化OCR
ocr = PaddleOCR(use_angle_cls=True, lang='en')

# 路径配置
input_root = 'captures'
output_root = 'result'
font_path = 'simfang.ttf'  # 确保字体文件存在

def get_text_size(draw, text, font):
    """兼容不同Pillow版本的文本尺寸获取"""
    try:
        # 新版本使用textbbox
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        # 旧版本回退到textsize
        return draw.textsize(text, font=font)

def process_images_recursive():
    for root, dirs, files in os.walk(input_root):
        for file in files:
            if not file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                continue

            input_path = os.path.join(root, file)
            relative_path = os.path.relpath(root, input_root)
            output_dir = os.path.join(output_root, relative_path)
            output_path = os.path.join(output_dir, f"result_{file}")

            os.makedirs(output_dir, exist_ok=True)
            start_time = time.time()

            try:
                # OCR处理
                result = ocr.ocr(input_path, cls=False)
                image = Image.open(input_path).convert('RGB')
                
                # 绘制OCR结果
                if result and result[0]:
                    image = draw_ocr(
                        image,
                        [line[0] for line in result[0]],
                        [line[1][0] for line in result[0]],
                        [line[1][1] for line in result[0]],
                        font_path=font_path
                    )
                    image = Image.fromarray(image)
                
                draw = ImageDraw.Draw(image)
                processing_time = (time.time() - start_time) * 1000

                # 添加时间戳
                font = ImageFont.truetype(font_path, 30)
                time_text = f"{processing_time:.1f}ms"
                
                # 使用兼容方法获取文本尺寸
                text_width, text_height = get_text_size(draw, time_text, font)
                
                margin = 10
                position = (margin, image.height - text_height - margin)

                # 绘制背景框
                draw.rectangle(
                    [position[0]-5, position[1]-5,
                     position[0]+text_width+5, position[1]+text_height+5],
                    fill=(0,0,0)
                )
                draw.text(position, time_text, font=font, fill=(255,255,255))

                # 保存结果
                image.save(output_path)
                print(f"Success: {input_path} -> {output_path}")

            except Exception as e:
                print(f"Error processing {input_path}: {str(e)}")
                # 保存原始图片用于调试
                image.save(os.path.join(output_dir, f"error_{file}"))

if __name__ == "__main__":
    os.makedirs(output_root, exist_ok=True)
    print("Starting processing...")
    process_images_recursive()
    print("Processing completed. Check results in", output_root)
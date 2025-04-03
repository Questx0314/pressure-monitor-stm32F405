import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import r2_score

# 定义数据
# 横坐标：电流值，单位 mA，假设均匀分布从 0 到 20 mA，共 21 个点
x = np.arange(0, 21, 1)  # 0, 1, 2, ... , 20
# 纵坐标：给定的电压值
y = np.array([0.006, 0.107, 0.301, 0.433, 0.632, 0.758, 0.948, 1.08, 1.277, 1.470, 
              1.585, 1.777, 1.909, 2.097, 2.220, 2.418, 2.54, 2.733, 2.926, 3.056, 3.250])

# 进行线性拟合，使用 np.polyfit 返回一次多项式的系数（斜率 a 和截距 b）
coeffs = np.polyfit(x, y, 1)
a, b = coeffs
print(f"拟合直线公式: y = {a:.4f} * x + {b:.4f}")

# 使用拟合参数计算预测值
y_fit = a * x + b

# 计算决定系数 R^2
R2 = r2_score(y, y_fit)
print(f"决定系数 R^2 = {R2:.4f}")

# 绘制图像
plt.figure(figsize=(8, 5))
plt.scatter(x, y, color='blue', label='原始数据')
plt.plot(x, y_fit, color='red', label=f'拟合直线: y={a:.4f}x+{b:.4f}\n$R^2$={R2:.4f}')
plt.xlabel('电流 (mA)')
plt.ylabel('电压 (V)')
plt.title('电流-电压数据的线性拟合')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

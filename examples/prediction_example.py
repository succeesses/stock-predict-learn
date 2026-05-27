"""
Kronos 预测示例
展示如何使用预训练的 Kronos 模型对金融 K 线数据进行预测，并可视化结果
"""

import pandas as pd
import matplotlib.pyplot as plt
import sys

# 解决 matplotlib 中文显示问题 - 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# 添加上级目录到路径，以便导入 model 模块
sys.path.append("../")

# 从 model 模块导入 Kronos 的三个核心组件：
# - KronosTokenizer: 将连续的 K 线数据量化为离散 tokens
# - Kronos: 主模型，自回归 Transformer
# - KronosPredictor: 高层预测 API，处理数据预处理、归一化、预测和反归一化
from model import Kronos, KronosTokenizer, KronosPredictor


def plot_prediction(kline_df, pred_df):
    """
    绘制预测结果对比图，包含收盘价和成交量两个子图

    参数:
        kline_df: 包含真实 K 线数据的 DataFrame
        pred_df: 模型预测的 K 线数据 DataFrame
    """
    # 将预测结果的索引设置为对应时间戳，与真实数据对齐
    pred_df.index = kline_df.index[-pred_df.shape[0]:]

    # 提取收盘价数据，分别是真实值和预测值
    sr_close = kline_df['close']
    sr_pred_close = pred_df['close']
    sr_close.name = 'Ground Truth'       # 真实值
    sr_pred_close.name = "Prediction"    # 预测值

    # 提取成交量数据，分别是真实值和预测值
    sr_volume = kline_df['volume']
    sr_pred_volume = pred_df['volume']
    sr_volume.name = 'Ground Truth'
    sr_pred_volume.name = "Prediction"

    # 将真实值和预测值合并到同一个 DataFrame 方便绘图
    close_df = pd.concat([sr_close, sr_pred_close], axis=1)
    volume_df = pd.concat([sr_volume, sr_pred_volume], axis=1)

    # 创建 2 行 1 列的子图，共享 x 轴，设置画布大小
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)

    # 绘制收盘价对比图
    ax1.plot(close_df['Ground Truth'], label='Ground Truth', color='blue', linewidth=1.5)
    ax1.plot(close_df['Prediction'], label='Prediction', color='red', linewidth=1.5)
    ax1.set_ylabel('Close Price', fontsize=14)
    ax1.legend(loc='lower left', fontsize=12)
    ax1.grid(True)

    # 绘制成交量对比图
    ax2.plot(volume_df['Ground Truth'], label='Ground Truth', color='blue', linewidth=1.5)
    ax2.plot(volume_df['Prediction'], label='Prediction', color='red', linewidth=1.5)
    ax2.set_ylabel('Volume', fontsize=14)
    ax2.legend(loc='upper left', fontsize=12)
    ax2.grid(True)

    # 自动调整布局，避免标签重叠
    plt.tight_layout()
    # 显示图形
    plt.show()


# =============================================================================
# 步骤 1: 从 Hugging Face Hub 加载预训练的分词器和模型
# =============================================================================
# 加载分词器 - base 版本词汇表大小约 2k
tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
# 加载 Kronos 模型 - base 版本 102.3M 参数，上下文窗口 512，更高预测精度
model = Kronos.from_pretrained("NeoQuasar/Kronos-base")

# =============================================================================
# 步骤 2: 创建预测器实例
# =============================================================================
# max_context: 模型支持的最大上下文长度，Kronos-small/base 是 512
# 预测器会自动处理超长上下文的截断，以及数据归一化/反归一化
predictor = KronosPredictor(model, tokenizer, max_context=512)

# =============================================================================
# 步骤 3: 准备输入数据
# =============================================================================
# 读取示例数据文件 - 这是上证 600977 的 5 分钟 K 线数据
df = pd.read_csv("./data/XSHG_5min_600977.csv")
# 将时间戳列转换为 datetime 格式
df['timestamps'] = pd.to_datetime(df['timestamps'])

# 超参数设置:
# lookback: 使用多少历史 K 线作为上下文（回看窗口）
# 注意: 不超过 max_context (对于 small/base 是 512)
lookback = 400
# pred_len: 预测未来多少个时间步
pred_len = 120

# 分割数据:
# x_df: 历史 K 线数据，必须包含 ['open', 'high', 'low', 'close']，volume 和 amount 是可选
# 这里数据包含所有 6 个维度: open, high, low, close, volume, amount
x_df = df.loc[:lookback-1, ['open', 'high', 'low', 'close', 'volume', 'amount']]
# x_timestamp: 历史数据对应的时间戳
x_timestamp = df.loc[:lookback-1, 'timestamps']
# y_timestamp: 要预测的未来时间段的时间戳
y_timestamp = df.loc[lookback:lookback+pred_len-1, 'timestamps']

# =============================================================================
# 步骤 4: 执行预测
# =============================================================================
# 调用 predict 方法生成预测
pred_df = predictor.predict(
    df=x_df,                # 历史 K 线数据
    x_timestamp=x_timestamp, # 历史时间戳
    y_timestamp=y_timestamp, # 预测目标时间戳
    pred_len=pred_len,       # 预测长度
    T=1.0,                   # 采样温度，1.0 表示不调整，值越小越确定，值越大越多样
    top_p=0.9,               # nucleus 采样参数，保留累积概率达到 top_p 的 tokens
    sample_count=1,          # 生成多少条预测路径，多条路径会被平均得到最终预测
                             # sample_count > 1 可以得到概率预测，提供不确定性估计
    verbose=True             # 是否打印进度信息
)

# =============================================================================
# 步骤 5: 可视化预测结果
# =============================================================================
# 打印预测结果的前几行
print("Forecasted Data Head:")
print(pred_df.head())

# 提取历史 + 预测区间的真实数据，用于绘图对比
kline_df = df.loc[:lookback+pred_len-1]

# 调用绘图函数展示预测结果
plot_prediction(kline_df, pred_df)


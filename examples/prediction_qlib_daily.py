"""
Kronos 预测示例 - 使用 Qlib 获取 A 股日线数据
展示如何从 Qlib 获取数据，然后使用预训练的 Kronos 模型进行预测，并可视化结果

替换 AKShare：当 AKShare 无法连接东方财富时，可以使用这个脚本从 Qlib 获取数据
"""

import qlib
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import sys
import os

# ========== Hugging Face SSL 证书修复 ==========
# 解决 "unable to get local issuer certificate" 错误
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'  # 使用国内镜像
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
# =================================================

# 解决 matplotlib 中文显示问题 - 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

from qlib.data import D
from qlib.constant import REG_CN

# 添加上级目录到路径，以便导入 model 模块
sys.path.append("../")

# 从 model 模块导入 Kronos 的三个核心组件：
# - KronosTokenizer: 将连续的 K 线数据量化为离散 tokens
# - Kronos: 主模型，自回归 Transformer
# - KronosPredictor: 高层预测 API，处理数据预处理、归一化、预测和反归一化
from model import Kronos, KronosTokenizer, KronosPredictor


def plot_prediction(kline_df, pred_df, stock_code, df_original=None):
    """
    绘制预测结果对比图，包含收盘价和成交量两个子图

    参数:
        kline_df: 包含真实 K 线数据的 DataFrame（前复权）
        pred_df: 模型预测的 K 线数据 DataFrame
        stock_code: 股票代码
        df_original: 原始不复权数据，用于第二张子图
    """
    # 将 timestamps 转换为 datetime 类型并设置为索引
    # 这解决了 matplotlib 错误将整数索引解释为 1970 年时间戳的问题
    kline_df = kline_df.copy()
    kline_df['timestamps'] = pd.to_datetime(kline_df['timestamps'])
    kline_df = kline_df.set_index('timestamps')

    # pred_df 已经带有 y_timestamp 索引（来自 KronosPredictor.predict）
    # 不需要重新设置索引，避免可能的对齐错误

    # 提取收盘价数据，分别是真实值和预测值
    sr_close = kline_df['close']
    sr_pred_close = pred_df['close']
    sr_close.name = 'Ground Truth 真实值'       # 真实值
    sr_pred_close.name = "Prediction 预测"    # 预测值

    # 提取成交量数据，分别是真实值和预测值
    sr_volume = kline_df['volume']
    sr_pred_volume = pred_df['volume']
    sr_volume.name = 'Ground Truth 真实值'
    sr_pred_volume.name = "Prediction 预测"

    # 将真实值和预测值合并到同一个 DataFrame 方便绘图
    close_df = pd.concat([sr_close, sr_pred_close], axis=1)

    # 创建图表 - 如果有原始数据增加一个不复权对子图，变成 3 行
    nrows = 3 if df_original is not None else 2
    fig, axes = plt.subplots(nrows, 1, figsize=(12, 10 if nrows == 3 else 8), sharex=True)

    # ========== 第一个子图: 前复权收盘价对比 ==========
    ax1 = axes[0] if nrows == 3 else axes[0]
    ax1.plot(close_df['Ground Truth 真实值'], label='Ground Truth 真实值', color='blue', linewidth=1.5)
    ax1.plot(close_df['Prediction 预测'], label='Prediction 预测', color='red', linewidth=1.5)
    ax1.set_ylabel('Close Price (前复权) 收盘价', fontsize=14)
    ax1.legend(loc='lower left', fontsize=12)
    ax1.grid(True, alpha=0.3)

    # ========== 第二个子图: 成交量对比 ==========
    ax2 = axes[1] if nrows == 3 else axes[1]
    volume_df = pd.concat([sr_volume, sr_pred_volume], axis=1)
    ax2.plot(volume_df['Ground Truth 真实值'], label='Ground Truth 真实值', color='blue', linewidth=1.5)
    ax2.plot(volume_df['Prediction 预测'], label='Prediction 预测', color='red', linewidth=1.5)
    ax2.set_ylabel('Volume 成交量', fontsize=14)
    ax2.legend(loc='upper left', fontsize=12)
    ax2.grid(True, alpha=0)

    # ========== 第三个子图: 不复权收盘价对比 ==========
    if df_original is not None and len(pred_df) > 0:
        df_original = df_original.copy()
        df_original['timestamps'] = pd.to_datetime(df_original['timestamps'])
        df_original = df_original.set_index('timestamps')
        # 只包含对应时间范围
        df_original = df_original.loc[kline_df.index]
        sr_close_original = df_original.loc[:kline_df.index[-len(pred_df)], 'close']
        sr_close_original.name = 'Ground Truth 真实值'
        # 预测价格转换为不复权: 使用最后一个价格比例
        last_adj = kline_df['close'].iloc[-len(pred_df)]
        last_original = df_original['close'].iloc[-len(pred_df)]
        scale = last_original / last_adj
        sr_pred_close_original = pred_df['close'] * scale
        sr_pred_close_original.name = 'Prediction 预测'
        close_df_original = pd.concat([sr_close_original, sr_pred_close_original], axis=1)
        ax3 = axes[2]
        ax3.plot(close_df_original['Ground Truth 真实值'], label='Ground Truth 真实值', color='blue', linewidth=1.5)
        ax3.plot(close_df_original['Prediction 预测'], label='Prediction 预测', color='red', linewidth=1.5, linestyle='--')
        ax3.set_ylabel('Close Price (不复权) 收盘价', fontsize=14)
        ax3.legend(loc='lower left', fontsize=12)
        ax3.grid(True, alpha=0.3)
        ax = ax3
    else:
        ax = ax2

    # ========== 优化 x 轴时间戳显示 ==========
    # 根据数据长度自动调整刻度密度
    total_days = len(kline_df)

    # 设置横坐标刻度 - 增加显示密度
    # 数据长度 < 500: 每个月显示一个刻度; > 500: 每 3 个月显示一个刻度
    if total_days <= 500:
        ax.xaxis.set_major_locator(mdates.MonthLocator())
    else:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))

    # 格式化为 YYYY-MM-DD
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

    # 旋转标签避免重叠
    plt.setp(ax.get_xticklabels(), rotation=30, ha='right', fontsize=10)

    # 添加标题 - 显示股票代码
    ax1.set_title(f'Kronos Qlib Daily Prediction - {stock_code} 预测对比', fontsize=15)

    # 自动调整布局，避免标签重叠
    plt.tight_layout()
    # 保存图像到文件
    output_dir = "./data"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f'{stock_code}_prediction.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n预测图像已保存: {output_path}")
    # 显示图形
    plt.show(block=False)


if __name__ == "__main__":
    # =========================================================================
    # 配置参数 - 你可以在这里修改
    # =========================================================================
    # 股票代码（Qlib 格式：SH 表示上证，SZ 表示深证）
    # 示例: SH600977（绿城水务）, SH000001（上证指数）, SZ000001（平安银行）
    stock_code = "SH600519"

    # Qlib 数据存放目录
    qlib_data_path = os.path.expanduser("~/.qlib/qlib_data/cn_data")

    # 超参数设置:
    # lookback: 使用多少历史 K 线作为上下文（回看窗口）
    # 注意: 不超过 max_context (对于 small/base 是 512)
    lookback = 400
    # pred_len: 预测未来多少个时间步（日线）
    pred_len = 60

    # =========================================================================
    # 步骤 1: 从 Qlib 加载 A 股日线数据
    # =========================================================================
    print(f"开始从 Qlib 获取 {stock_code} 日线数据...")

    # 检查 Qlib 数据目录是否存在
    qlib_data_path_expanded = os.path.abspath(os.path.expanduser(qlib_data_path))
    if not os.path.exists(qlib_data_path_expanded):
        print(f"\n错误: Qlib 数据目录不存在: {qlib_data_path_expanded}")
        print("")
        print("请先下载 Qlib A 股日线数据，选择以下任意一种方式:")
        print("")
        print("方式一: 下载社区预处理好的数据包")
        print("  mkdir -p ~/.qlib/qlib_data/cn_data")
        print("  wget https://github.com/chenditc/investment_data/releases/latest/download/qlib_bin.tar.gz")
        print("  tar -zxvf qlib_bin.tar.gz -C ~/.qlib/qlib_data/cn_data --strip-components=1")
        print("")
        print("方式二: 使用 Qlib 脚本自动下载")
        print("  cd qlib-master")
        print("  python scripts/get_data.py qlib_data --target_dir ~/.qlib/qlib_data/cn_data --region cn")
        print("")
        sys.exit(1)

    # 初始化 Qlib
    qlib.init(mount_path=qlib_data_path, region=REG_CN)

    # 获取数据时间范围
    # 根据 lookback + pred_len 计算需要多少数据，自动向前取
    # 我们需要总共 lookback + pred_len 条数据来做对比验证
    # 从 2018 年开始获取，足够长的历史
    start_time = "2018-01-01"
    end_time = "2099-12-31"

    # 定义需要获取的字段
    # Qlib 字段: $open $high $low $close $volume $factor
    fields = ["$open", "$high", "$low", "$close", "$volume", "$factor"]

    print(f"  时间范围: {start_time} → {end_time}")
    print("  正在获取数据...")

    # 从 Qlib 获取数据
    df = D.features(
        instruments=[stock_code],
        fields=fields,
        start_time=start_time,
        end_time=end_time,
        freq="day"  # 日线
    )

    # 重置索引，将多级索引变为普通列
    df = df.reset_index()
    print(f"  获取完成，共 {len(df)} 条日线记录")

    # 重命名列，适配 Kronos 格式
    df.rename(columns={
        "$open": "open",
        "$high": "high",
        "$low": "low",
        "$close": "close",
        "$volume": "volume",
        "datetime": "timestamps",
    }, inplace=True)

    # ========== 计算不复权价格（用于绘图显示真实交易价格）==========
    # Qlib 中 $open/$high/$low/$close 本身就是前复权价格，$factor 是复权因子
    # 不复权价格 = 前复权价格 / $factor —— 这样才能得到和行情软件一致的真实价格
    print("  正在计算不复权价格...")
    df_original = df.copy()
    for col in ["open", "high", "low", "close"]:
        df_original[col] = df_original[col] / df_original["$factor"]
    df_original = df_original[["timestamps", "open", "high", "low", "close", "volume"]].copy()

    # ========== 前复权价格已经在 Qlib 中计算完成，直接使用 ==========
    # Qlib 提供的 $open/$high/$low/$close 已经是前复权价格，直接用于模型预测
    # 前复权消除了拆分分红造成的价格跳空，让价格趋势连续，有利于模型预测
    print("  使用 Qlib 前复权价格，无需额外计算")

    # 估算成交额（Qlib 不直接提供 amount，使用 收盘价 × 成交量 近似）
    df["amount"] = df["close"] * df["volume"]

    # 只保留 Kronos 需要的列
    df = df[["timestamps", "open", "high", "low", "close", "volume", "amount"]].copy()

    # 删除可能的空值
    df = df.dropna()

    # 按时间排序（Qlib 已经是排序好的，但这里再确保一次）
    df = df.sort_values('timestamps', ascending=True).reset_index(drop=True)

    print(f"  数据处理完成，最终 {len(df)} 条记录")
    print(f"  时间范围: {df['timestamps'].min()} → {df['timestamps'].max()}")
    print(f"  价格范围: {df['close'].min():.2f} → {df['close'].max():.2f} (最新价: {df['close'].iloc[-1]:.2f})")

    # 检查数据量是否足够
    total_required = lookback + pred_len
    if len(df) < total_required:
        print(f"\n警告: 数据量不足！需要 {total_required} 条，实际只有 {len(df)} 条")
        print("   将使用所有可用数据，lookback = ", len(df) - pred_len)
        lookback = len(df) - pred_len
        if lookback <= 0:
            print("错误: 数据量太少，请扩大时间范围或减少预测长度")
            sys.exit(1)

    # 保存获取到的数据到 CSV，方便后续重用
    output_csv = f"./data/{stock_code}_daily.csv"
    os.makedirs("./data", exist_ok=True)
    df.to_csv(output_csv, index=False)
    print(f"  数据已保存到: {output_csv}")

    # =========================================================================
    # 分割数据
    # =========================================================================
    # 取最后 (lookback + pred_len) 条数据，确保包含最新数据用于绘图对比
    # 这样如果数据更新到 2026 年，图也会显示到 2026 年
    total_required = lookback + pred_len
    df = df.iloc[-total_required:].reset_index(drop=True)

    # x_df: 历史 K 线数据，必须包含 ['open', 'high', 'low', 'close']，volume 和 amount 是可选
    # 这里数据包含所有 6 个维度: open, high, low, close, volume, amount
    x_df = df.loc[:lookback-1, ['open', 'high', 'low', 'close', 'volume', 'amount']]
    # x_timestamp: 历史数据对应的时间戳
    x_timestamp = df.loc[:lookback-1, 'timestamps']
    # y_timestamp: 要预测的未来时间段的时间戳（真实数据，用于对比）
    y_timestamp = df.loc[lookback:lookback+pred_len-1, 'timestamps']

    print(f"\n数据分割:")
    print(f"  历史窗口 (lookback): {lookback} 条")
    print(f"  预测长度 (pred_len): {pred_len} 条")
    print(f"  历史时间: {x_timestamp.iloc[0]} → {x_timestamp.iloc[-1]}")
    print(f"  预测时间: {y_timestamp.iloc[0]} → {y_timestamp.iloc[-1]}")
    print(f"  历史价格范围: {x_df['close'].min():.2f} → {x_df['close'].max():.2f}, 平均: {x_df['close'].mean():.2f}")

    # =========================================================================
    # 步骤 2: 从 Hugging Face Hub 加载预训练的分词器和模型
    # =========================================================================
    print("\n加载预模型...")
    # 加载分词器 - base 版本词汇表大小约 2k
    tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    # 加载 Kronos 模型 - base 版本 102.3M 参数，上下文窗口 512，更高预测精度
    model = Kronos.from_pretrained("NeoQuasar/Kronos-base")
    print("  模型加载完成")

    # =========================================================================
    # 步骤 3: 创建预测器实例
    # =========================================================================
    # max_context: 模型支持的最大上下文长度，Kronos-small/base 是 512
    # 预测器会自动处理超长上下文的截断，以及数据归一化/反归一化
    predictor = KronosPredictor(model, tokenizer, max_context=512)
    print("  预测器初始化完成")

    # =========================================================================
    # 步骤 4: 执行预测
    # =========================================================================
    print("\n开始预测...")
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

    # =========================================================================
    # 步骤 5: 可视化预测结果
    # =========================================================================
    # 打印预测结果的前几行
    print("\n预测完成！Forecasted Data Head:")
    print(pred_df.head())
    if len(pred_df) > 0:
        print(f"\n预测时间范围: {pred_df.index[0]} → {pred_df.index[-1]}")
        print(f"预测价格范围: {pred_df['close'].min():.2f} → {pred_df['close'].max():.2f}")
        print(f"真实价格范围: {df.loc[lookback:lookback+pred_len-1, 'close'].min():.2f} → {df.loc[lookback:lookback+pred_len-1, 'close'].max():.2f}")

    # 提取历史 + 预测区间的真实数据，用于绘图对比
    kline_df = df.loc[:lookback+pred_len-1]

    # 调用绘图函数展示预测结果（包含不复权子图）
    plot_prediction(kline_df, pred_df, stock_code, df_original)

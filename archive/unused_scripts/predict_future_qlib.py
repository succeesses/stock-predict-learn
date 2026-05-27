"""
Kronos 未来纯预测 - 使用 Hugging Face 默认预训练模型
支持两种数据源: Qlib 本地数据库 / 本地 CSV 文件

【特点】
- 直接从 Hugging Face 加载 Kronos 官方预训练模型 (mini/small/base)
- 无需本地微调，开箱即用
- 适合快速验证和一般性预测
- 如追求更高 A 股准确率，请使用 predict_future_finetuned.py (微调后模型)

【常见问题】
如果遇到 SSL 证书错误 (CERTIFICATE_VERIFY_FAILED)，脚本会自动尝试修复。
也可以手动运行: export HF_ENDPOINT=https://hf-mirror.com (使用国内镜像)
"""

import qlib
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import sys
import os
from datetime import datetime, timedelta

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

from model import Kronos, KronosTokenizer, KronosPredictor


def plot_future_prediction(kline_df, pred_df, stock_code, df_original=None):
    """
    绘制未来预测图，只包含历史 + 预测，没有真实值对比

    参数:
        kline_df: 历史 K 线数据（前复权）
        pred_df: 模型预测的 K 线数据
        stock_code: 股票代码
        df_original: 原始不复权数据，用于第二张子图
    """
    # 将 timestamps 转换为 datetime 类型并设置为索引
    kline_df = kline_df.copy()
    kline_df['timestamps'] = pd.to_datetime(kline_df['timestamps'])
    kline_df = kline_df.set_index('timestamps')

    # 提取收盘价数据
    sr_close = kline_df['close']
    sr_close.name = 'Historical (前复权)'

    # 提取预测收盘价
    sr_pred_close = pred_df['close']
    sr_pred_close.name = 'Prediction (预测未来)'

    # 合并
    close_df = pd.concat([sr_close, sr_pred_close], axis=1)

    # 创建图表 - 2 行 1 列，如果有原始数据增加一行变成 3 行
    nrows = 3 if df_original is not None else 2
    fig, axes = plt.subplots(nrows, 1, figsize=(12, 10 if nrows == 3 else 8), sharex=True)

    # ========== 第一个子图: 前复权收盘价 ==========
    ax1 = axes[0] if nrows == 3 else axes[0]
    ax1.plot(close_df['Historical (前复权)'].dropna(), label='Historical 历史', color='blue', linewidth=1.5)
    ax1.plot(close_df['Prediction (预测未来)'].dropna(), label='Kronos Prediction 预测', color='red', linewidth=2, linestyle='--')
    ax1.set_ylabel('Close Price (前复权) 收盘价', fontsize=14)
    ax1.legend(loc='lower left', fontsize=12)
    ax1.grid(True, alpha=0.3)

    # ========== 第二个子图: 成交量 ==========
    ax2 = axes[1] if nrows == 3 else axes[1]
    if 'volume' in pred_df.columns:
        sr_volume = kline_df['volume']
        sr_pred_volume = pred_df['volume']
        sr_volume.name = 'Historical 历史'
        sr_pred_volume.name = 'Prediction 预测'
        volume_df = pd.concat([sr_volume, sr_pred_volume], axis=1)
        ax2.plot(volume_df['Historical 历史'].dropna(), label='Historical 历史', color='blue', linewidth=1)
        ax2.plot(volume_df['Prediction 预测'].dropna(), label='Prediction 预测', color='red', linewidth=1.5, linestyle='--')
        ax2.set_ylabel('Volume 成交量', fontsize=14)
        ax2.legend(loc='upper left', fontsize=12)
        ax2.grid(True, alpha=0)

    # ========== 第三个子图: 不复权收盘价 ==========
    if df_original is not None:
        df_original = df_original.copy()
        df_original['timestamps'] = pd.to_datetime(df_original['timestamps'])
        df_original = df_original.set_index('timestamps')
        # 只显示和预测相同时间范围的历史
        df_original = df_original.loc[kline_df.index]
        sr_close_original = df_original['close']
        sr_close_original.name = 'Historical (不复权) 历史'
        ax3 = axes[2]
        ax3.plot(sr_close_original.dropna(), label='Historical 历史', color='blue', linewidth=1.5)
        # 预测价格需要用同样的缩放比例转换为不复权
        # 使用最后一个历史价格的比例来转换整个预测
        if len(kline_df) > 0:
            last_adj = kline_df['close'].iloc[-1]
            last_original = df_original['close'].iloc[-1]
            scale = last_original / last_adj
            sr_pred_close_original = pred_df['close'] * scale
            sr_pred_close_original.name = 'Prediction (预测未来)'
            close_df_original = pd.concat([sr_close_original, sr_pred_close_original], axis=1)
            ax3.plot(close_df_original['Prediction (预测未来)'].dropna(), label='Kronos Prediction 预测', color='red', linewidth=2, linestyle='--')
        ax3.set_ylabel('Close Price (不复权) 收盘价', fontsize=14)
        ax3.legend(loc='lower left', fontsize=12)
        ax3.grid(True, alpha=0.3)
        ax = ax3
    else:
        ax = ax2

    # ========== 优化 x 轴时间戳显示 ==========
    total_days = len(close_df)
    if total_days <= 500:
        ax.xaxis.set_major_locator(mdates.MonthLocator())
    else:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax.get_xticklabels(), rotation=30, ha='right', fontsize=10)

    # 添加标题
    if df_original is not None:
        axes[0].set_title(f'Kronos Future Prediction 未来预测 - {stock_code} (Next {len(pred_df)} days)', fontsize=15)
    else:
        ax1.set_title(f'Kronos Future Prediction 未来预测 - {stock_code} (Next {len(pred_df)} days)', fontsize=15)

    plt.tight_layout()
    output_dir = "./data"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f'{stock_code}_future_prediction.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n未来预测图像已保存: {output_path}")

    # 保存预测数据到 CSV
    pred_csv = os.path.join(output_dir, f'{stock_code}_future_prediction.csv')
    pred_df.to_csv(pred_csv)
    print(f"未来预测数据已保存: {pred_csv}")

    plt.show(block=False)


if __name__ == "__main__":
    # =========================================================================
    # 配置参数 - 你可以在这里修改
    # =========================================================================
    # 配置参数 - 你可以在这里修改
    # =========================================================================
    # 股票代码（Qlib 格式：SH 表示上证，SZ 表示深证）
    # 示例: SH600519（贵州茅台）, SH000001（上证指数）, SZ000001（平安银行）
    stock_code = "SH600519"

    # ========== 数据来源选择 ==========
    # USE_LOCAL_CSV = False: 从 Qlib 直接获取最新数据
    # USE_LOCAL_CSV = True: 从本地 CSV 读取数据（文件: ./data/{stock_code}_daily.csv）
    #   适合已有 CSV 数据，不想重复获取的情况
    USE_LOCAL_CSV = True  # 默认使用本地 CSV，避免网络问题
    local_csv_path = f"./data/{stock_code}_daily.csv"

    # ========== Hugging Face 模型选择 ==========
    # 可选: "NeoQuasar/Kronos-mini", "NeoQuasar/Kronos-small", "NeoQuasar/Kronos-base"
    # - mini: 4.1M 参数，2048 上下文，最快
    # - small: 24.7M 参数，512 上下文，平衡（推荐）
    # - base: 102.3M 参数，512 上下文，质量最高
    MODEL_NAME = "NeoQuasar/Kronos-small"
    TOKENIZER_NAME = "NeoQuasar/Kronos-Tokenizer-base"

    # Qlib 数据存放目录（仅在 USE_LOCAL_CSV=False 时需要）
    qlib_data_path = os.path.expanduser("~/.qlib/qlib_data/cn_data")

    # 超参数设置:
    # lookback: 使用多少历史 K 线作为上下文（回看窗口）
    # 注意: 不超过 max_context (对于 small/base 是 512, mini 是 2048)
    lookback = 400
    # pred_len: 预测未来多少个时间步（日线）
    pred_len = 60

    # 采样参数
    T = 1.0           # 采样温度，1.0 表示不调整，值越小越确定
    top_p = 0.9       # nucleus 采样参数
    sample_count = 1  # 生成多少条预测路径

    # =========================================================================
    # 步骤 1: 加载数据 - 支持两种方式
    # =========================================================================
    print(f"股票: {stock_code}")
    print(f"使用 Hugging Face 预训练模型: {MODEL_NAME}")
    print(f"数据来源: {'本地 CSV (' + local_csv_path + ')' if USE_LOCAL_CSV else 'Qlib 本地数据库'}")

    df_original = None
    if USE_LOCAL_CSV:
        # ========== 方式 1: 从本地 CSV 读取 ==========
        if not os.path.exists(local_csv_path):
            print(f"\n错误: 本地 CSV 文件不存在: {local_csv_path}")
            print(f"请先运行: python get_stock_data_from_qlib.py 导出数据")
            sys.exit(1)

        print(f"\n从本地 CSV 读取数据: {local_csv_path}")
        df = pd.read_csv(local_csv_path)
        df['timestamps'] = pd.to_datetime(df['timestamps'])
        print(f"  读取完成，共 {len(df)} 条日线记录")

        # ========== 计算不复权价格 ==========
        df_original = df.copy()  # 始终创建，确保 3 个子图都显示
        if '$factor' in df.columns:
            print("  正在计算不复权价格...")
            for col in ["open", "high", "low", "close"]:
                df_original[col] = df_original[col] / df_original["$factor"]
            print("  ✓ 不复权价格计算完成（前复权 ÷ 复权因子）")
        else:
            print("  ⚠  CSV 中无 $factor 列，直接显示前复权价格作为第三张子图")
        df_original = df_original[["timestamps", "open", "high", "low", "close", "volume"]].copy()

        # 确保 amount 列存在
        if 'amount' not in df.columns:
            print("  估算成交额 (close × volume)...")
            df["amount"] = df["close"] * df["volume"]

        # 只保留 Kronos 需要的列
        df = df[["timestamps", "open", "high", "low", "close", "volume", "amount"]].copy()

    else:
        # ========== 方式 2: 从 Qlib 加载 ==========
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
    start_time = "2018-01-01"
    end_time = "2099-12-31"

    # 定义需要获取的字段
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

    # 通用处理：删除空值，排序
    df = df.dropna()
    df = df.sort_values('timestamps', ascending=True).reset_index(drop=True)

    print(f"\n数据处理完成，最终 {len(df)} 条记录")
    print(f"  时间范围: {df['timestamps'].min()} → {df['timestamps'].max()}")
    print(f"  价格范围 (前复权): {df['close'].min():.2f} → {df['close'].max():.2f} (最新价: {df['close'].iloc[-1]:.2f})")
    if df_original is not None and len(df_original) > 0:
        print(f"  价格范围 (不复权): {df_original['close'].min():.2f} → {df_original['close'].max():.2f} (最新价: {df_original['close'].iloc[-1]:.2f})")

    # =========================================================================
    # 分割数据 - 纯预测模式: 使用最后 lookback 条历史，预测未来 pred_len 条
    # =========================================================================
    # 检查数据量是否足够
    if len(df) < lookback:
        print(f"\n错误: 数据量不足！至少需要 {lookback} 条历史，实际只有 {len(df)} 条")
        sys.exit(1)

    # 保存获取到的数据到 CSV
    output_csv = f"./data/{stock_code}_daily.csv"
    os.makedirs("./data", exist_ok=True)
    df.to_csv(output_csv, index=False)
    print(f"  完整数据已保存到: {output_csv}")

    # 取最后 lookback 条作为历史上下文
    df = df.iloc[-lookback:].reset_index(drop=True)
    x_df = df[['open', 'high', 'low', 'close', 'volume', 'amount']]
    x_timestamp = df['timestamps']

    # 生成未来的交易日时间戳
    # 从最后一个历史日期往后推，跳过周末节假日（简单处理：按工作日往后数）
    last_date = pd.to_datetime(x_timestamp.iloc[-1])
    future_dates = []
    current_date = last_date + timedelta(days=1)
    while len(future_dates) < pred_len:
        # 0=Monday, 4=Friday → 只保留工作日
        if current_date.weekday() < 5:
            future_dates.append(current_date)
        current_date += timedelta(days=1)
    y_timestamp = pd.Series(future_dates)

    print(f"\n数据分割 (纯预测模式):")
    print(f"  历史窗口 (lookback): {len(x_df)} 条")
    print(f"  预测长度 (pred_len): {len(y_timestamp)} 条")
    print(f"  历史时间: {x_timestamp.iloc[0]} → {x_timestamp.iloc[-1]}")
    print(f"  预测时间: {y_timestamp.iloc[0]} → {y_timestamp.iloc[-1]}")

    # =========================================================================
    # 步骤 2: 从 Hugging Face Hub 加载预训练的分词器和模型
    # =========================================================================
    print(f"\n从 Hugging Face 加载模型: {MODEL_NAME}")
    print("  (首次运行会自动下载，后续运行使用本地缓存)")
    tokenizer = KronosTokenizer.from_pretrained(TOKENIZER_NAME)
    model = Kronos.from_pretrained(MODEL_NAME)
    print("  模型加载完成")

    # =========================================================================
    # 步骤 3: 创建预测器实例
    # =========================================================================
    # 根据模型类型自动设置 max_context
    if 'mini' in MODEL_NAME:
        max_context = 2048
    else:
        max_context = 512

    predictor = KronosPredictor(model, tokenizer, max_context=max_context)
    print(f"  预测器初始化完成 (max_context={max_context})")

    # =========================================================================
    # 步骤 4: 执行预测
    # =========================================================================
    print("\n开始预测...")
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
    print("\n预测完成！Forecasted Data Head:")
    print(pred_df.head())
    print(f"\n预测价格范围: {pred_df['close'].min():.2f} → {pred_df['close'].max():.2f}")

    # 提取历史数据用于绘图
    kline_df = df.copy()

    # 调用绘图函数展示预测结果（包含不复权子图）
    plot_future_prediction(kline_df, pred_df, stock_code, df_original)

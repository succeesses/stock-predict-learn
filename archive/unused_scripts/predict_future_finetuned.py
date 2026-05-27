"""
Kronos 未来纯预测 - 使用**微调后模型** + Qlib 获取 A 股日线数据
使用所有历史数据到最新日期，预测未来 N 个交易日

区别于 predict_future_qlib.py:
- 使用本地微调后的分词器和预测器，而不是 Hugging Face 下载的默认预训练模型
- 模型路径从 finetune 配置读取
- 支持两种数据来源：从 Qlib 获取 / 从本地 CSV 读取（由 get_stock_data_from_qlib.py 导出）
"""

import qlib
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import sys
import os
from datetime import datetime, timedelta

# 解决 matplotlib 中文显示问题 - 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

from qlib.data import D
from qlib.constant import REG_CN

# 添加 finetune 目录到路径，以便导入 config
sys.path.append("../")
sys.path.append("../finetune")
from finetune.config import Config
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
        axes[0].set_title(f'Kronos Future Prediction 未来预测 - {stock_code} (Next {len(pred_df)} days) [Finetuned Model]', fontsize=15)
    else:
        ax1.set_title(f'Kronos Future Prediction 未来预测 - {stock_code} (Next {len(pred_df)} days) [Finetuned Model]', fontsize=15)

    plt.tight_layout()
    output_dir = "./data"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f'{stock_code}_future_prediction_finetuned.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n未来预测图像已保存: {output_path}")

    # 保存预测数据到 CSV
    pred_csv = os.path.join(output_dir, f'{stock_code}_future_prediction_finetuned.csv')
    pred_df.to_csv(pred_csv)
    print(f"未来预测数据已保存: {pred_csv}")

    plt.show(block=False)



if __name__ == "__main__":
    # =========================================================================
    # 配置参数 - 你可以在这里修改
    # =========================================================================
    # 股票代码（Qlib 格式：SH 表示上证，SZ 表示深证）
    # 示例: SH600519（贵州茅台）, SH000001（上证指数）, SZ000001（平安银行）
    stock_code = "SH600519"

    # ========== 数据来源选择 ==========
    # USE_LOCAL_CSV = False: 从 Qlib 直接获取最新数据（需要 Qlib 数据目录）
    # USE_LOCAL_CSV = True: 从本地 CSV 读取数据（文件: ./data/{stock_code}_daily.csv）
    #   本地 CSV 由 get_stock_data_from_qlib.py 导出，适合网络不好不想重复获取
    USE_LOCAL_CSV = True
    local_csv_path = f"./data/{stock_code}_daily.csv"

    # 从 finetune config 读取模型路径
    finetune_config = Config()
    finetuned_tokenizer_path = finetune_config.finetuned_tokenizer_path
    finetuned_predictor_path = finetune_config.finetuned_predictor_path

    # Qlib 数据存放目录（和 finetune 保持一致，仅在 USE_LOCAL_CSV=False 时需要）
    qlib_data_path = finetune_config.qlib_data_path

    # 超参数设置:
    # lookback: 使用多少历史 K 线作为上下文（回看窗口）
    # 注意: 不超过 max_context (对于 small/base 是 512)
    lookback = 400
    # pred_len: 预测未来多少个时间步（日线）
    pred_len = 60

    # 采样参数（和默认预训练相同）
    T = 1.0           # 采样温度，1.0 表示不调整，值越小越确定，值越大越多样
    top_p = 0.9       # nucleus 采样参数，保留累积概率达到 top_p 的 tokens
    sample_count = 1  # 生成多少条预测路径，多条路径会被平均得到最终预测
                                 # sample_count > 1 可以得到概率预测，提供不确定性估计

    # =========================================================================
    # 步骤 1: 加载数据 - 支持两种方式
    # =========================================================================
    print(f"股票: {stock_code}")
    print(f"使用微调后模型:")
    print(f"  分词器: {finetuned_tokenizer_path}")
    print(f"  预测器: {finetuned_predictor_path}")
    print(f"  数据来源: {'本地 CSV (' + local_csv_path + ')' if USE_LOCAL_CSV else 'Qlib'}")

    df_original = None
    if USE_LOCAL_CSV:
        # ========== 方式 1: 从本地 CSV 读取 ==========
        # CSV 由 get_stock_data_from_qlib.py 导出，格式包含:
        # timestamps, open, high, low, close, volume, amount, $factor
        if not os.path.exists(local_csv_path):
            print(f"\n错误: 本地 CSV 文件不存在: {local_csv_path}")
            print(f"请先运行: python get_stock_data_from_qlib.py 导出数据")
            sys.exit(1)

        print(f"\n从本地 CSV 读取数据: {local_csv_path}")
        df = pd.read_csv(local_csv_path)
        df['timestamps'] = pd.to_datetime(df['timestamps'])
        print(f"  读取完成，共 {len(df)} 条日线记录")

        # ========== 计算不复权价格（用于绘图显示真实交易价格）==========
        # Qlib 中 open/high/low/close 本身就是前复权价格，$factor 是复权因子
        # 不复权价格 = 前复权价格 / $factor —— 这样得到和行情软件一致的真实价格
        df_original = df.copy()  # 始终创建，确保 3 个子图都显示
        if '$factor' in df.columns:
            print("  正在计算不复权价格...")
            for col in ["open", "high", "low", "close"]:
                df_original[col] = df_original[col] / df_original["$factor"]
            print("  ✓ 不复权价格计算完成（前复权 ÷ 复权因子）")
        else:
            print("  ⚠  CSV 中无 $factor 列，直接显示前复权价格作为第三张子图")
        df_original = df_original[["timestamps", "open", "high", "low", "close", "volume"]].copy()

        # 确保 amount 列存在（如果没有，重新计算）
        if 'amount' not in df.columns:
            print("  估算成交额 (close × volume)...")
            df["amount"] = df["close"] * df["volume"]

        # 只保留 Kronos 需要的列
        df = df[["timestamps", "open", "high", "low", "close", "volume", "amount"]].copy()

    else:
        # ========== 方式 2: 从 Qlib 加载 ==========
        # 检查 Qlib 数据目录是否存在
        qlib_data_path_expanded = os.path.abspath(os.path.expanduser(qlib_data_path))
        if not os.path.exists(qlib_data_path_expanded):
            print(f"\n错误: Qlib 数据目录不存在: {qlib_data_path_expanded}")
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
        # Qlib 中 open/high/low/close 本身就是前复权价格，$factor 是复权因子
        # 不复权价格 = 前复权价格 / $factor —— 这样得到和行情软件一致的真实价格
        print("  正在计算不复权价格...")
        df_original = df.copy()
        for col in ["open", "high", "low", "close"]:
            df_original[col] = df_original[col] / df_original["$factor"]
        df_original = df_original[["timestamps", "open", "high", "low", "close", "volume"]].copy()

        # ========== Qlib 提供的已经是前复权价格，直接使用 ==========
        # 估算成交额（Qlib 不直接提供 amount，使用 收盘价 × 成交量 近似）
        df["amount"] = df["close"] * df["volume"]

        # 只保留 Kronos 需要的列
        df = df[["timestamps", "open", "high", "low", "close", "volume", "amount"]].copy()

    # 通用处理：删除空值，排序
    df = df.dropna()
    df = df.sort_values('timestamps', ascending=True).reset_index(drop=True)

    print(f"\n 数据处理完成，最终 {len(df)} 条记录")
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

    # 保存获取到的数据到 CSV（覆盖，方便重用）
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
    # 步骤 2: 加载本地微调后的分词器和模型
    # =========================================================================
    print("\n加载微调后的模型...")
    # Convert to absolute path from project root (finetune directory)
    # finetune_config has paths relative to finetune/ directory, we need to adjust
    finetune_root = os.path.join("..", "finetune")
    if not os.path.isabs(finetuned_tokenizer_path):
        finetuned_tokenizer_path = os.path.join(finetune_root, finetuned_tokenizer_path)
    if not os.path.isabs(finetuned_predictor_path):
        finetuned_predictor_path = os.path.join(finetune_root, finetuned_predictor_path)

    finetuned_tokenizer_path = os.path.abspath(finetuned_tokenizer_path)
    finetuned_predictor_path = os.path.abspath(finetuned_predictor_path)

    print(f"  分词器路径: {finetuned_tokenizer_path}")
    print(f"  预测器路径: {finetuned_predictor_path}")

    # Check if paths exist
    if not os.path.exists(finetuned_tokenizer_path):
        print(f"\n错误: 分词器模型不存在: {finetuned_tokenizer_path}")
        print("请先完成分词器和预测器微调训练: python train_tokenizer_single_gpu.py && python train_predictor_single_gpu.py")
        sys.exit(1)
    if not os.path.exists(finetuned_predictor_path):
        print(f"\n错误: 预测器模型不存在: {finetuned_predictor_path}")
        print("请先完成分词器和预测器微调训练: python train_tokenizer_single_gpu.py && python train_predictor_single_gpu.py")
        sys.exit(1)

    tokenizer = KronosTokenizer.from_pretrained(finetuned_tokenizer_path)
    model = Kronos.from_pretrained(finetuned_predictor_path)
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
    pred_df = predictor.predict(
        df=x_df,                # 历史 K 线数据
        x_timestamp=x_timestamp, # 历史时间戳
        y_timestamp=y_timestamp, # 预测目标时间戳
        pred_len=pred_len,       # 预测长度
        T=T,                     # 采样温度
        top_p=top_p,             # nucleus 采样参数
        sample_count=sample_count, # 生成多少条预测路径，多条路径会被平均得到最终预测
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

    # 提取历史数据用于绘图
    kline_df = df.copy()

    # 调用绘图函数展示预测结果（包含不复权子图）
    plot_future_prediction(kline_df, pred_df, stock_code, df_original)

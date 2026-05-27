"""
Kronos 历史回测验证 - 使用**微调后模型** + 本地 CSV 数据
功能: 在历史区间进行预测，与真实值对比，验证微调模型的准确性

【特点】
- 使用本地微调后的分词器和预测器（准确率更高）
- 从本地 CSV 读取数据（不需要 Qlib 连接）
- 输出预测与真实值对比图和误差指标
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import sys
import os

# ========== Hugging Face SSL 证书修复 ==========
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
# =================================================

# 解决 matplotlib 中文显示问题
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# 添加上级目录到路径
sys.path.append("../")
sys.path.append("../finetune")

from finetune.config import Config
from model import Kronos, KronosTokenizer, KronosPredictor


def plot_backtest_result(history_df, pred_df, stock_code, df_original=None):
    """
    绘制回测结果图，包含:
    1. 前复权收盘价: 历史 + 预测 vs 真实值
    2. 成交量
    3. 不复权收盘价（如果有 $factor）
    """
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)

    # ========== 子图 1: 前复权收盘价 ==========
    ax1 = axes[0]

    # 历史价格
    ax1.plot(history_df['timestamps'], history_df['close'],
             label='Historical 历史数据', color='blue', linewidth=1.5)

    # 真实未来价格
    ax1.plot(pred_df['timestamps'], pred_df['close'],
             label='Ground Truth 真实值', color='green', linewidth=1.5, linestyle='-')

    # 预测价格
    ax1.plot(pred_df['timestamps'], pred_df['pred_close'],
             label='Prediction 模型预测', color='red', linewidth=2, linestyle='--')

    ax1.axvline(x=history_df['timestamps'].iloc[-1], color='gray',
                linestyle=':', linewidth=2, label='Prediction Start 预测起点')
    ax1.set_ylabel('Close Price (前复权) 收盘价', fontsize=12)
    ax1.legend(loc='upper left', fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.set_title(f'Kronos 回测验证 - {stock_code} (微调模型)', fontsize=14, pad=20)

    # ========== 子图 2: 成交量 ==========
    ax2 = axes[1]
    ax2.plot(history_df['timestamps'], history_df['volume'],
             label='Historical 历史', color='blue', linewidth=1)
    ax2.plot(pred_df['timestamps'], pred_df['volume'],
             label='Ground Truth 真实', color='green', linewidth=1)
    ax2.set_ylabel('Volume 成交量', fontsize=12)
    ax2.legend(loc='upper left', fontsize=10)
    ax2.grid(True, alpha=0.3)

    # ========== 子图 3: 不复权收盘价 ==========
    ax3 = axes[2]
    if df_original is not None:
        # 截取 df_original 到回测的时间范围（和 history_df + pred_df 对应）
        start_time = history_df['timestamps'].iloc[0]
        end_time = pred_df['timestamps'].iloc[-1]
        df_original_range = df_original[
            (df_original['timestamps'] >= start_time) &
            (df_original['timestamps'] <= end_time)
        ].reset_index(drop=True)

        # 历史不复权
        history_original = df_original_range[df_original_range['timestamps'] <= history_df['timestamps'].iloc[-1]]
        ax3.plot(history_original['timestamps'], history_original['close'],
                 label='Historical (不复权) 历史', color='blue', linewidth=1.5)

        # 真实未来不复权
        future_original = df_original_range[df_original_range['timestamps'] > history_df['timestamps'].iloc[-1]]
        if len(future_original) > 0:
            ax3.plot(future_original['timestamps'], future_original['close'],
                     label='Ground Truth (不复权) 真实值', color='green', linewidth=1.5)

        # 预测价格转换为不复权（用最后一个历史价格的比例）
        if len(history_original) > 0:
            last_adj = history_df['close'].iloc[-1]
            last_original = history_original['close'].iloc[-1]
            scale = last_original / last_adj
            pred_close_original = pred_df['pred_close'] * scale
            ax3.plot(pred_df['timestamps'], pred_close_original,
                     label='Prediction (不复权) 预测', color='red', linewidth=2, linestyle='--')

        ax3.set_ylabel('Close Price (不复权) 收盘价', fontsize=12)
        ax3.legend(loc='upper left', fontsize=10)
        ax3.grid(True, alpha=0.3)
    else:
        ax3.text(0.5, 0.5, 'CSV 中无 $factor 列，无法计算不复权价格\n\n建议重新导出 CSV: python get_stock_data_from_qlib.py',
                 ha='center', va='center', transform=ax3.transAxes, fontsize=12)
        ax3.set_ylabel('Close Price 收盘价', fontsize=12)

    # 优化 x 轴显示
    ax3.xaxis.set_major_locator(mdates.MonthLocator())
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax3.get_xticklabels(), rotation=30, ha='right', fontsize=9)
    ax3.set_xlabel('Date 日期', fontsize=12)

    plt.tight_layout()

    # 保存图像
    output_dir = "./data"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f'{stock_code}_backtest_finetuned.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n回测图像已保存: {output_path}")

    plt.show(block=False)


def calculate_metrics(pred_df):
    """计算预测误差指标"""
    y_true = pred_df['close']
    y_pred = pred_df['pred_close']

    mae = np.mean(np.abs(y_true - y_pred))
    mse = np.mean((y_true - y_pred) ** 2)
    rmse = np.sqrt(mse)
    mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100

    # 方向准确率（预测涨跌幅方向是否正确）
    true_change = np.sign(y_true.values[1:] - y_true.values[:-1])
    pred_change = np.sign(y_pred.values[1:] - y_pred.values[:-1])
    direction_acc = np.mean(true_change == pred_change) * 100

    print("\n" + "="*50)
    print("回测误差指标 (微调模型)")
    print("="*50)
    print(f"MAE  平均绝对误差: {mae:.4f}")
    print(f"MSE  均方误差:     {mse:.4f}")
    print(f"RMSE 均方根误差:   {rmse:.4f}")
    print(f"MAPE 平均绝对百分比误差: {mape:.2f}%")
    print(f"方向准确率:         {direction_acc:.2f}%")
    print("="*50)

    return {
        'MAE': mae,
        'MSE': mse,
        'RMSE': rmse,
        'MAPE': mape,
        'direction_acc': direction_acc
    }


if __name__ == "__main__":
    # =========================================================================
    # 配置参数 - 你可以在这里修改
    # =========================================================================
    # 股票代码（用于文件名和显示）
    stock_code = "SH600519"

    # 本地 CSV 路径（由 get_stock_data_from_qlib.py 导出）
    local_csv_path = f"./data/{stock_code}_daily.csv"

    # 回测参数
    lookback = 400       # 历史回看窗口大小
    pred_len = 60        # 预测未来天数

    # 回测起点（从数据末尾往前推多少天开始）
    # 例如: BACKTEST_OFFSET = 100 表示用倒数第 500 天到第 100 天作为历史，
    # 预测倒数第 100 天到倒数第 40 天，然后和真实值对比
    backtest_offset = 100

    # =========================================================================
    # 步骤 1: 加载本地 CSV 数据
    # =========================================================================
    print("="*60)
    print("Kronos 回测验证 (微调模型)")
    print("="*60)

    if not os.path.exists(local_csv_path):
        print(f"\n错误: 本地 CSV 文件不存在: {local_csv_path}")
        print(f"请先运行: python get_stock_data_from_qlib.py 导出数据")
        sys.exit(1)

    print(f"\n从本地 CSV 读取数据: {local_csv_path}")
    df = pd.read_csv(local_csv_path)
    df['timestamps'] = pd.to_datetime(df['timestamps'])
    print(f"  读取完成，共 {len(df)} 条日线记录")

    # 计算不复权价格（如果有 $factor）
    df_original = None
    if '$factor' in df.columns:
        print("  ✓ 检测到 $factor 列，正在计算不复权价格...")
        df_original = df.copy()
        for col in ["open", "high", "low", "close"]:
            df_original[col] = df_original[col] / df_original["$factor"]
        df_original = df_original[["timestamps", "open", "high", "low", "close", "volume"]].copy()
        print("  ✓ 不复权价格计算完成，将在第三子图显示")
    else:
        print("  ⚠  CSV 中无 $factor 列，第三子图将不显示不复权价格")
        print("     建议重新导出数据: python get_stock_data_from_qlib.py")

    # 确保 amount 列存在
    if 'amount' not in df.columns:
        df["amount"] = df["close"] * df["volume"]

    # 只保留需要的列
    df = df[["timestamps", "open", "high", "low", "close", "volume", "amount"]].copy()

    # 删除空值并排序
    df = df.dropna()
    df = df.sort_values('timestamps', ascending=True).reset_index(drop=True)

    # =========================================================================
    # 步骤 2: 分割回测数据
    # =========================================================================
    total_needed = lookback + pred_len + backtest_offset

    if len(df) < total_needed:
        print(f"\n错误: 数据量不足！回测需要至少 {total_needed} 条记录，实际只有 {len(df)} 条")
        print(f"  请减小 lookback 或 pred_len，或更新 CSV 数据")
        sys.exit(1)

    # 找到预测起点
    predict_start_idx = len(df) - backtest_offset - pred_len
    history_end_idx = predict_start_idx

    print(f"\n数据分割:")
    print(f"  历史窗口: 第 {history_end_idx - lookback} 行 → 第 {history_end_idx} 行")
    print(f"  预测区间: 第 {history_end_idx} 行 → 第 {history_end_idx + pred_len} 行")
    print(f"  历史日期: {df['timestamps'].iloc[history_end_idx - lookback]} → {df['timestamps'].iloc[history_end_idx]}")
    print(f"  预测日期: {df['timestamps'].iloc[history_end_idx]} → {df['timestamps'].iloc[history_end_idx + pred_len - 1]}")

    # 提取历史数据（用于模型预测）
    history_df = df.iloc[history_end_idx - lookback : history_end_idx].reset_index(drop=True)
    future_df = df.iloc[history_end_idx : history_end_idx + pred_len].reset_index(drop=True)

    # =========================================================================
    # 步骤 3: 加载微调后的模型
    # =========================================================================
    print("\n加载微调后的模型...")

    finetune_config = Config()
    tokenizer_path = os.path.abspath(os.path.join("..", "finetune", finetune_config.finetuned_tokenizer_path))
    predictor_path = os.path.abspath(os.path.join("..", "finetune", finetune_config.finetuned_predictor_path))

    print(f"  分词器路径: {tokenizer_path}")
    print(f"  预测器路径: {predictor_path}")

    if not os.path.exists(tokenizer_path):
        print(f"\n错误: 微调分词器不存在: {tokenizer_path}")
        print("请先运行微调: cd finetune && python train_tokenizer_single_gpu.py")
        sys.exit(1)
    if not os.path.exists(predictor_path):
        print(f"\n错误: 微调预测器不存在: {predictor_path}")
        print("请先运行微调: cd finetune && python train_predictor_single_gpu.py")
        sys.exit(1)

    tokenizer = KronosTokenizer.from_pretrained(tokenizer_path)
    model = Kronos.from_pretrained(predictor_path)
    print("  模型加载完成")

    # =========================================================================
    # 步骤 4: 创建预测器并执行预测
    # =========================================================================
    predictor = KronosPredictor(model, tokenizer, max_context=512)
    print("  预测器初始化完成")

    print("\n开始预测...")
    pred_result = predictor.predict(
        df=history_df[['open', 'high', 'low', 'close', 'volume', 'amount']],
        x_timestamp=history_df['timestamps'],
        y_timestamp=future_df['timestamps'],
        pred_len=pred_len,
        T=1.0,
        top_p=0.9,
        sample_count=1,
        verbose=True
    )

    # =========================================================================
    # 步骤 5: 合并预测结果和真实值
    # =========================================================================
    pred_result = pred_result.reset_index()
    pred_result.rename(columns={'index': 'timestamps'}, inplace=True)

    # 合并预测和真实值
    pred_df = future_df.copy()
    pred_df['pred_close'] = pred_result['close'].values
    pred_df['pred_high'] = pred_result['high'].values
    pred_df['pred_low'] = pred_result['low'].values
    pred_df['pred_open'] = pred_result['open'].values

    # 保存预测结果
    output_dir = "./data"
    os.makedirs(output_dir, exist_ok=True)
    output_csv = os.path.join(output_dir, f'{stock_code}_backtest_finetuned.csv')
    pred_df.to_csv(output_csv, index=False)
    print(f"\n回测数据已保存: {output_csv}")

    # =========================================================================
    # 步骤 6: 计算指标和绘图
    # =========================================================================
    calculate_metrics(pred_df)
    plot_backtest_result(history_df, pred_df, stock_code, df_original)

    print("\n回测完成！")

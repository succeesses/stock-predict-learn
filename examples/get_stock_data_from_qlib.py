"""
从 Qlib 本地缓存获取股票数据 → 导出为 Kronos 可用的 CSV 格式
优先使用 Qlib 本地已有数据（你手动下载/更新的 cn_data），不需要每次重新从网络下载
适合：已经通过 Qlib 下载好全市场数据，只需要导出单只股票给 Kronos 预测
"""

import qlib
import pandas as pd
import numpy as np
import sys
import os
from qlib.data import D
from qlib.constant import REG_CN
from datetime import datetime


def get_stock_data_from_qlib(
    stock_code,
    qlib_data_path="~/.qlib/qlib_data/cn_data",
    start_time=None,
    end_time=None
):
    """
    从 Qlib 本地读取股票数据，导出为 Kronos 格式 CSV

    参数:
        stock_code: Qlib 格式股票代码 SH600977
        qlib_data_path: Qlib 数据目录
        start_time: 获取起始时间，None 表示从最早开始
        end_time: 获取结束时间，None 表示到最新

    返回:
        导出的 CSV 文件路径
    """
    # 展开用户目录
    qlib_data_path = os.path.abspath(os.path.expanduser(qlib_data_path))

    print(f"========== Qlib 导出单只股票数据 ==========")
    print(f"Qlib 数据目录: {qlib_data_path}")

    # 检查数据目录是否存在
    if not os.path.exists(qlib_data_path):
        print(f"\n错误: Qlib 数据目录不存在: {qlib_data_path}")
        print("请先确认 Qlib 数据已经下载完成")
        return None

    # 初始化 Qlib
    print("\n初始化 Qlib...")
    qlib.init(mount_path=qlib_data_path, region=REG_CN)

    # 设置默认时间范围
    if start_time is None:
        start_time = "2010-01-01"
    if end_time is None:
        end_time = datetime.now().strftime("%Y-%m-%d")

    print(f"股票代码: {stock_code}")
    print(f"时间范围: {start_time} → {end_time}")

    # 定义需要获取的字段
    # Qlib 字段: $open $high $low $close $volume $factor
    fields = ["$open", "$high", "$low", "$close", "$volume", "$factor"]

    print("\n从 Qlib 读取数据...")
    # 从 Qlib 获取数据
    df = D.features(
        instruments=[stock_code],
        fields=fields,
        start_time=start_time,
        end_time=end_time,
        freq="day"  # 日线
    )

    # 重置索引
    df = df.reset_index()
    print(f"读取完成，共 {len(df)} 条记录")

    if len(df) == 0:
        print(f"错误: Qlib 中没有找到 {stock_code} 的数据，请检查代码是否正确")
        print(f"代码格式应为: SH600977 (上证) / SZ000001 (深证)")
        return None

    # 重命名列，适配 Kronos 格式
    df.rename(columns={
        "$open": "open",
        "$high": "high",
        "$low": "low",
        "$close": "close",
        "$volume": "volume",
        "datetime": "timestamps",
    }, inplace=True)

    # ========== 计算前复权价格（这一步必须！）==========
    # Qlib 保存的是原始不复权价格，需要乘以复权因子得到前复权价格
    # 前复权可以消除拆分分红造成的价格跳空，让价格趋势连续正确
    print("\n计算前复权价格...")
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col] * df["$factor"]

    # 估算成交额（Qlib 不直接提供 amount，用 close × volume 近似）
    df["amount"] = df["close"] * df["volume"]

    # 保留 Kronos 需要的列 + $factor 复权因子（用于计算不复权价格）
    kronos_df = df[["timestamps", "open", "high", "low", "close", "volume", "amount", "$factor"]].copy()

    # 删除空值
    kronos_df = kronos_df.dropna()

    # 按时间排序（Qlib 已经有序，这里再确保一次）
    kronos_df = kronos_df.sort_values('timestamps', ascending=True).reset_index(drop=True)

    # ========== 保存 CSV ==========
    output_dir = "./data"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{stock_code}_daily.csv")

    kronos_df.to_csv(output_file, index=False)

    # 打印信息
    print(f"\n========== 导出完成 ==========")
    print(f"✓ 输出文件: {output_file}")
    print(f"✓ 总记录数: {len(kronos_df)}")
    print(f"✓ 时间范围: {kronos_df['timestamps'].min()} → {kronos_df['timestamps'].max()}")
    print("")
    print("现在可以运行 prediction_qlib_daily.py 进行预测了!")

    return output_file


if __name__ == "__main__":
    # ========== 配置 ==========
    # 你要导出的股票代码（Qlib 格式）
    # SH 开头 = 上海交易所，SZ 开头 = 深圳交易所
    # 示例: SH600977（绿城水务），SZ000001（平安银行），SH000001（上证指数）
    STOCK_CODE = "SH600519"

    # Qlib 数据目录 - 一般不需要改
    QLIB_DATA_PATH = "~/.qlib/qlib_data/cn_data"

    # 时间范围 - 留空就是自动获取全部
    # 如果只需要最近几年，可以设置 START_TIME = "2018-01-01"
    START_TIME = None   # None = 从最早开始
    END_TIME = None     # None = 到最新结束

    # ========== 运行 ==========
    get_stock_data_from_qlib(
        stock_code=STOCK_CODE,
        qlib_data_path=QLIB_DATA_PATH,
        start_time=START_TIME,
        end_time=END_TIME
    )

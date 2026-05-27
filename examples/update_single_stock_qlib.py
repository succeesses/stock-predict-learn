"""
单独更新单只股票数据到最新日期
用于 Qlib 基础数据已有，但需要更新到最新的情况
解决全市场更新遇到网络限制的问题
"""

import qlib
import pandas as pd
import numpy as np
import sys
import os
from qlib.data import D
from qlib.constant import REG_CN
from datetime import datetime

import yahooquery
from yahooquery import Ticker


def update_single_stock(stock_code, qlib_data_path, end_date=None):
    """
    更新单只股票数据到最新日期

    参数:
        stock_code: Qlib 格式，如 SH600977
        qlib_data_path: Qlib 数据目录
        end_date: 结束日期，默认今天
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    print(f"开始更新单只股票: {stock_code}")
    print(f"目标结束日期: {end_date}")

    # 初始化 Qlib
    qlib.init(mount_path=qlib_data_path, region=REG_CN)

    # 转换代码为 Yahoo Finance 格式
    # SH600977 -> 600977.SS
    # SZ000001 -> 000001.SZ
    if stock_code.startswith('SH'):
        yahoo_code = f"{stock_code[2:]}.SS"
    elif stock_code.startswith('SZ'):
        yahoo_code = f"{stock_code[2:]}.SZ"
    else:
        raise ValueError(f"Unknown stock code prefix: {stock_code}")

    print(f"Yahoo Finance 代码: {yahoo_code}")

    # 从 Yahoo Finance 获取最新数据
    print("正在从 Yahoo Finance 获取最新数据...")
    ticker = Ticker(yahoo_code)
    try:
        df = ticker.history(period='max', interval='1d')
    except Exception as e:
        print(f"获取数据失败: {e}")
        return None

    if df.empty:
        print("获取到空数据")
        return None

    df = df.reset_index()
    print(f"获取到 {len(df)} 条日线数据")
    print(f"Yahoo 时间范围: {df['date'].min()} → {df['date'].max()}")

    # 转换列名
    df = df.rename(columns={
        'date': 'datetime',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'volume': 'volume',
    })

    # 计算复权因子 - Yahoo Finance 的数据已经是复权后的价格
    # Qlib 需要存储不复权价格 + 复权因子，我们这里已经是复权后，所以 factor=1
    df['factor'] = 1.0

    # 提取 instrument 名
    df['instrument'] = stock_code

    print(f"处理后数据: {len(df)} 条")

    # 保存为 CSV 供 Kronos 直接使用
    output_csv = f"./data/{stock_code}_daily.csv"
    os.makedirs("./data", exist_ok=True)

    # 转换为 Kronos 需要的格式
    kronos_df = df[['datetime', 'open', 'high', 'low', 'close', 'volume']].copy()
    kronos_df = kronos_df.rename(columns={'datetime': 'timestamps'})
    # 估算 amount = close * volume
    kronos_df['amount'] = kronos_df['close'] * kronos_df['volume']

    # 按时间排序
    kronos_df = kronos_df.sort_values('timestamps').reset_index(drop=True)

    kronos_df.to_csv(output_csv, index=False)
    print(f"\n✓ 已保存到: {output_csv}")
    print(f"  时间范围: {kronos_df['timestamps'].min()} → {kronos_df['timestamps'].max()}")
    print(f"  总条数: {len(kronos_df)}")

    print("\n现在可以直接运行 prediction_qlib_daily.py 进行预测了！")
    return kronos_df


if __name__ == "__main__":
    # ========== 配置 ==========
    # 你要更新的股票
    STOCK_CODE = "SH600977"  # 修改这里换成你要的股票

    # Qlib 数据目录
    QLIB_DATA_PATH = os.path.expanduser("~/.qlib/qlib_data/cn_data")

    # 结束日期 - 默认今天，如果不需要到今天可以修改
    END_DATE = None

    # ========== 运行 ==========
    result = update_single_stock(STOCK_CODE, QLIB_DATA_PATH, END_DATE)

    if result is None:
        sys.exit(1)

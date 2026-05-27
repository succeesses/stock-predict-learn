"""
生成随机游走数据作为示例
我们需要至少 400 + 120 = 520 条数据
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 起始时间
start_date = datetime(2024, 1, 1, 9, 35)

# 生成 520 条 5分钟数据
n = 520
dates = []
current = start_date
for i in range(n):
    dates.append(current)
    # 加5分钟，跳过收盘时间（这里简化处理）
    current += timedelta(minutes=5)
    # 如果到了15:00之后，跳到第二天9:35
    if current.hour >= 15:
        current = current + timedelta(days=1)
        current = current.replace(hour=9, minute=35)

# 生成随机游走价格
np.random.seed(42)  # 固定种子保证可复现
base_price = 10.0
returns = np.random.normal(0.000, 0.015, n)
prices = base_price * (1 + returns).cumprod()

# 生成 OHLCVA 数据
# 使用一个简单的方法生成合理的OHLC：开盘=前收，高/低在涨跌范围内
data = []
prev_close = base_price
for i in range(n):
    current_price = prices[i]
    # open = prev_close
    open_p = prev_close
    # high = max(open_p, current_price) + np.random.uniform(0, 0.02 * open_p)
    # low = min(open_p, current_price) - np.random.uniform(0, 0.02 * open_p)
    high_p = max(open_p, current_price) * (1 + np.random.uniform(0, 0.02))
    low_p = min(open_p, current_price) * (1 - np.random.uniform(0, 0.02))
    close_p = current_price
    volume = np.random.randint(800000, 1500000)
    amount = volume * close_p
    data.append({
        'timestamps': dates[i].strftime('%Y-%m-%d %H:%M'),
        'open': round(open_p, 4),
        'high': round(high_p, 4),
        'low': round(low_p, 4),
        'close': round(close_p, 4),
        'volume': volume,
        'amount': round(amount, 2),
    })
    prev_close = current_price

df = pd.DataFrame(data)
df.to_csv("./data/XSHG_5min_600977.csv", index=False)

print(f"Generated {len(df)} random 5-minute K-line records")
print(f"  Time range: {df['timestamps'].iloc[0]} to {df['timestamps'].iloc[-1]}")
print(f"  Price range: {df['close'].min():.2f} ~ {df['close'].max():.2f}")
print(f"  File saved to: examples/data/XSHG_5min_600977.csv")

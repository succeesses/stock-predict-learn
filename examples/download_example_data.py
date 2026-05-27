"""
下载示例数据 XSHG_5min_600977.csv
使用 AKShare 获取 绿城水利(600977) 5分钟K线数据
"""

import akshare as ak
import pandas as pd
import os

# 创建data目录
os.makedirs("./data", exist_ok=True)

# 获取600977 绿城水务（原绿城水务，现叫绿城水务）
stock_code = "600977"

print(f"正在获取 {stock_code} 5分钟K线数据...")
df = ak.stock_zh_a_hist_min_em(symbol=stock_code, period="5")

# 转换列名符合Kronos要求
df.rename(columns={
    '时间': 'timestamps',
    '开盘': 'open',
    '最高': 'high',
    '最低': 'low',
    '收盘': 'close',
    '成交量': 'volume',
    '成交额': 'amount',
}, inplace=True)

# 只保留需要的列
df = df[['timestamps', 'open', 'high', 'low', 'close', 'volume', 'amount']]

# 转换时间格式
df['timestamps'] = pd.to_datetime(df['timestamps'])

# 按时间排序
df = df.sort_values('timestamps', ascending=True)

# 保存
output_file = f"./data/XSHG_5min_{stock_code}.csv"
df.to_csv(output_file, index=False)

print(f"数据已保存到 examples/{output_file}")
print(f"  共 {len(df)} 条5分钟K线记录")
print(f"  时间范围: {df['timestamps'].min()} 到 {df['timestamps'].max()}")

# 使用 AKShare 获取 A 股 K 线数据教程

本文介绍如何使用 Python 的 `akshare` 库免费获取 A 股日线和 5 分钟 K 线数据，并将其保存为符合 Kronos 项目要求的 CSV 格式。

## 什么是 AKShare

AKShare 是一个开源的 Python 财经数据接口包，**完全免费**，支持获取 A 股、港股、美股等市场的历史行情数据、基本面数据等。

- GitHub: https://github.com/akfamily/akshare
- 文档: https://akshare.akfamily.xyz/

## 安装 AKShare

```bash
pip install akshare --upgrade
```

## 获取 A 股日线数据

### 完整代码示例

```python
import akshare as ak
import pandas as pd

def get_a_stock_daily(stock_code: str, output_file: str = None):
    """
    获取 A 股某只股票的日线数据
    
    参数:
        stock_code: 股票代码，格式为 "600580" （不需要加市场前缀SH/SZ，akshare会自动识别）
        output_file: 输出CSV文件路径，为None则不保存
    
    返回:
        df: 包含K线数据的DataFrame
    """
    # 获取日线数据
    # ak.stock_zh_a_hist() 返回A股历史行情数据
    # - symbol: 股票代码
    # - period: 频率，"daily"表示日线
    # - adjust: 复权方式，"qfq"前复权，"hfq"后复权，""不复权
    df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
    
    # 将列名转换为Kronos要求的格式
    # akshare返回的列名是: 日期,开盘,收盘,最高,最低,涨跌幅,换手率,成交量,成交额
    df.rename(columns={
        '日期': 'timestamps',
        '开盘': 'open',
        '最高': 'high',
        '最低': 'low',
        '收盘': 'close',
        '成交量': 'volume',
        '成交额': 'amount',
    }, inplace=True)
    
    # 只保留Kronos需要的列
    df = df[['timestamps', 'open', 'high', 'low', 'close', 'volume', 'amount']]
    
    # 转换时间戳格式
    df['timestamps'] = pd.to_datetime(df['timestamps'])
    
    # 按时间升序排序（akshare默认已经是升序）
    df = df.sort_values('timestamps', ascending=True)
    
    # 保存为CSV
    if output_file is not None:
        df.to_csv(output_file, index=False)
        print(f"数据已保存到: {output_file}, 共 {len(df)} 条记录")
    
    return df

# ===== 使用示例 =====
if __name__ == "__main__":
    # 获取 卧龙电驱(600580) 日线数据
    stock_code = "600580"
    df_daily = get_a_stock_daily(
        stock_code=stock_code,
        output_file=f"./{stock_code}_daily.csv"
    )
    print("\n数据预览:")
    print(df_daily.head())
    print(f"\n时间范围: {df_daily['timestamps'].min()} 到 {df_daily['timestamps'].max()}")
```

### 输出说明

获取到的数据格式（符合Kronos要求）：

| timestamps | open | high | low  | close | volume  | amount     |
|------------|------|------|------|-------|---------|------------|
| 1998-09-24 | 6.18 | 6.88 | 5.98 |  6.68 | 3124500 | 2070000000 |
| 1998-09-25 | 6.62 | 6.98 | 6.48 |  6.88 | 1602500 | 1080000000 |
| ...        | ...  | ...  | ...  |  ...  | ...     | ...        |

## 获取 A 股 5 分钟 K 线数据

### 完整代码示例

```python
import akshare as ak
import pandas as pd
from datetime import datetime

def get_a_stock_5min(stock_code: str, output_file: str = None):
    """
    获取 A 股某只股票的 5 分钟 K 线数据
    
    参数:
        stock_code: 股票代码，例如 "600580"
        output_file: 输出CSV文件路径
    
    返回:
        df: 包含5分钟K线数据的DataFrame
    """
    # 获取5分钟K线数据
    # ak.stock_zh_a_hist_min_em() 获取A股分钟级历史行情（东方财富数据源）
    # - symbol: 股票代码
    # - period: 分钟频率，支持 "5", "15", "30", "60"
    df = ak.stock_zh_a_hist_min_em(symbol=stock_code, period="5")
    
    # 转换列名
    # akshare返回: 时间,开盘,收盘,最高,最低,涨跌幅,成交量,成交额
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
    
    # 时间格式转换
    df['timestamps'] = pd.to_datetime(df['timestamps'])
    
    # 按时间排序
    df = df.sort_values('timestamps', ascending=True)
    
    # 保存
    if output_file is not None:
        df.to_csv(output_file, index=False)
        print(f"5分钟数据已保存到: {output_file}, 共 {len(df)} 条记录")
    
    return df

# ===== 使用示例 =====
if __name__ == "__main__":
    stock_code = "600580"
    df_5min = get_a_stock_5min(
        stock_code=stock_code,
        output_file=f"./{stock_code}_5min.csv"
    )
    print("\n数据预览:")
    print(df_5min.head())
    print(f"\n时间范围: {df_5min['timestamps'].min()} 到 {df_5min['timestamps'].max()}")
```

### 说明

- AKShare 的分钟级数据来自东方财富，**最近几年**的数据都可以获取到
- 如果需要获取更远历史的分钟数据，可能需要分多次获取或者使用其他数据源
- 5分钟数据量比日线大很多，一只股票最近几年通常会有几万条数据

## 同时获取多只股票数据示例

```python
import os
from get_a_stock_daily import get_a_stock_daily
from get_a_stock_5min import get_a_stock_5min

# 股票代码列表
stock_codes = ["600580", "000021", "002354", "300207"]

# 创建输出目录
os.makedirs("./data", exist_ok=True)

# 获取日线
for code in stock_codes:
    print(f"正在获取 {code} 日线数据...")
    get_a_stock_daily(code, output_file=f"./data/{code}_daily.csv")

# 获取5分钟
for code in stock_codes:
    print(f"正在获取 {code} 5分钟数据...")
    get_a_stock_5min(code, output_file=f"./data/{code}_5min.csv")
```

## 数据格式说明（给 Kronos 用）

获取的数据直接就是 Kronos `finetune_csv` 目录要求的格式：

| 列名 | 说明 | 是否必须 |
|------|------|----------|
| timestamps | 时间戳，格式可以是 `YYYY-MM-DD`（日线）或 `YYYY-MM-DD HH:MM`（分钟线） | 必填 |
| open | 开盘价 | 必填 |
| high | 最高价 | 必填 |
| low | 最低价 | 必填 |
| close | 收盘价 | 必填 |
| volume | 成交量 | 必填（没有数据填 0） |
| amount | 成交额 | 必填（没有数据填 0） |

如果你的数据源没有 `volume` 或 `amount`，可以全填0，Kronos模型依然可以工作。

## 在 Kronos 中使用获取到的数据

1. 将保存好的CSV文件路径填入配置文件 `finetune_csv/configs/your_config.yaml`:

```yaml
data:
  data_path: "/path/to/your/600580_daily.csv"  # 这里换成你刚才保存的文件路径
  lookback_window: 400      # 使用400天历史
  predict_window: 5         # 预测未来5天
  max_context: 512
```

2. 运行微调：

```bash
cd finetune_csv
python train_sequential.py --config configs/your_config.yaml
```

## 注意事项

### 1. 股票代码格式

AKShare 识别 A 股股票代码只需要纯数字：
- ✅ 正确: `"600580"`, `"000001"`, `"300750"`
- ❌ 错误: `"SH600580"`, `"SZ000001"`（不需要前缀）

### 2. 复权选择

建议使用**前复权**（`adjust="qfq"`）：
- 前复权会调整历史价格，保持价格连续性
- 更适合机器学习建模，因为价格走势更连贯

如果你不想复权，使用 `adjust=""`。

### 3. 获取频率限制

AKShare 完全免费，但建议不要频繁请求，可以：
- 一次性获取后保存到本地，后续直接读取CSV
- 每天更新一次即可，不需要每分钟更新
- 如果遇到 IP 限制，休息几分钟再试

### 4. 数据量

| 数据频率 | 一年的数据量 | 十年的数据量 |
|----------|-------------|-------------|
| 日线 | ~250 条 | ~2500 条 |
| 5分钟 | ~250 × 48 = **12000** 条 | ~120000 条 |

5分钟数据量较大，请确保磁盘空间足够。

### 5. 最新数据

- 日线：交易日收盘后，晚间就能获取到当日数据
- 5分钟：盘中实时更新，延迟大约几分钟

## 常见问题

**Q: 获取不到数据怎么办？**
- A: 检查股票代码格式，必须是纯数字，不需要SH/SZ前缀。检查网络连接，确保能访问东方财富网站。

**Q: 获取的5分钟数据只有最近几年，历史数据没有怎么办？**
- A: AKShare 免费接口只提供最近几年的分钟级数据，这是正常的。如果需要更早的分钟数据，可以考虑使用付费数据源或者Tushare。

**Q: 获取的数据如何直接给Kronos预测？**
- A: 保存的CSV格式已经完全符合Kronos要求，可以直接使用。只需要在配置文件中指定 `data_path` 即可。

**Q: 可以获取其他频率吗（1分钟、15分钟、30分钟、60分钟）？**
- A: 可以，AKShare 支持 `period="1"`, `"15"`, `"30"`, `"60"`，只需要修改代码中对应的period参数即可。

## 参考链接

- AKShare 官方文档: https://akshare.akfamily.xyz/data/stock/stock.html#id1
- AKShare GitHub: https://github.com/akfamily/akshare
- Kronos GitHub: https://github.com/shiyu-coder/Kronos

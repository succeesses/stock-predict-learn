# 使用 Qlib 获取 A 股日线数据完整教程

## 一、Qlib 项目简介

[Qlib](https://github.com/microsoft/qlib) 是微软开源的**面向 AI 的量化投资平台**，它：
- 提供完整的量化研究流水线：数据处理 → 模型训练 → 回测 → 分析
- 内置了自动化的数据下载工具，支持获取 A 股历史数据
- 数据格式规整，经过清洗，质量较高
- 支持日频、分钟频多种数据频率

## 二、Qlib 获取 A 股日线数据的两种方式

### 方式一：直接下载社区预处理好的数据包（推荐，最简单）

由于 Qlib 官方数据源暂时关闭，社区提供了已经预处理好的数据可以直接下载：

```bash
# 1. 创建数据目录
mkdir -p ~/.qlib/qlib_data/cn_data

# 2. 下载社区提供的完整数据包（约几百MB）
wget https://github.com/chenditc/investment_data/releases/latest/download/qlib_bin.tar.gz

# 3. 解压到 qlib 数据目录
tar -zxvf qlib_bin.tar.gz -C ~/.qlib/qlib_data/cn_data --strip-components=1

# 4. 清理压缩包
rm -f qlib_bin.tar.gz
```

> Windows 可以手动浏览器下载后解压到 `%USERPROFILE%\.qlib\qlib_data\cn_data` 目录

### 方式二：使用 Qlib 脚本自动下载（从 Yahoo Finance）

Qlib 提供脚本可以自动从 Yahoo Finance 获取 A 股数据：

```bash
# 方法 1: 使用模块方式
# 获取日线数据
python -m qlib.cli.data qlib_data --target_dir ~/.qlib/qlib_data/cn_data --region cn

# 获取1分钟线数据
python -m qlib.cli.data qlib_data --target_dir ~/.qlib/qlib_data/cn_data_1min --region cn --interval 1min
```

```bash
# 方法 2: 使用脚本方式（克隆了 Qlib 源码后）
cd qlib-master

# 获取日线数据
python scripts/get_data.py qlib_data --target_dir ~/.qlib/qlib_data/cn_data --region cn

# 获取1分钟线数据
python scripts/get_data.py qlib_data --target_dir ~/.qlib/qlib_data/cn_data_1min --region cn --interval 1min
```

## 三、Qlib 数据特点

| 特性 | 说明 |
|------|------|
| **覆盖范围** | 全部 A 股（沪深两市）|
| **时间跨度** | 从 2010 年至今 |
| **包含字段** | `$open`/`$high`/`$low`/`$close`/`$volume`/`$change`/`$factor`（复权因子）|
| **数据格式** | Qlib 自定义二进制格式，需要通过 Qlib API 读取 |
| **更新频率** | 支持每日自动增量更新 |

## 四、从 Qlib 读取数据并导出为 Kronos 可用的 CSV 格式

Kronos 需要的输入格式是 CSV，包含列：`timestamps`, `open`, `high`, `low`, `close`, `volume`, `amount`

以下是完整的导出示例代码：

```python
import qlib
import pandas as pd
from qlib.data import D
from qlib.constant import REG_CN

# ========== 1. 初始化 Qlib ==========
# Qlib 数据存储路径
mount_path = "~/.qlib/qlib_data/cn_data"  # 这里是日线数据
# 如果是 1 分钟数据: mount_path = "~/.qlib/qlib_data/cn_data_1min"

# 初始化 Qlib（中国市场）
qlib.init(mount_path=mount_path, region=REG_CN)

# ========== 2. 选择你要导出的股票和时间范围 ==========
# 股票代码格式：Qlib 使用 SH600977 表示上证 600977
stock_code = "SH600977"  # 绿城水务

# 时间范围
start_time = "2020-01-01"
end_time = "2025-12-31"

# ========== 3. 从 Qlib 读取数据 ==========
# 定义需要获取的字段
fields = ["$open", "$high", "$low", "$close", "$volume", "$factor"]

# 获取数据
df = D.features(
    instruments=[stock_code],
    fields=fields,
    start_time=start_time,
    end_time=end_time,
    freq="day"  # "day" 日线 / "1min" 分钟线
)

# 重置索引，将多级索引变为普通列
df = df.reset_index()
df.rename(columns={
    "$open": "open",
    "$high": "high",
    "$low": "low",
    "$close": "close",
    "$volume": "volume",
}, inplace=True)

# ========== 4. 计算复权价格（非常重要！）==========
# Qlib 保存的是不复权价格，需要乘以复权因子得到复权价格
for col in ["open", "high", "low", "close"]:
    df[col] = df[col] * df["$factor"]

# 估算成交额（Qlib 不直接提供 amount，可以用 收盘价 * 成交量 近似）
# 公式：amount = close * volume，单位一致
df["amount"] = df["close"] * df["volume"]

# ========== 5. 整理时间戳格式 ==========
df.rename(columns={"datetime": "timestamps"}, inplace=True)

# 只保留 Kronos 需要的列
kronos_df = df[["timestamps", "open", "high", "low", "close", "volume", "amount"]]

# ========== 6. 保存为 CSV ==========
output_file = f"{stock_code}_daily.csv"
kronos_df.to_csv(output_file, index=False)

print(f"✓ 数据已导出: {output_file}")
print(f"  共 {len(kronos_df)} 条日线记录")
print(f"  时间范围: {kronos_df['timestamps'].min()} 到 {kronos_df['timestamps'].max()}")
```

## 五、每日自动更新数据（可选）

Qlib 支持定时自动更新数据，可以设置 crontab 任务：

```bash
# 编辑 crontab
crontab -e

# 添加如下行，每周一到周五晚上 8 点更新
# 注意替换路径
0 20 * * 1-5 python /path/to/qlib/scripts/data_collector/yahoo/collector.py update_data_to_bin --qlib_data_1d_dir ~/.qlib/qlib_data/cn_data
```

手动更新命令：
```bash
python scripts/data_collector/yahoo/collector.py update_data_to_bin \
  --qlib_data_1d_dir ~/.qlib/qlib_data/cn_data \
  --trading_date 2025-01-01 \
  --end_date 2025-12-31
```

## 六、检查数据完整性

Qlib 提供数据健康检查脚本：

```bash
python qlib-master/scripts/check_data_health.py check_data \
  --qlib_dir ~/.qlib/qlib_data/cn_data
```

## 七、Qlib vs AKShare 对比

| 对比维度 | Qlib | AKShare |
|---------|------|---------|
| **数据来源** | Yahoo Finance | 东方财富 |
| **覆盖范围** | 全市场所有股票，可批量下载 | 单只股票逐个下载 |
| **使用方式** | 需要先下载完整数据集到本地，后续读取快 | 每次运行实时请求下载 |
| **数据格式** | Qlib 二进制（需要转换） | 直接返回 CSV 格式 |
| **更新方式** | 支持增量自动更新 | 需要重新下载 |
| **网络限制** | Yahoo Finance，当前环境可能能访问 | 东方财富，当前环境访问被拒绝 |
| **适合场景** | 批量获取多只股票长期数据，用于微调训练 | 快速获取单只股票最新数据 |

## 八、完整操作步骤总结

```bash
# 1. 安装 Qlib
conda activate kronos
pip install pyqlib

# 2. 下载数据（方式一：社区预编译包）
mkdir -p ~/.qlib/qlib_data/cn_data
wget https://github.com/chenditc/investment_data/releases/latest/download/qlib_bin.tar.gz
tar -zxvf qlib_bin.tar.gz -C ~/.qlib/qlib_data/cn_data --strip-components=1

# 或者方式二：脚本自动下载
cd qlib-master
python scripts/get_data.py qlib_data --target_dir ~/.qlib/qlib_data/cn_data --region cn

# 3. 使用上面的 Python 代码导出你需要的股票到 CSV
# 4. 直接在 Kronos 中使用导出的 CSV 进行预测
```

## 九、当前网络环境下的可行性分析

从之前 AKShare 下载失败的情况来看：
- AKShare 连接东方财富服务器被主动关闭，**当前网络环境无法使用**
- Qlib 从 Yahoo Finance 获取数据，如果 Yahoo Finance 在当前网络能访问，则可用
- 如果 Yahoo Finance 也无法访问，仍然可以使用**方式一：下载社区预编译好的数据包**（通过浏览器下载后手动放入对应目录）

如果下载成功，Qlib 提供的数据质量更高，更适合批量处理多只股票，非常适合 Kronos 微调训练使用。

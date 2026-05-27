# Qlib 数据源更新 + 预测完整使用手册

## 一、概述

由于 AKShare 访问东方财富遇到网络限制无法获取数据，我们已经切换到 **Qlib** 作为数据源。Qlib 是微软开源的量化投资平台，自带完整 A 股历史数据，可以完美替代 AKShare。

---

## 二、已有基础

✅ 目前已经完成：
1. Qlib 基础数据包已下载到 `~/.qlib/qlib_data/cn_data`（社区贡献，包含全市场 A 股 `2010-01-01` → `2020-09-25`）
2. 一站式整合脚本 `examples/prediction_qlib_daily.py` 创建完成，自动获取数据 → 预测 → 可视化
3. 单只股票更新脚本 `examples/update_single_stock_qlib.py` 创建完成

---

## 三、更新方式

### 方式一：更新单只股票（推荐，只预测几只股票使用）

当你只需要预测少数几只股票，不需要全市场数据做微调训练，用这个方法最简单。

#### 步骤 1：修改配置，指定要更新的股票

打开 `examples/update_single_stock_qlib.py`，修改开头的配置：

```python
# ========== 配置 ==========
# 你要更新的股票 (Qlib 格式: SH=上证, SZ=深证)
STOCK_CODE = "SH600977"  # 修改这里！示例: SH600000, SZ000001

# Qlib 数据目录，一般不需要改
QLIB_DATA_PATH = os.path.expanduser("~/.qlib/qlib_data/cn_data")

# 结束日期，默认获取到今天，不用改
END_DATE = None
```

#### 步骤 2：运行更新

```bash
cd examples
conda activate kronos
python update_single_stock_qlib.py
```

#### 输出示例

```
[INFO] qlib successfully initialized
开始更新单只股票: SH600977
目标结束日期: 2026-04-19
Yahoo Finance 代码: 600977.SS
正在从 Yahoo Finance 获取最新数据...
获取到 1234 条日线数据
✓ 已保存到: ./data/SH600977_daily.csv
  时间范围: 2010-01-01 00:00:00 → 2026-04-19 00:00:00
  总条数: 1234

现在可以直接运行 prediction_qlib_daily.py 进行预测了！
```

更新完成后，数据自动保存到 `examples/data/{STOCK_CODE}_daily.csv`，下一步直接预测。

---

### 方式二：全量更新（需要全市场数据做微调训练使用）

如果你需要全市场所有 A 股数据到最新日期，用于 Kronos 微调训练，使用这个方法。

#### 前置条件

需要网络环境能够访问 `push2his.eastmoney.com`（AKShare 使用的同一个 API），如果当前网络不行，需要**切换网络环境**（例如手机热点）。

#### 步骤 1：运行增量更新命令

```bash
cd qlib-master
conda activate kronos

# 增量更新：从 2020-09-26（基础数据截止日）更新到今天
python scripts/data_collector/yahoo/collector.py update_data_to_bin \
  --qlib_data_1d_dir ~/.qlib/qlib_data/cn_data \
  --trading_date 2020-09-26 \
  --end_date $(date +%Y-%m-%d)
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `--qlib_data_1d_dir` | Qlib 数据目录，保持默认 `~/.qlib/qlib_data/cn_data` |
| `--trading_date` | 开始更新日期，基础数据截止 `2020-09-25`，所以从 `2020-09-26` 开始 |
| `--end_date` | 结束日期，`$(date +%Y-%m-%d)` 自动获取今天 |

#### 预计耗时

- 更新约 5.5 年 × ~4000 只股票，需要 **数小时**，取决于网络速度
- 自动多进程并行下载，进度会显示在终端

---

## 四、更新完成后如何预测

### 方法一：一站式脚本（推荐，自动处理一切）

直接运行整合好的脚本，**自动获取数据 → 预测 → 可视化**：

```bash
cd examples
conda activate kronos
python prediction_qlib_daily.py
```

脚本默认预测 **SH600977（绿城水务）**，修改默认股票打开脚本编辑：

```python
# prediction_qlib_daily.py 开头修改
stock_code = "SH600977"  # -> 改成你要预测的股票
lookback = 400   # 历史窗口大小（不能超过 512）
pred_len = 60     # 预测未来多少天
```

### 方法二：用自己更新好的 CSV 数据预测

如果你已经用 `update_single_stock_qlib.py` 导出了 CSV，可以直接预测：

1. CSV 格式要求：
   ```
   timestamps,open,high,low,close,volume,amount
   2020-01-02,xxx.xx,xxx.xx,xxx.xx,xxx.xx,xxxxxx,xxxxxx
   ```

2. 修改 `prediction_qlib_daily.py` 中 `stock_code` 为你的股票，运行即可。

---

## 五、预测结果说明

预测完成后，会输出：

1. **预测结果表头**：在控制台打印前几行预测值
2. **对比图像**：
   - 自动弹出窗口显示对比图（真实值 vs 预测值）
   - 同时自动保存文件：`examples/data/{stock_code}_prediction.png`
   - 图像包含两个子图：
     - 上图：收盘价对比
     - 下图：成交量对比

---

## 六、常见问题

### Q: 更新单只股票失败/网络错误怎么办？
A: 当前网络环境限制了 Yahoo Finance/东方财富访问，需要切换网络（例如手机热点）后重试。

### Q: 我只需要测试流程，需要更新吗？
A: 不需要，基础数据截止 2020-09-25 已经足够做完整预测测试，直接运行 `prediction_qlib_daily.py` 就能出结果。

### Q: 预测很慢正常吗？
A: 正常。Kronos 是自回归预测，CPU 预测 60 步大约需要 20-30 秒，这是正常的。

### Q: Qlib 和 AKShare 数据格式一样吗？
A: 转换后格式完全一致，都是 `timestamps,open,high,low,close,volume,amount`，Kronos 可以直接使用。

### Q: 复权处理了吗？
A: 处理了。
- Qlib 原始数据：保存不复权价格 × 复权因子，脚本自动计算前复权
- Yahoo Finance 直接下载的就是复权后价格，因子设为 1

---

## 七、文件清单

| 文件 | 作用 |
|------|------|
| `examples/prediction_qlib_daily.py` | 一站式：Qlib 数据 → Kronos 预测 → 可视化 |
| `examples/update_single_stock_qlib.py` | 单独更新单只股票到最新日期，导出 CSV |
| `Qlib获取A股日线数据教程.md` | 下载和初始设置教程 |
| `Qlib数据源更新和预测使用手册.md` | 本手册 - 更新和预测使用说明 |

---

## 八、快速命令参考

```bash
# 1. 更新单只股票
cd examples
conda activate kronos
# 编辑 update_single_stock_qlib.py 修改股票代码
python update_single_stock_qlib.py

# 2. 预测
python prediction_qlib_daily.py

# 3. 全量增量更新（需要网络通畅）
cd qlib-master
python scripts/data_collector/yahoo/collector.py update_data_to_bin \
  --qlib_data_1d_dir ~/.qlib/qlib_data/cn_data \
  --trading_date 2020-09-26 \
  --end_date $(date +%Y-%m-%d)
```

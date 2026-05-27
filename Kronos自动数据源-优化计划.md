# Kronos 自动数据源 — 代码优化与测试计划

---

## 1. 背景与目标

### 1.1 当前问题

Kronos 的日线数据获取强依赖 Qlib 本地缓存。用户需要手动完成以下步骤才能使用：

1. 手动下载 Qlib `cn_data` 数据包（~1GB tar.gz）
2. 解压到 `~/.qlib/qlib_data/cn_data`
3. 手动配置 `finetune/config.py` 中的路径
4. 定期手动更新数据

这不仅繁琐，而且无法自动化每日增量更新。对于微调场景，用户还需手工确保 CSI300 成分股的数据完整性。

### 1.2 设计目标

```
核心目标：无需用户手动准备数据，一键完成预测/微调
          └── 所有数据由程序自动从公共数据源获取

子目标 1: 预测场景 — 用户输入股票代码，自动获取最新日线 → KronosPredictor
子目标 2: 微调场景 — 自动获取 CSI300 成分股历史数据 → pickle 训练集
子目标 3: 每日增量 — 只拉取上次获取后的新数据，不重复下载
```

### 1.3 技术选型对比结论

经过对三个数据源方案（justicePlutus data_provider、a-stock-data、Qlib）的深入调查，确定：

```
K线主数据源:  mootdx TCP 协议（通达信直连）
  ├── 零封禁风险（TCP 二进制协议，非 HTTP 爬虫）
  ├── 支持多周期（日/周/月/1分钟/5分钟/15分钟/30分钟/60分钟）
  ├── 无需限流（TCP 请求 50-100ms，不会被封）
  └── 仅需国内 IP（海外用 fallback）

补充数据源:  腾讯财经 API（PE/PB/市值/换手率/涨跌停价）
  └── HTTP GET，零封禁风险，补充 mootdx 缺少的估值字段

兜底数据源:  justicePlutus efinance/akshare（HTTP）
  └── 仅用于海外部署或 mootdx 不可用时的降级
```

---

## 2. 实现范围

### 2.1 新建模块

```
kronos_data_provider/          ← 新建目录
├── __init__.py                ← 导出 KronosDataManager
├── manager.py                 ← 统一入口类
├── backends/
│   ├── __init__.py
│   ├── mootdx_backend.py      ← mootdx TCP K线获取
│   ├── tencent_backend.py     ← 腾讯财经实时行情
│   └── http_fallback.py       ← HTTP 兜底（复用 justicePlutus 思路）
├── cache.py                   ← 本地 CSV 缓存管理（增量更新）
├── stock_list.py              ← 成分股列表管理（CSI300/自定义）
└── exceptions.py              ← 异常定义
```

### 2.2 修改已有模块

```
finetune/config.py
  └── 新增字段: data_cache_dir, stock_list_source
  └── 弃用字段: qlib_data_path（可选保留向后兼容）

finetune/qlib_data_preprocess.py
  └── 替换实现: 从 kronos_data_provider 读取 → 输出 pickle
  └── 文件名建议改为: data_preprocessor.py

examples/prediction_example.py
  └── 新增: prediction_auto.py（自动获取数据 + 预测）
```

### 2.3 不做修改

```
model/kronos.py               ← 不改
model/module.py               ← 不改
finetune/dataset.py           ← 不改（QlibDataset 只读 pickle）
finetune/train_predictor.py   ← 不改
finetune/train_tokenizer.py   ← 不改
finetune/train_*.bat/sh       ← 不改
finetune_csv/                 ← 不改
webui/                        ← 不改
tests/test_kronos_regression.py ← 不改
```

---

## 3. 详细实施步骤

### 阶段一：基础设施（核心模块）

#### Step 1.1: 创建 `kronos_data_provider/` 目录结构

新建包骨架，含 `__init__.py`、`exceptions.py`。

#### Step 1.2: 实现 mootdx 后端

**文件**: `kronos_data_provider/backends/mootdx_backend.py`

**函数**:
```python
def get_daily_kline(code: str, offset: int = 800) -> pd.DataFrame
```

**功能**:
- 使用 `mootdx.quotes.Quotes.factory(market='std')` 建立 TCP 连接
- 调用 `client.bars(symbol=code, category=4, offset=N)` 获取日 K 线
- 返回列: `['date', 'open', 'high', 'low', 'close', 'volume', 'amount']`
- 支持 code 归一化（自动添加 SH/SZ 前缀）

**验证方法**:
```python
df = get_daily_kline("600519")
assert len(df) > 0
assert list(df.columns) == ['date', 'open', 'high', 'low', 'close', 'volume', 'amount']
```

#### Step 1.3: 实现腾讯财经后端

**文件**: `kronos_data_provider/backends/tencent_backend.py`

**函数**:
```python
def get_realtime_quote(codes: list[str]) -> dict[str, dict]
```

**功能**:
- 调用 `qt.gtimg.cn/q=sh{code}` 获取实时行情
- 解析 `~` 分隔的 88 个字段
- 返回 PE/PB/市值/换手率/涨跌停价等补充数据

#### Step 1.4: 实现 HTTP 兜底后端

**文件**: `kronos_data_provider/backends/http_fallback.py`

**函数**:
```python
def get_daily_kline_http(code: str, start_date: str, end_date: str) -> pd.DataFrame
```

**功能**:
- 用 `requests` 直连东财 HTTP API（参考 a-stock-data 的 mootdx 之外的思路）
- 作为 mootdx TCP 不可用时的降级方案（如海外服务器）

#### Step 1.5: 实现统一入口类

**文件**: `kronos_data_provider/manager.py`

**类**:
```python
class KronosDataManager:
    def get_daily_data(self, code: str, start: str = None, end: str = None) -> pd.DataFrame
    def get_realtime_quote(self, code: str) -> dict
    def get_batch_daily_data(self, codes: list[str], start: str, end: str) -> dict[str, pd.DataFrame]
```

**策略**:
```
get_daily_data(code):
  1. check local CSV cache → 命中则返回
  2. mootdx TCP → 主路径
  3. HTTP fallback → 仅在 mootdx 失败时触发
  4. save to cache

get_batch_daily_data(codes):
  1. check cache for each code
  2. mootdx serial requests (TCP, no rate limiting)
  3. ~0.1s per stock → 300 stocks ≈ 30s
```

#### Step 1.6: 实现本地缓存模块

**文件**: `kronos_data_provider/cache.py`

**类**:
```python
class DataCache:
    def get(self, code: str) -> pd.DataFrame          # 读取本地
    def update(self, code: str, df: pd.DataFrame)       # 写入/追加
    def last_date(self, code: str) -> str               # 最近更新时间
    def needs_update(self, code: str) -> bool           # 是否需要增量
```

**数据结构**:
```
data_cache/                   ← 目录由 config 指定
├── 600519.csv                ← 每只股票一个文件
├── 000001.csv
└── ...

CSV 格式: date,open,high,low,close,volume,amount
```

#### Step 1.7: 实现成分股管理

**文件**: `kronos_data_provider/stock_list.py`

**函数**:
```python
def get_csi300() -> list[str]        # 内置最新 CSI300 成分股列表
def get_csi500() -> list[str]        # 内置最新 CSI500
def get_custom_list() -> list[str]   # 从 config 读取自定义列表
```

内置列表来源：手动整理一份最新 CSI300 成分股代码（约 300 只），直接从 AKShare 或东财 `datacenter-web` 获取。

---

### 阶段二：预测场景

#### Step 2.1: 新增 `prediction_auto.py`

**文件**: `examples/prediction_auto.py`

**流程**:
```
1. 用户输入股票代码（如 "600519"）
2. KronosDataManager.get_daily_data("600519") → 自动获取
3. 构建 x_df / x_timestamp / y_timestamp
4. KronosPredictor.predict(...) → 预测结果
5. 可视化输出
```

**与现有 `prediction_example.py` 的区别**:
- 不需要手动准备 CSV 数据文件
- 不需要手动设置 lookback（自动取 max_context 条最新数据）
- 支持命令行传参：`python prediction_auto.py --code 600519 --pred-len 30`

#### Step 2.2: 修改 `examples/data/README` 或新增说明

说明自动模式与传统模式的区别，以及如何切换。

---

### 阶段三：微调场景

#### Step 3.1: 实现批量数据获取

在 `KronosDataManager.get_batch_daily_data()` 基础上补充：
```
for code in constituent_list:
    df = self.get_daily_data(code, start="2010-01-01", end=today)
    save_to_cache(code, df)
```

#### Step 3.2: 重写预处理脚本

**文件**: `finetune/data_preprocessor.py`（新建，替代 `qlib_data_preprocess.py`）

**流程**:
```
1. 从 stock_list 获取成分股列表
2. 从 KronosDataManager 批量获取/更新数据
3. 按时间范围切分 train/val/test
4. 计算 vol / amt / time features
5. 输出 pickle 到 dataset_path
```

**与 Qlib 版本的关键区别**:
- 不依赖 Qlib：`import qlib` → 全部移除
- 数据来源：`KronosDataManager` 而非 `D.features()`
- 成分股：内置列表而非 Qlib instrument 解析

#### Step 3.3: 修改 `finetune/config.py`

**新增字段**:
```python
# 数据缓存目录（替换 qlib_data_path）
self.data_cache_dir = "./data_cache"

# 成分股来源: "csi300" / "csi500" / "custom"
self.stock_list_source = "csi300"

# 自定义股票列表（当 stock_list_source = "custom" 时使用）
self.custom_stock_list = []
```

**弃用字段**（保留但标记 deprecated）:
```python
self.qlib_data_path = None  # 不再需要，保留为空仅向后兼容
```

#### Step 3.4: 更新训练入口

修改 `finetune/train_predictor.py` 和 `train_tokenizer.py`：
- 检查 `data_preprocessor.py` 是否已运行
- 如果没有，自动运行
- 不需要用户手动预处理

---

### 阶段四：每日增量更新

#### Step 4.1: 实现增量更新逻辑

在 `DataCache` 中实现 `needs_update()`：
```python
def needs_update(self, code: str) -> bool:
    """检查是否需要增量更新（最新交易日 < 今日）"""
    last = self.last_date(code)
    if last is None:
        return True
    # 获取最新交易日（跳过周末节假日）
    latest_trading_day = self._latest_trading_day()
    return last < latest_trading_day
```

#### Step 4.2: 新增独立更新脚本

**文件**: `examples/update_data_cache.py`

```bash
python examples/update_data_cache.py
# 可选：--source csi300 --force
```

增量更新流程：
1. 遍历缓存中所有股票
2. 检查每只是否需要更新
3. 只拉取新数据，追加到 CSV
4. 可用于定时任务（cron / Task Scheduler）

---

## 4. 测试计划

### 4.1 单元测试

**文件**: `tests/test_kronos_data_provider.py`

| 测试 | 验证内容 |
|------|---------|
| `test_mootdx_single_stock` | mootdx 能获取单只股票日线 |
| `test_mootdx_multi_stock` | mootdx 能处理多只股票 |
| `test_tencent_realtime` | 腾讯财经返回 PE/PB/市值 |
| `test_cache_read_write` | 缓存写入后能正确读取 |
| `test_cache_incremental` | 增量追加不重复 |
| `test_cache_needs_update` | 最新交易日判断正确 |
| `test_code_normalization` | `SH600519` / `600519.SH` → `600519` |
| `test_http_fallback` | HTTP 降级能返回数据 |
| `test_stock_list_csi300` | CSI300 列表长度 > 200 |
| `test_manager_get_daily` | KronosDataManager 统一入口 |
| `test_manager_nonexistent_code` | 不存在的代码抛合理异常 |
| `test_cross_region` | 港股（`HK00700`）和美股（`AAPL`）处理 |

### 4.2 集成测试

| 测试 | 验证内容 |
|------|---------|
| 预测端到端 | `prediction_auto.py --code 600519` 能完整运行并输出 PNG |
| 预处理端到端 | `data_preprocessor.py` 能生成 pickle 且格式与 QlibDataset 兼容 |
| 增量更新 | 运行两次 `update_data_cache.py`，第二次应只拉增量 |

### 4.3 兼容性测试

| 测试 | 验证内容 |
|------|---------|
| QlibDataset 读新 pickle | `finetune/dataset.py` 能加载新预处理器输出的 pickle |
| 回归测试不变 | `test_kronos_regression.py` 仍然通过 |

### 4.4 边界情况

| 测试 | 验证内容 |
|------|---------|
| 退市股票 | 返回空 DataFrame 而非崩溃 |
| 新股（上市不足 1 年） | 数据不足时返回已有数据 |
| 非交易日 | cache 判断时跳过周末/节假日 |
| 网络中断 | mootdx 连接失败 → 自动走 HTTP fallback |
| 空缓存首次运行 | 自动创建缓存目录 |

### 4.5 测试执行顺序

```
1. 基础工具测试:
   test_code_normalization
   test_stock_list_csi300
   test_cache_*

2. 后端测试:
   test_mootdx_single_stock        (需要国内 IP)
   test_tencent_realtime
   test_http_fallback

3. Manager 测试:
   test_manager_get_daily
   test_manager_nonexistent_code

4. 集成测试:
   预测端到端
   预处理端到端
```

---

## 5. 向后兼容与迁移

### 5.1 旧配置兼容

`finetune/config.py` 保留 `qlib_data_path` 字段，但标记为 deprecated：
```python
self.qlib_data_path = None  # @deprecated 改用 data_cache_dir
```

如果用户有旧配置文件，程序检测到 `qlib_data_path` 非空时给出提示，但不出错。

### 5.2 旧数据兼容

已有的 `finetune/data/processed_datasets/*.pkl` 仍然可用，`QlibDataset` 照常读取。新的预处理器输出格式与旧的完全一致（都是 `{symbol: DataFrame}` 的 pickle 结构）。

### 5.3 依赖变更

| 操作 | 包 |
|------|-----|
| **新增** | `mootdx>=0.10` |
| **新增** | `requests`（通常已有） |
| **保留** | `pandas`、`numpy`、`torch` 等已有依赖 |
| **可选保留** | `pyqlib`、`akshare`、`efinance`、`yfinance`（不强制卸载） |

---

## 6. 文件变更总清单

### 新建文件

```
kronos_data_provider/
├── __init__.py
├── manager.py
├── cache.py
├── stock_list.py
├── exceptions.py
└── backends/
    ├── __init__.py
    ├── mootdx_backend.py
    ├── tencent_backend.py
    └── http_fallback.py

examples/
├── prediction_auto.py
└── update_data_cache.py

finetune/
└── data_preprocessor.py

tests/
└── test_kronos_data_provider.py
```

### 修改文件

```
finetune/config.py                   ← 新增字段，弃用 Qlib 路径
finetune/train_predictor.py          ← + 自动检查预处理
finetune/train_tokenizer.py          ← + 自动检查预处理
AGENTS.md                            ← 更新架构说明
```

### 标记为删除的文件

```
finetune/qlib_data_preprocess.py     ← 被 data_preprocessor.py 替代
```

---

## 7. 风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| mootdx 在海外服务器不稳定 | 中 | 高 | HTTP fallback 兜底 |
| 通达信 TCP 协议变更 | 低 | 高 | mootdx 库维护者跟进 |
| CSI300 成分股列表过期 | 中 | 低 | 手动更新 + 支持自定义列表 |
| 腾讯财经 API 格式变更 | 低 | 中 | 独立单元测试捕获 |
| 全新安装无历史数据 | 高 | 低 | 自动首次建库 + 进度条 |

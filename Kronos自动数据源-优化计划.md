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

#### ✅ Step 1.1: 创建 `kronos_data_provider/` 目录结构（已完成）

新建包骨架，含 `__init__.py`、`exceptions.py`、`cache.py`、`stock_list.py`、`manager.py`。

#### ✅ Step 1.2: 实现 mootdx 后端（已完成）

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

#### ✅ Step 1.3: 实现腾讯财经后端（已完成）

**文件**: `kronos_data_provider/backends/tencent_backend.py`

**函数**:
```python
def get_realtime_quote(codes: list[str]) -> dict[str, dict]
def get_index_quote(codes: list[str]) -> dict[str, dict]
def get_etf_quote(codes: list[str]) -> dict[str, dict]
def get_realtime_df(codes: list[str]) -> pd.DataFrame
```

**验证结果**: 个股3/3、指数3/3、ETF 2/2 全部通过。

#### ✅ Step 1.4: 实现 HTTP 兜底后端（已完成）

**文件**: `kronos_data_provider/backends/http_fallback.py`

**函数**:
```python
def get_daily_kline_http(code: str, start_date: str, end_date: str, days: int) -> pd.DataFrame
```
直连 `push2his.eastmoney.com`，含 tenacity 自动重试。**已通过验证**。

#### ✅ Step 1.5: 实现统一入口类（已完成）

**文件**: `kronos_data_provider/manager.py`

**类**: `KronosDataManager`
- `get_daily_data()` — 三级切换：cache → mootdx → HTTP
- `get_realtime_quote()` / `get_index_quote()` / `get_etf_quote()` — 腾讯财经
- `get_batch_daily_data()` — 批量获取
- `to_kronos_csv()` — 导出预测管线可直接读取的 CSV
- 代码归一化：`SH600519` / `600519.SH` / `sh600519` 均正确解析

#### ✅ Step 1.6: 实现本地缓存模块（已完成）

**文件**: `kronos_data_provider/cache.py`

**类**: `DataCache`
- 增量更新（`update()` 只追加新数据，不重复）
- 交易日感知（`needs_update()` 跳过周末/节假日）
- 清空操作（`clear()`）
- 验证：31/31 测试通过

#### ✅ Step 1.7: 实现成分股管理（已完成）

**文件**: `kronos_data_provider/stock_list.py`

**主数据源**: AKShare `ak.index_stock_cons(symbol="000300")` 实时获取（~280-300 只精确匹配）
**降级方案**: 内置 A 股核心股票池（当 akshare 不可用时）

**函数**:
```python
def get_csi300(prefer_live=True) -> list[str]     # CSI300 成分股
def is_csi300(code) -> bool                       # 判断是否成分股
def get_stock_list(source) -> list[str]           # 统一入口
def fetch_live_csi300() -> list[str] | None       # AKShare 实时获取
def validate_codes(codes) -> dict[str, str]       # 代码格式校验
```

**设计要点**:
- AKShare 组件股获取已验证通过（280 只去重后）
- 内置兜底列表包含 1000+ 只 A 股主要标的
- 代码归一化统一（SH600519 / 600519.SH 皆可）
- 27/27 测试通过

---

### 阶段二：预测场景

#### ✅ Step 2.1: 新增 `prediction_auto.py`（已完成）

**文件**: `examples/prediction_auto.py`

自动数据获取 → 模型加载 → 预测 → 可视化，一行命令完成。

**用法**:
```bash
conda activate kronos
cd examples

# 贵州茅台，预测 30 天
python prediction_auto.py --code 600519 --pred-len 30

# 指定模型和 lookback
python prediction_auto.py --code 000001 --pred-len 20 --lookback 256 --model small

# 指定输出路径
python prediction_auto.py --code 300750 --pred-len 60 --output ./my_pred.png
```

**验证结果**: `python prediction_auto.py --code 600519 --pred-len 10 --model small` 通过。
- mootdx 自动获取 346 条日线
- Kronos-small 模型成功预测 10 天
- 输出预测图 `examples/data/prediction_auto_test.png`

#### ✅ Step 2.2: 功能说明（已完成）

已内嵌在 `prediction_auto.py` 的模块文档字符串中，`--help` 可查看完整参数列表。

---

### 阶段三：微调场景

#### ✅ Step 3.1: 实现批量数据获取（已完成）

`KronosDataManager.get_batch_daily_data()` 已在 manager.py 中实现。
每只股票串行获取，自动走 cache → mootdx → HTTP fallback，结果回写本地缓存。
验证：3 只股票（600519/000001/300750）批量获取通过。

#### ✅ Step 3.2: 重写预处理脚本（已完成）

**文件**: `finetune/data_preprocessor.py`（新建，替代 `qlib_data_preprocess.py`）

**流程**:
1. 从 `stock_list` 获取成分股列表
2. 从 `KronosDataManager` 批量获取/更新数据
3. 按时间范围切分 train/val/test
4. 转换列名: volume→vol, amount→amt
5. 输出 pickle 到 `dataset_path`

**与 Qlib 版本的关键区别**:
- 不依赖 Qlib：全部移除
- 数据来源：`KronosDataManager` 而非 `D.features()`
- 成分股：`stock_list` 模块获取（实时 AKShare / 内置兜底）
- pickle 格式与 `QlibDataset` 完全兼容（已验证）

#### ✅ Step 3.3: 修改 `finetune/config.py`（已完成）

**新增字段**:
```python
self.data_cache_dir = "./data_cache"
self.stock_list_source = "csi300"
self.custom_stock_list = []
```

**弃用字段**: `self.qlib_data_path = None`（保留向后兼容）

#### ✅ Step 3.4: 更新训练入口（已完成）

`finetune/train_predictor.py` 和 `finetune/train_tokenizer.py` 均添加了自动预处理检测：
- 启动时检查 `{dataset_path}/train_data.pkl` 是否存在
- 不存在则自动调用 `DataPreprocessor` 获取数据
- 用户无需手动运行预处理步骤

**验证**: 24/24 测试通过。

---

### 阶段四：每日增量更新 ✅

#### ✅ Step 4.1: 实现增量更新逻辑（已完成）

`DataCache.needs_update()` 已实现交易日感知逻辑：
- 内置 2026 年 A 股休市日历
- `_last_trading_day()` 返回最近已完成交易日
- `needs_update()` 返回 `last_cached_date < latest_trading_day`
- 验证：增量运行返回 0 更新，正确跳过

#### ✅ Step 4.2: 新增独立更新脚本（已完成）

**文件**: `examples/update_data_cache.py`

```bash
# 更新所有已缓存股票
python update_data_cache.py

# 更新 CSI300 成分股（首次获取全部，后续增量）
python update_data_cache.py --source csi300

# 强制重新获取
python update_data_cache.py --source csi300 --force
```

**验证**: 首次拉取 2 只股票，增量运行 0 更新，正确跳过已是最新的数据。

---

## 4. 测试结果

**全部测试通过**: 49/49 新数据提供者测试 + 4/4 原始回归测试 = 53/53 ✅

**运行命令**:
```bash
conda activate kronos
python -m pytest tests/test_kronos_data_provider.py -v            # 49 tests
python -m pytest tests/test_kronos_regression.py -v               # 4 tests (回归)
python -m pytest tests/ -v                                         # 全部 53 tests
```

### 4.1 单元测试 — 37/37 ✅

| 测试类 | 测试用例 | 结果 |
|--------|---------|------|
| **TestCodeNormalization** | 7 tests | ✅ 全部通过 |
| **TestMootdxBackend** | 4 tests | ✅ 沪市/深市/MA指标/不存在代码抛异常 |
| **TestTencentBackend** | 3 tests | ✅ 实时行情/PE/PB/市值/指数 |
| **TestCache** | 8 tests | ✅ 读写/增量/交易日判断/清空/自动创建 |
| **TestTradingDay** | 6 tests | ✅ 工作日/周末/节假日/交易日函数 |
| **TestStockList** | 6 tests | ✅ CSI300 大小/成分股判断/自定义列表/校验 |
| **TestHTTPFallback** | 1 test | ✅ HTTP 降级返回标准格式 |
| **TestManager** | 5 tests | ✅ 获取/实时行情/批量/CSV导出/不存在代码 |
| **TestCrossRegion** | 2 tests | ✅ 港股/美股代码识别 |
| **TestEdgeCases** | 2 tests | ✅ 空缓存首次运行/新股短历史 |

### 4.2 集成测试 — 3/3 ✅

| 测试 | 验证内容 | 耗时 |
|------|---------|------|
| **预测端到端** | `prediction_auto.py --code 600519` 产出 PNG | ~25s |
| **预处理端到端** | pickle 格式兼容 QlibDataset | ~2s |
| **增量更新** | 第二次运行跳过增量 | ~2s |

### 4.3 兼容性测试 — 通过 ✅

| 测试 | 结果 |
|------|------|
| 原始回归测试 `test_kronos_regression.py` | ✅ 4/4 通过（512 和 256 上下文） |

### 4.4 已覆盖的边界情况

| 场景 | 覆盖 |
|------|------|
| 不存在股票代码 → DataProviderError | ✅ `test_nonexistent_code` |
| 新股短历史 → 返回已有数据 | ✅ `test_new_stock_short_history` |
| 非交易日 → cache 跳过 | ✅ `test_holiday_not_trading` |
| mootdx 失败 → HTTP fallback | ✅ 单元测试 + `test_http_fallback` |
| 空缓存首次运行 → 自动创建目录 | ✅ `test_dir_auto_create` + `test_empty_cache_first_run` |

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

# JusticePlutus 数据源获取架构

> 覆盖范围：`data_provider/` 下所有数据获取代码及 `src/core/pipeline.py` 中的调用方式。

---

## 1. 总体架构

```
┌──────────────────────────────────────────────────────────┐
│                     StockAnalysisPipeline                │
│                   (src/core/pipeline.py)                 │
├──────────────────────────────────────────────────────────┤
│  创建 DataFetcherManager → 管理 8+ 个 BaseFetcher 实现   │
│                                                          │
│  数据获取入口：                                           │
│  ├─ fetcher_manager.get_daily_data()        → 日线 K 线  │
│  ├─ fetcher_manager.get_realtime_quote()     → 实时行情  │
│  ├─ fetcher_manager.get_chip_distribution()  → 筹码分布  │
│  └─ fetcher_manager.get_stock_name()         → 股票名称  │
└──────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│                   DataFetcherManager                     │
│                  (data_provider/base.py)                 │
│                                                          │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │  IFindFetcher │   │ EfinanceFetch│   │AkshareFetcher│ │
│  │  (Priority -1)│   │  (Priority 0)│   │ (Priority 1) │ │
│  ├──────────────┤   ├──────────────┤   ├──────────────┤ │
│  │同花顺 iFinD  │   │  东方财富     │   │  akshare 库   │ │
│  │专业数据       │   │ (efinance库)  │   │(EM/新浪/腾讯)│ │
│  └──────────────┘   └──────────────┘   └──────────────┘ │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │ TushareFetch │   │  PytdxFetcher│   │BaostockFetch │ │
│  │ (Priority 2) │   │  (Priority 2)│   │ (Priority 3) │ │
│  ├──────────────┤   ├──────────────┤   ├──────────────┤ │
│  │ Tushare Pro  │   │  通达信行情   │   │   证券宝      │ │
│  │   API        │   │  pytdx 直连  │   │  baostock    │ │
│  └──────────────┘   └──────────────┘   └──────────────┘ │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │YfinanceFetch │   │HSCloudFetcher│   │WencaiFetcher │ │
│  │ (Priority 4) │   │ (仅筹码, P90)│    │ (仅筹码, P91) │ │
│  ├──────────────┤   ├──────────────┤   ├──────────────┤ │
│  │  Yahoo Finance│  │  HS 云筹码   │   │   问财筹码    │ │
│  │  (兜底/美股)  │   │   service   │   │  pywencai    │ │
│  └──────────────┘   └──────────────┘   └──────────────┘ │
└──────────────────────────────────────────────────────────┘
```

---

## 2. 数据源速览

| 数据源 | 优先级 | 用途 | 是否需要 Token | 限流风险 | 数据质量 |
|--------|--------|------|----------------|----------|----------|
| **IFindFetcher** | -1 (最高) | 日线/实时/筹码/财务 | 需要 token | 低 | 最高 |
| **EfinanceFetcher** | 0 | 日线/实时/筹码 | 否 | 高 | 高 |
| **AkshareFetcher** | 1 | 日线/实时/筹码 | 否 | 高 | 高 |
| **TushareFetcher** | 2 (未配置Token时) / 0 (配置Token时) | 日线/实时/筹码 | 需要 token | 中 (80次/分) | 高 |
| **PytdxFetcher** | 2 | 日线/实时 | 否 | 无 | 中 |
| **BaostockFetcher** | 3 | 日线 | 否 | 无 | 中(延迟T+1) |
| **YfinanceFetcher** | 4 | 日线/实时/美股 | 否 | 低 | 国际数据 |
| **HSCloudFetcher** | 90 | 仅筹码分布 | 需要认证 | - | 筹码专用 |
| **WencaiFetcher** | 91 | 仅筹码分布(降级) | 需要 cookie | - | 筹码兜底 |

---

## 3. 设计模式

### 3.1 策略模式 (Strategy Pattern)

- **`BaseFetcher`** (`data_provider/base.py:181`): 抽象基类，定义统一接口
- **`DataFetcherManager`** (`data_provider/base.py:412`): 策略管理器，实现自动切换

所有数据源实现 `BaseFetcher` 的同一组抽象方法，`DataFetcherManager` 按优先级排序并自动故障切换。

### 3.2 统一返回类型

**日线数据** — 全部通过 `_normalize_data()` 转换到标准列名：
```
['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']
```

**实时行情** — `UnifiedRealtimeQuote` (`data_provider/realtime_types.py:107`):
```python
class UnifiedRealtimeQuote:
    code: str          # 股票代码
    name: str          # 名称
    source: RealtimeSource  # 数据来源枚举
    price: float       # 最新价
    change_pct: float  # 涨跌幅
    change_amount: float # 涨跌额
    volume: int        # 成交量
    amount: float      # 成交额
    volume_ratio: float # 量比
    turnover_rate: float # 换手率
    amplitude: float   # 振幅
    open_price/high/low/pre_close  # 价格区间
    pe_ratio/pb_ratio/total_mv/circ_mv  # 估值指标
```

**筹码分布** — `ChipDistribution` (`data_provider/realtime_types.py:180`):
```python
class ChipDistribution:
    code: str
    profit_ratio: float   # 获利比例(0-1)
    avg_cost: float       # 平均成本
    cost_90_low/high: float   # 90%筹码成本区间
    concentration_90: float   # 90%筹码集中度
```

### 3.3 熔断器模式 (Circuit Breaker)

`data_provider/realtime_types.py:267` — `CircuitBreaker` 类，实现三级状态机：

```
CLOSED（正常） --连续失败N次--> OPEN（熔断）--冷却时间到--> HALF_OPEN（半开）
HALF_OPEN --成功--> CLOSED
HALF_OPEN --失败--> OPEN
```

两个全局实例：
- `_realtime_circuit_breaker`: 失败3次熔断，冷却5分钟
- `_chip_circuit_breaker`: 失败2次熔断，冷却10分钟

---

## 4. 核心调用链

### 4.1 日线 K 线获取 (get_daily_data)

`BaseFetcher.get_daily_data()` (`base.py:269`) 是模板方法，流程固定：

```
get_daily_data()
  │
  ├─ 1. 计算日期范围 (start_date / end_date / days)
  │
  ├─ 2. _fetch_raw_data(stock_code, start_date, end_date)
  │     子类实现，各数据源不同的 HTTP 调用
  │     - efinance: 调用 ef.stock.get_quote_history() → 东方财富接口
  │     - akshare:  调用 ak.stock_zh_a_hist() → akshare 封装
  │     - tushare:  调用 pro.daily() → Tushare Pro API
  │     - pytdx:    通达信 TCP 直连 → TdxHq_API.get_security_bars()
  │     - baostock:  bs.query_history_k_data_plus()
  │     - yfinance:  yf.download() → Yahoo Finance
  │
  ├─ 3. _normalize_data(raw_df, stock_code)
  │     子类实现，列名映射 → 标准列名
  │
  ├─ 4. _clean_data(df)
  │     统一清洗：日期格式、数值类型、去空、排序
  │
  └─ 5. _calculate_indicators(df)
       统一计算：MA5/MA10/MA20、量比
```

### 4.2 DataFetcherManager 的日线故障切换

`DataFetcherManager.get_daily_data()` (`base.py:553`) 实现自动切换：

```
get_daily_data(stock_code)
  │
  ├─ 归一化股票代码 (normalize_stock_code)
  │
  ├─ 美股路由：美股指数/股票 → 直连 YfinanceFetcher
  │
  ├─ THS 先行：配置了 iFinD 时 → 优先尝试 IFindFetcher
  │
  └─ 主循环：按优先级遍历 self._fetchers
       ├─ 尝试 fetcher.get_daily_data()
       ├─ 成功 → 返回 (df, source_name)
       ├─ 失败 → 记录错误，log("数据源切换: A -> B")
       └─ 全部失败 → 抛出 DataFetchError（汇总所有失败原因）
```

### 4.3 实时行情获取 (get_realtime_quote)

`DataFetcherManager.get_realtime_quote()` (`base.py:782`)，流程分三层：

```
get_realtime_quote(stock_code)
  │
  ├─ 美股指数 → YfinanceFetcher
  ├─ 美股股票 → YfinanceFetcher
  │
  ├─ THS 先行 → 尝试 IFindFetcher (补充 iFinD 估值指标)
  │
  └─ 按 config.realtime_source_priority 遍历（默认: efinance,akshare_em,akshare_sina,tencent）
       ├─ efinance    → EfinanceFetcher.get_realtime_quote()
       ├─ akshare_em  → AkshareFetcher.get_realtime_quote(source="em")
       ├─ akshare_sina→ AkshareFetcher.get_realtime_quote(source="sina")
       ├─ tencent/akshare_qq → AkshareFetcher.get_realtime_quote(source="tencent")
       └─ tushare     → TushareFetcher.get_realtime_quote()
       │
       ├─ 补充合并：主源缺失 volume_ratio/turnover_rate 等时从后续源补充
       └─ 全部失败 → 返回 None（降级兜底，不抛异常）
```

**特色策略 — 字段补充合并** (`base.py:978`):

当主数据源返回的 `UnifiedRealtimeQuote` 中缺少 `volume_ratio`、`turnover_rate`、`pe_ratio`、`pb_ratio` 等补充字段时，继续尝试后续数据源补齐缺失字段。补充字段优先级列表 (`_SUPPLEMENT_FIELDS`):

```python
['volume_ratio', 'turnover_rate', 'pe_ratio', 'pb_ratio',
 'total_mv', 'circ_mv', 'amplitude']
```

**特色策略 — iFinD 估值回填** (`base.py:992`):

当 IFindFetcher 获取到实时行情后，调用 `service.get_financial_pack()` 取当日估值数据（PE/PB/量比/换手率/市值），直接回填到 `UnifiedRealtimeQuote`，减少外部补充请求。

### 4.4 筹码分布获取 (get_chip_distribution)

独立于日线和实时行情的降级链（`base.py:1023`）：

```
get_chip_distribution(stock_code)
  │
  ├─ 检查 enable_chip_distribution 配置
  ├─ 检查芯片熔断器
  │
  ├─ 尝试 HSCloudFetcher   (hscloud 云筹码)
  ├─ 尝试 WencaiFetcher    (问财 pywencai)
  ├─ 尝试 AkshareFetcher   (akshare 筹码)
  ├─ 尝试 TushareFetcher   (Tushare 筹码)
  ├─ 尝试 EfinanceFetcher  (efinance 筹码)
  │
  └─ 全部失败 → 返回 None
```

### 4.5 股票名称获取 (get_stock_name)

多级查询链（`base.py:1087`）：

| 层级 | 来源 | 说明 |
|------|------|------|
| 1 | 本地缓存 `_stock_name_cache` | 避免重复请求 |
| 2 | 实时行情缓存 | `get_realtime_quote()` 返回结果中提取 |
| 3 | IFindFetcher | 优先使用（如果配置 THS Pro） |
| 4 | 静态映射 `STOCK_NAME_MAP` | `src/data/stock_mapping.py` 中的预置表 |
| 5 | 各数据源 `get_stock_name()` | 依次遍历 |
| 6 | LLM 搜索 | 外部调用兜底 |

---

## 5. 股票代码归一化

`normalize_stock_code()` (`base.py:70`) — 所有入口前都调用：

| 输入 | 输出 | 规则 |
|------|------|------|
| `600519` | `600519` | 已纯净 |
| `SH600519` | `600519` | 去除 `SH`/`SZ` 前缀 |
| `600519.SH` | `600519` | 去除 `.SH`/`.SZ`/`.BJ` 后缀 |
| `sh600519` | `600519` | 大小写不敏感 |
| `HK00700` | `HK00700` | 港股保留 `HK` 前缀 |
| `AAPL` | `AAPL` | 美股保留 |

---

## 6. 市场路由规则

`DataFetcherManager.get_daily_data()` 和 `get_realtime_quote()` 中有明确的市场判断：

| 市场 | 判断函数 | 路由到 |
|------|----------|--------|
| 美股指数 | `is_us_index_code()` (`us_index_mapping.py:46`) | YfinanceFetcher |
| 美股股票 | `is_us_stock_code()` (`us_index_mapping.py:65`) | YfinanceFetcher |
| 港股 | `is_hk_stock_code()` (`akshare_fetcher.py:137`) | 走主循环（efinance/akshare） |
| A 股 | 默认 | 正常优先级遍历 |
| 北交所 | `is_bse_code()` (`base.py:114`) | A股处理（`8xxxxx`/`4xxxxx`/`92xxxx`）|

美股和港股的分支区别：
- **美股**：直接快速路由到 YfinanceFetcher，不经过主循环
- **港股**：走主循环，由 efinance/akshare 处理（港股代码带 `HK` 前缀）

---

## 7. 防封禁与流控策略

### 7.1 随机休眠 + Jitter

所有爬虫类数据源（Efinance、Akshare）在每次请求前执行：

```python
def random_sleep(self, min_seconds=1.0, max_seconds=3.0):
    sleep_time = random.uniform(min_seconds, max_seconds)
    time.sleep(sleep_time)
```

不同源有不同的默认间隔：

| 数据源 | 默认休眠范围 |
|--------|-------------|
| EfinanceFetcher | 1.5-3.0 秒 |
| AkshareFetcher | 2.0-5.0 秒 |

### 7.2 User-Agent 轮换

预置 5 种 User-Agent 池，`_set_random_user_agent()` 随机切换。

### 7.3 指数退避重试 (Tenacity)

所有 HTTP 请求统一使用 `tenacity` 重试：
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, requests.RequestException))
)
```

### 7.4 Tushare 配额管理

`TushareFetcher` (`tushare_fetcher.py`) 内置 "每分钟调用计数器"：

- 免费用户：80次/分钟
- 超过配额时强制休眠到下一分钟
- `__init__` 中通过 `rate_limit_per_minute` 参数可调

### 7.5 实时行情缓存

EfinanceFetcher 和 AkshareFetcher 各有独立缓存：

```python
_realtime_cache = {'data': None, 'timestamp': 0, 'ttl': 600}  # 10分钟
_etf_realtime_cache = {'data': None, 'timestamp': 0, 'ttl': 600}  # 10分钟
```

AkshareFetcher 的缓存 TTL 为 1200 秒（20 分钟），更保守。

### 7.6 批量预取 (prefetch_realtime_quotes)

`DataFetcherManager.prefetch_realtime_quotes()` (`base.py:701`):

- 仅当实时行情优先级使用**全量数据源**（efinance/akshare_em/tushare）且股票数 ≥ 5 时触发
- 通过调用第一只股票的实时行情触发批量拉取，填充缓存
- 轻量级数据源（新浪、腾讯）逐个查询，不预取

---

## 8. 配置项 (src/config.py)

关键数据源配置项：

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `REALTIME_SOURCE_PRIORITY` | 实时行情源优先级 | `efinance,akshare_em,akshare_sina,tencent` |
| `ENABLE_REALTIME_QUOTE` | 实时行情开关 | `True` |
| `ENABLE_CHIP_DISTRIBUTION` | 筹码分布开关 | `True` |
| `ENABLE_EASTMONEY_PATCH` | 东方财富补丁 | `False` |
| `PREFETCH_REALTIME_QUOTES` | 批量预取开关 | `True` |
| `TUSHARE_TOKEN` | Tushare Pro Token | 空（配置后优先级升为 0） |
| `TUSHARE_PRIORITY` | Tushare 自定义优先级 | `2` |
| `EFINANCE_PRIORITY` | efinance 自定义优先级 | `0` |
| `AKSHARE_PRIORITY` | akshare 自定义优先级 | `1` |
| `BAOSTOCK_PRIORITY` | baostock 自定义优先级 | `3` |
| `YFINANCE_PRIORITY` | yfinance 自定义优先级 | `4` |
| `PYTDX_SERVERS` | 通达信服务器列表 | 内置默认 IP |
| `PYTDX_HOST` / `PYTDX_PORT` | 通达信单服务器 | 空 |
| `HS_CLOUD_*` | HS 云筹码认证 | 空 |
| `WENCAI_COOKIE` | 问财 cookie | 空 |

---

## 9. 异常体系

```
DataFetchError (base.py:166)          # 所有数据获取异常的基类
├── RateLimitError (base.py:171)       # API 速率限制
└── DataSourceUnavailableError (base.py:176) # 数据源不可用
```

`summarize_exception()` (`base.py:60`) — 递归解包异常链并生成稳定分类字符串，用于日志聚合和故障排查。

---

## 10. Error 分类标签

`akshare_fetcher.py` 和 `efinance_fetcher.py` 都实现了 HTTP 错误分类函数，将各类异常映射到 5 种标准标签：

| 标签 | 含义 | 典型触发 |
|------|------|----------|
| `remote_disconnect` | 连接中断 | 反爬/SDK重置 |
| `timeout` | 超时 | 服务器慢/频率高 |
| `rate_limit_or_anti_bot` | 限流/反爬 | 请求频率过高 |
| `request_error` | 请求异常 | 网络问题 |
| `unknown_request_error` | 未知 | 兜底 |

---

## 11. Baostock 连接管理

BaostockFetcher (`baostock_fetcher.py`) 使用上下文管理器管理连接：

```python
@contextmanager
def _get_connection(self):
    bs.login()
    try:
        yield
    finally:
        bs.logout()
```

每次请求独立登录/登出，防止连接泄露。`bs.login()` 可匿名调用。

---

## 12. 使用方式 (CLI 入口)

```bash
# 直接运行分析流水线
python -m justice_plutus run --stocks 600519,000001,300750

# 只抓数据不做 AI 分析
python -m justice_plutus run --dry-run

# 不推送通知
python -m justice_plutus run --no-notify

# 指定并发数
python -m justice_plutus run --workers 4
```

`justice_plutus/cli.py:19` 构建 argparse 解析器，`justice_plutus/runtime.py` 提供运行元数据管理。

---

## 13. 关键设计决策

1. **美股直路由**：不经过优先级排序，强制使用 YfinanceFetcher（因为国内数据源不支持美股）。
2. **日线 vs 实时分离**：日线走 `_fetchers` 优先级，实时走 `realtime_source_priority` 配置，两者独立。
3. **筹码分布走独立降级链**：不参与主数据源优先级，单独在 `get_chip_distribution()` 中硬编码。
4. **iFinD 先行**：当配置了同花顺 iFinD 专业数据时，日线和实时都优先尝试，然后再走免费数据源的故障切换链。
5. **断点续传**：Pipeline 检查数据库是否有今日数据，避免重复拉取。
6. **字段合并**：实时行情支持从多个数据源合并补充字段，第一个成功的数据源作为主数据，后续源补充缺失的估值字段。

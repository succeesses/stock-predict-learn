# Kronos 后续优化方向

> 基于当前代码状态（自动数据源、预测、预处理、增量更新已完成）的进一步优化思考。

---

## 一、市场覆盖扩展

### 1.1 港股支持

**现状**: `mootdx_backend` 对港股代码抛出 `DataSourceUnavailableError`，`http_fallback` 同样不支持。

**方案**:
- 在 `manager.py` 的 `get_daily_data()` 中添加港股路由分支
- 检测到 `HK00700` 格式时，使用 yfinance 或 efinance 的港股接口获取
- efinance 天然支持港股（efinance 的 `stock.get_quote_history` 可传港股代码）

**优先级**: 高 — 港股是 A 股之外最重要的中国市场

### 1.2 美股支持

**现状**: 同样被 mootdx 拒绝。

**方案**:
- 在 `manager.py` 中添加美股路由分支（检测纯字母代码如 AAPL）
- 后端: yfinance（已在 `update_single_stock_qlib.py` 中使用 yahooquery，可与 yfinance 统一）
- 注意: yfinance 的复权价格处理（与 A 股不同，Yahoo 返回调整后价格）

**优先级**: 中 — 部分用户有美股需求

---

## 二、多周期 K 线支持

### 2.1 分钟级 K 线

**现状**: `mootdx_backend` 只支持日线（`category=4`）。但 Kronos 模型的原始论文使用 **5 分钟 K 线**。

**方案**:
- mootdx 的 `bars()` 函数原生支持多周期
- 日线: `category=4`（已实现）
- 5 分钟: `category=8`（需要新增）
- 15 分钟: `category=9`
- 30 分钟: `category=10`
- 60 分钟: `category=11`
- 在 `mootdx_backend.py` 中添加 `get_kline(code, freq="daily", offset=800)` 参数
- 缓存文件也要区分周期（如 `600519_5min.csv` vs `600519_daily.csv`）

**优先级**: 高 — Kronos 本身就是为多周期设计的

### 2.2 分钟级数据在预测场景的应用

- `prediction_auto.py` 增加 `--freq` 参数（daily/5min/15min/...）
- 自动适配 max_context: 日线 512 条 ≈ 2 年，5 分钟 512 条 ≈ 2 天
- 数据缓存区分周期存储

---

## 三、QLib 完全替代

### 3.1 重写回测模块

**现状**: `finetune/qlib_test.py` 仍依赖 Qlib 的 `qlib.data.D` 和 `qlib.contrib.strategy`。

**方案**:
- 可选项：仍然保留 Qlib 作为可选依赖（当用户需要精确回测时）
- 替换: 用 `KronosDataManager` + 简单的 top-K 策略自实现回测
- 从 `finetune/config.py` 读取预测信号，直接计算收益率/夏普比/最大回撤

**优先级**: 低（如果用户不跑回测就不需要改）

### 3.2 移除 pyqlib 依赖

**现状**: `requirements.txt` 中没有 pyqlib（用户手动安装），但 `qlib_data_preprocess.py` 依赖它。

**方案**:
- 完全弃用 `qlib_data_preprocess.py`，用 `data_preprocessor.py` 替代
- 更新 `train_all_macos.sh` 和 Windows 启动脚本
- `AGENTS.md` 和 `CLAUDE.md` 中更新说明

**优先级**: 中（清理遗留）

---

## 四、性能与可靠性

### 4.1 批量获取并行化

**现状**: `get_batch_daily_data()` 串行获取每只股票。300 只股票 × 0.1s = 30s，但如果走 HTTP fallback 就慢得多。

**方案**:
- 使用 `concurrent.futures.ThreadPoolExecutor` 实现并行获取
- mootdx TCP 不支持并行（同一连接），需要为每个线程创建独立连接
- 并行数不能太大，建议 `max_workers=4`
- 在 `manager.py` 中添加 `get_batch_daily_data_parallel()`

### 4.2 mootdx 连接池

**现状**: 每次 `get_daily_kline()` 都重新创建 `Quotes.factory()` 连接。

**方案**:
- 在 `mootdx_backend.py` 中使用模块级单例 `_client = None`
- 延迟初始化并复用连接
- 连接断开时自动重连

### 4.3 HTTP fallback 增强

**现状**: 东方财富 API 仅有一种获取方式。

**方案**:
- 增加更多 fallback 端点：
  - 腾讯财经 K 线（`proxy.finance.qq.com`）
  - 新浪财经 K 线（`vip.stock.finance.sina.com.cn`）
  - AKShare（作为第三级备用，pip install akshare）
- 实现多级切换：mootdx → 东财 HTTP → 腾讯 → 新浪 → AKShare

### 4.4 模型文件本地缓存

**现状**: `Kronos.from_pretrained()` 每次从 Hugging Face Hub 下载，耗时且需要网络。

**方案**:
- huggingface_hub 默认会缓存到 `~/.cache/huggingface/hub/`
- 但首次下载仍然慢（base 模型 102M）
- 可选：在 `prediction_auto.py` 中显示下载进度
- 添加 `--local-model-dir` 参数让用户指定本地存好的模型路径

---

## 五、用户体验与自动化

### 5.1 CLI 统一入口

**现状**: 4 个独立脚本，参数风格不统一。

**方案**: 在项目根目录创建统一的命令行入口：

```bash
kronos --help

kronos predict --code 600519 --pred-len 30
kronos update-cache --source csi300
kronos preprocess
kronos train --model predictor --epochs 30
kronos backtest --start 2025-01-01 --end 2026-06-01
```

可以使用 `argparse` 子命令或 `click` / `typer` 库。

### 5.2 WebUI 集成自动数据源

**现状**: `webui/app.py` 使用 Flask，但需要手动准备 CSV 或使用模拟数据。

**方案**: 将 `KronosDataManager` 注入 WebUI：
- 用户输入股票代码 → 自动获取日线 → Kronos 预测 → 显示图表
- 参考 webui/app.py 第 30 行的 `MODEL_AVAILABLE` 处理逻辑

### 5.3 定时任务一键配置

**现状**: 用户需要手动设置 cron / Task Scheduler。

**方案**: 添加配置脚本：

```bash
# Linux / macOS
python scripts/setup_cron.py --task "python update_data_cache.py --source csi300" --time "17:00"

# Windows
python scripts/setup_scheduler.py --task "python update_data_cache.py" --time "17:00"
```

### 5.4 启动优化（environment.yml）

**现状**: 需要手动 `conda create` + `pip install` 多个依赖。

**方案**: 提供 `environment.yml`：

```yaml
name: kronos
channels:
  - pytorch
  - conda-forge
  - defaults
dependencies:
  - python=3.10
  - pytorch>=2.0.0
  - pip
  - pip:
    - pandas>=2.2.0
    - matplotlib>=3.9.0
    - huggingface_hub>=0.33.0
    - safetensors
    - mootdx>=0.10
    - requests
    - tenacity
    - akshare  # 可选，用于实时成分股
```

---

## 六、数据质量与监控

### 6.1 数据一致性校验

**现状**: 没有机制检查从 mootdx 获取的数据是否合理。

**方案**:
- 在 `mootdx_backend.py` 中添加合理性检查：
  - 收盘价 > 0
  - 最高价 >= 最低价
  - 最高价 >= 收盘价 >= 最低价
  - 当天涨跌幅不超过 ±30%（正常 A 股 ±10%，科创/创业 ±20%）
  - 突然的跳空（如价格翻倍）触发警告

### 6.2 缓存健康检查

**现状**: `DataCache.get()` 直接读取 CSV，没有校验。

**方案**:
- 添加 `health_check()` 方法：
  - 检查 CSV 文件格式是否正确
  - 检查日期是否连续（跳过周末/节假日）
  - 检查是否有过长的时间缺口
  - 报告每只股票的缓存状态（最新日期 / 缺失天数）

### 6.3 成分股自动刷新

**现状**: `fetch_live_csi300()` 手动调用，只在启动时获取一次。

**方案**:
- `get_stock_list()` 添加 TTL 缓存（如 24 小时内不重复获取）
- 后台线程定期刷新成分股（csi300 每半年调整一次成分）
- 缓存过期时自动重新获取

---

## 七、代码工程化

### 7.1 API 文档

**现状**: 仅有内联注释和 `AGENTS.md`。

**方案**:
- 为 `kronos_data_provider` 编写 Sphinx / MkDocs 文档
- 主要类和函数的 `__doc__` 完善

### 7.2 CI/CD

**现状**: 无自动化测试流水线。

**方案**:
- GitHub Actions workflow:
  - `python -m pytest tests/`
  - 仅运行不需要网络/国内 IP 的测试（cache, normalization, stock_list 等）
  - mootdx/腾讯测试标记为 `@pytest.mark.network`

### 7.3 pre-commit hooks

**现状**: 无代码格式化/检查。

**方案**:
- `.pre-commit-config.yaml`:
  - `black`（代码格式化）
  - `ruff`（lint）
  - 自动移除 `print()` 调试语句

### 7.4 模块化拆分

**现状**: `kronos_data_provider/` 是一个包，但与其他模块耦合紧。

**方案**:
- 将 `kronos_data_provider` 独立为可 pip install 的包
- 发布到 PyPI（如果合适）
- 与 justicePlutus 的 `data_provider` 保持正交

---

## 八、Roadmap 优先级

| 优先级 | 方向 | 预计工作量 |
|--------|------|-----------|
| **P0** | 美股/港股支持 | 1-2 天 |
| **P0** | 多周期 K 线（5 分钟） | 1 天 |
| **P1** | mootdx 连接池复用 | 0.5 天 |
| **P1** | CLI 统一入口 | 2 天 |
| **P1** | WebUI 集成 | 1 天 |
| **P2** | 批量获取并行化 | 1 天 |
| **P2** | HTTP fallback 增强（腾讯/新浪） | 1 天 |
| **P2** | 数据一致性校验 | 1 天 |
| **P3** | 缓存健康检查 | 0.5 天 |
| **P3** | CI/CD + pre-commit | 0.5 天 |
| **P3** | 环境一键安装（environment.yml） | 0.5 天 |
| **P4** | 定时任务配置脚本 | 0.5 天 |
| **P4** | 模块独立发布 | 2 天 |

# Kronos 金融时序预测 Skill

Kronos 是专为金融 K 线数据设计的自回归基础模型，基于全球超过 45 家交易所数据预训练。支持微调适配A股市场，提供命令行和WebUI两种使用方式。

## 📋 技能概述

| 属性 | 值 |
|------|-----|
| **模型名称** | Kronos (mini/small/base) |
| **参数量** | 4.1M / 24.7M / 102.3M |
| **上下文长度** | 512 (small/base), 2048 (mini) |
| **支持数据** | 日线 / 分钟线 OHLCV |
| **预测模式** | 纯未来预测 / 历史验证回测 |
| **加速支持** | NVIDIA CUDA / Apple MPS / CPU |
| **支持系统** | macOS (Apple Silicon) / Linux / Windows |

---

## ⚠️ 重要运行环境说明

**所有 Python 脚本必须在 Conda 环境中运行**。使用前必须执行：

```bash
# 激活 kronos 环境
conda activate kronos

# 验证环境是否正确 (应显示 Python 3.10.x)
python --version
```

**环境要求识别点**:
- ✅ **环境名称**: `kronos` (可通过 `setup_macos.sh` 自动创建)
- ✅ **Python 版本**: 3.10.x
- ✅ **必须激活**: 所有脚本运行前必须先执行 `conda activate kronos`
- ✅ **工作目录**: 根据不同技能切换到 `examples/`、`finetune/` 或 `webui/` 目录

如果没有该环境，请先运行 `./setup_macos.sh` (macOS) 或参考文档的环境安装步骤。

---

## 🎯 核心技能使用清单

以下是 Kronos Skill 支持的所有核心操作，按使用频率排序：

| 技能编号 | 技能名称 | 功能说明 | 快速命令 |
|---------|---------|---------|---------|
| **Skill 1** | **从 Qlib 本地数据库导出股票数据** | 将 Qlib 本地缓存的单只股票日线数据导出为 CSV 格式 | `cd examples && python get_stock_data_from_qlib.py` |
| **Skill 2** | **预测股票未来走势（默认预训练模型）** | 从 Hugging Face 下载官方预训练模型，无需微调，开箱即用 | `cd examples && python predict_future_qlib.py` |
| **Skill 3** | **预测股票未来走势（微调后模型）** | 使用本地微调好的模型，A 股预测准确率更高 | `cd examples && python predict_future_finetuned.py` |
| **Skill 4** | **历史回测验证（预训练模型）** | 使用官方预训练模型，在历史区间与真实值对比 | `cd examples && python prediction_qlib_daily.py` |
| **Skill 5** | **历史回测验证（微调后模型）** | ✅ **新增** 使用本地微调模型 + 本地 CSV 回测 | `cd examples && python prediction_finetuned_backtest.py` |
| **Skill 6** | **全市场回测评估** | 在测试集上批量回测，输出累计收益曲线和绩效指标 | `cd finetune && python qlib_test.py --device auto` |
| **Skill 7** | **微调分词器** | 使用 A 股本地数据重新训练 tokenizer，适配本地数据分布 | `cd finetune && python train_tokenizer_single_gpu.py` |
| **Skill 8** | **微调预测器** | 使用微调后的 tokenizer，训练自回归预测模型 | `cd finetune && python train_predictor_single_gpu.py` |
| **Skill 9** | **下载 Qlib A 股训练数据** | 下载 `cn_data` 全量 A 股日线数据库（浏览器手动下载优先，wget 备选） | 见下方详细说明 |
| **Skill 10** | **WebUI 可视化操作** | 网页界面交互式上传数据、调整参数、查看预测结果 | `cd webui && ./start.sh` |

---

### 📌 Skill 1: 从 Qlib 本地数据库导出股票数据

**用途**: 将 Qlib 缓存的 A 股日线数据导出为 Kronos 兼容的 CSV 格式

**操作步骤**:
```bash
cd examples
conda activate kronos

# 编辑脚本修改股票代码
# nano get_stock_data_from_qlib.py
# 修改 stock_code = "SH600519"  # 贵州茅台

python get_stock_data_from_qlib.py
```

**输出**: `examples/data/SH600519_daily.csv`
- 包含列: `timestamps, open, high, low, close, volume, amount, $factor`

---

### 📌 Skill 2: 预测股票未来走势（默认预训练模型）

**适用场景**: 快速验证，无需本地微调，直接使用 Hugging Face 官方预训练模型

**特点**:
- ✅ 无需微调，开箱即用
- ✅ 首次运行 **自动下载** 模型到本地缓存（无需手动操作）
- ✅ 支持三种模型大小: mini (4.1M) / small (24.7M) / base (102.3M)
- ✅ 支持 Qlib 数据库 和 本地 CSV 两种数据源

**操作步骤**:
```bash
cd examples
conda activate kronos

# 编辑 predict_future_qlib.py 配置参数:
# - stock_code = "SH600519"           # 股票代码
# - USE_LOCAL_CSV = False              # True=本地CSV, False=从Qlib获取
# - MODEL_NAME = "NeoQuasar/Kronos-small"  # 选择模型大小
# - lookback = 400                     # 历史回看窗口
# - pred_len = 60                      # 预测未来天数

python predict_future_qlib.py
```

**输出**:
- 图像: `examples/data/{stock_code}_future_prediction.png`
- 数据: `examples/data/{stock_code}_future_prediction.csv`

---

### 📌 Skill 3: 预测股票未来走势（微调后模型）

**适用场景**: 追求更高的 A 股预测准确率，已完成微调训练

**特点**:
- ✅ 使用本地微调后的分词器和预测器
- ✅ 针对 A 股数据分布优化，准确率更高
- ✅ 支持 Qlib 数据库 和 本地 CSV 两种数据源

**前置依赖**: 已运行 Skill 6 (微调分词器) 和 Skill 7 (微调预测器)

**操作步骤**:
```bash
cd examples
conda activate kronos

# 编辑 predict_future_finetuned.py 配置参数:
# - stock_code = "SH600519"      # 股票代码
# - USE_LOCAL_CSV = True          # 使用本地 CSV 数据
# - lookback = 400                # 历史回看窗口
# - pred_len = 60                 # 预测未来天数

python predict_future_finetuned.py
```

**输出**:
- 图像: `examples/data/{stock_code}_future_prediction_finetuned.png`
- 数据: `examples/data/{stock_code}_future_prediction_finetuned.csv`

---

### 📌 Skill 4: 历史回测验证（预训练模型 + Qlib）

**用途**: 使用官方预训练模型，在历史区间运行预测，与真实值对比

**操作步骤**:
```bash
cd examples
conda activate kronos

# 编辑 prediction_qlib_daily.py 设置回测区间
python prediction_qlib_daily.py
```

**输出**: 历史区间的预测值与真实值对比图，包含误差统计

---

### 📌 Skill 5: 历史回测验证（微调后模型 + 本地 CSV）✅ **新增**

**适用场景**: 验证微调后模型的准确性，**不依赖 Qlib**，只使用本地 CSV 数据

**特点**:
- ✅ 使用本地微调后的模型（准确率更高）
- ✅ 只读取本地 CSV 文件，不需要 Qlib 数据目录
- ✅ 支持 CSV 中的 `$factor` 列，显示不复权价格
- ✅ 输出完整误差指标（MAE/MSE/RMSE/MAPE/方向准确率）

**前置依赖**: 已完成微调，且已导出股票 CSV 数据到 `examples/data/` 目录

**操作步骤**:
```bash
cd examples
conda activate kronos

# 编辑 prediction_finetuned_backtest.py 配置参数:
# - stock_code = "SH600519"      # 股票代码（对应 CSV 文件名）
# - lookback = 400                # 历史回看窗口
# - pred_len = 60                 # 预测未来天数
# - backtest_offset = 100         # 回测起点（从数据末尾往前推多少天）

python prediction_finetuned_backtest.py
```

**参数说明**:
- `backtest_offset = 100`: 回测从「倒数第 100 天」开始
  - 用 **倒数第 500 天 → 倒数第 100 天**作为历史数据
  - 预测 **倒数第 100 天 → 倒数第 40 天**的价格
  - 与真实值对比计算误差

**输出**:
- 图像: `examples/data/{stock_code}_backtest_finetuned.png`
  - 子图 1: 前复权收盘价（历史 + 预测 vs 真实值）
  - 子图 2: 成交量
  - 子图 3: 不复权收盘价（如果 CSV 有 `$factor`）
- 数据: `examples/data/{stock_code}_backtest_finetuned.csv`
- 控制台: MAE/MSE/RMSE/MAPE/方向准确率 5 项误差指标

---

### 📌 Skill 6: 全市场回测评估

**用途**: 在指定股票池的全市场测试集上批量回测，输出专业绩效指标

**股票池配置** (在 `finetune/config.py` 中修改):
```python
self.instrument = 'csi300'  # 股票池: csi300 / csi800 / csi1000
```

**操作步骤**:
```bash
cd finetune
conda activate kronos

# --device auto: 自动检测 MPS/CUDA/CPU
python qlib_test.py --device auto
```

**输出**:
- 累计收益对比图 (vs 对应股票池基准指数)
- 夏普比率、年化收益、最大回撤等绩效指标
- 保存路径: `finetune/outputs/backtest_results/`

---

### 📌 Skill 7 & 8: 利用本地数据库微调模型

**完整微调流水线** (推荐使用一键脚本):
```bash
cd finetune
chmod +x train_all_macos.sh
./train_all_macos.sh
```

**分步手动微调**:
```bash
cd finetune
conda activate kronos

# 步骤 1: 数据预处理（将 Qlib 数据转换为训练格式）
python qlib_data_preprocess.py
# 输出: data/processed_datasets/{train,val,test}_data.pkl

# 步骤 2: 微调分词器
python train_tokenizer_single_gpu.py
# 输出: outputs/models/finetune_tokenizer_demo/checkpoints/best_model/

# 步骤 3: 微调预测器
python train_predictor_single_gpu.py
# 输出: outputs/models/finetune_predictor_demo/checkpoints/best_model/
```

---

### 📌 Skill 9: 下载 Qlib A 股训练数据（`cn_data`）

**用途**: 下载全量 A 股日线数据库，用于微调和回测
**推荐方式**: 浏览器手动下载（速度远快于 wget 命令行）
**数据大小**: 约 300MB（压缩包）

---

#### 方式 A: 浏览器手动下载（✅ 推荐，速度快）

1. 打开 GitHub 发布页面：https://github.com/chenditc/investment_data/releases/latest
2. 找到并下载 `qlib_bin.tar.gz` 文件
3. 执行以下命令解压到 Qlib 数据目录：

```bash
# macOS/Linux:
mkdir -p ~/.qlib/qlib_data
# 将下载的 qlib_bin.tar.gz 移动到 ~/Downloads/ 后执行：
mv ~/Downloads/qlib_bin.tar.gz ~/.qlib/qlib_data/
cd ~/.qlib/qlib_data
tar -zxvf qlib_bin.tar.gz -C cn_data --strip-components=1
```

**Windows**（PowerShell）：
```powershell
mkdir -p C:\Users\用户名\.qlib\qlib_data
# 将下载的文件移动到该目录，然后解压
tar -zxvf qlib_bin.tar.gz -C cn_data --strip-components=1
```

---

#### 方式 B: wget 命令行下载（适合服务器，较慢）

```bash
mkdir -p ~/.qlib/qlib_data
cd ~/.qlib/qlib_data
wget https://github.com/chenditc/investment_data/releases/latest/download/qlib_bin.tar.gz
mkdir -p cn_data
LC_ALL=C tar -zxvf qlib_bin.tar.gz -C cn_data --strip-components=1
```

---

#### 验证数据：
```bash
ls -la ~/.qlib/qlib_data/cn_data/
# 应该能看到很多 .bin 文件（按股票代码分类的日线数据）
```

---

**💡 提示**: 预训练模型（Hugging Face）不需要手动下载，运行预测脚本时会 **自动下载并缓存**，只有网络受限时才需要手动下载。

**验证下载**:
```bash
# 运行 Python 验证模型能否正常加载
python -c "from model import Kronos; m = Kronos.from_pretrained('NeoQuasar/Kronos-small'); print('OK')"
```

---

### 📌 Skill 10: WebUI 可视化操作

**用途**: 图形化界面，适合交互式预测和结果查看

**启动方式**:
```bash
cd webui
conda activate kronos
./start.sh

# 浏览器打开: http://localhost:7070
```

**功能**:
- 支持 CSV/Feather 格式数据上传
- 可调预测参数 (温度、采样、路径数)
- 实时预测结果可视化
- 预测与真实值对比分析
- 专业 K 线图展示

---

## 🎯 预测模型选择对照表

| 对比项 | Skill 2: 预训练模型（未来预测） | Skill 3: 微调模型（未来预测） | Skill 4: 预训练模型（历史回测） | Skill 5: 微调模型（历史回测）✅ |
|--------|-------------------------------|-------------------------------|-------------------------------|-------------------------------|
| **脚本名称** | `predict_future_qlib.py` | `predict_future_finetuned.py` | `prediction_qlib_daily.py` | `prediction_finetuned_backtest.py` |
| **模型来源** | Hugging Face 自动下载 | 本地微调文件 | Hugging Face 自动下载 | 本地微调文件 |
| **微调要求** | ❌ 无需 | ✅ 需微调 | ❌ 无需 | ✅ 需微调 |
| **数据源** | Qlib / 本地 CSV | Qlib / 本地 CSV | Qlib | 本地 CSV 仅 |
| **预测模式** | 纯未来预测 | 纯未来预测 | 历史回测（有真实值对比） | 历史回测（有真实值对比） |
| **A 股准确率** | 通用基础水平 | ⭐⭐⭐⭐⭐ 更高 | 通用基础水平 | ⭐⭐⭐⭐⭐ 更高 |
| **输出误差指标** | ❌ 无 | ❌ 无 | ⚠️ 基础 | ✅ 完整 5 项指标 |
| **适用场景** | 快速验证 | 实盘预测 | 快速验证模型 | 验证微调效果 |
| **输出文件名** | `{stock_code}_future_prediction.png/csv` | `{stock_code}_future_prediction_finetuned.png/csv` |

**推荐**: 先使用 Skill 2（预训练）快速上手，如需要更高 A 股预测质量，再使用 Skill 3（微调后）。

---

## 📦 打包迁移清单

### ✅ **必须打包迁移的核心代码**

```
Kronos-master/
├── model/                          # 核心模型代码（必须）
│   ├── __init__.py
│   ├── kronos.py                  # 主模型、分词器、预测器类
│   ├── module.py                  # Transformer 组件
│   └── utils.py                   # 工具函数
│
├── examples/                       # 预测脚本（必须）
│   ├── predict_future_qlib.py     # 默认预训练模型预测（Qlib数据）
│   ├── predict_future_finetuned.py # 微调后模型预测（推荐）
│   ├── get_stock_data_from_qlib.py # 从Qlib导出单只股票CSV
│   └── prediction_qlib_daily.py   # 回测验证模式（有真实值对比）
│
├── finetune/                      # 微调相关代码（必须）
│   ├── config.py                  # 所有配置集中在这里
│   ├── dataset.py                 # Qlib Dataset 实现
│   ├── qlib_data_preprocess.py   # 数据预处理，生成train/val/test pickle
│   ├── train_tokenizer_single_gpu.py  # 分词器微调（单GPU/CPU，推荐）
│   ├── train_predictor_single_gpu.py  # 预测器微调（单GPU/CPU，推荐）
│   ├── qlib_test.py              # 回测评估脚本
│   └── outputs/                  # 微调后模型保存位置（运行后生成）
│       └── models/
│           ├── finetune_tokenizer_demo/checkpoints/best_model/
│           └── finetune_predictor_demo/checkpoints/best_model/
│
├── webui/                         # 网页界面（可选）
│   ├── app.py                     # Flask 后端
│   ├── run.py                     # 启动脚本
│   ├── start.sh                   # Linux/macOS 启动
│   ├── start.ps1                  # Windows 启动
│   ├── requirements.txt           # WebUI 额外依赖
│   ├── templates/                 # 前端HTML模板
│   └── prediction_results/        # 预测结果保存目录
│
├── CLAUDE.md                      # 项目开发文档
└── requirements.txt               # Python 依赖
```

### 📊 **需要打包的数据文件（如果已在本机生成）**

```
# 如果本机已经有这些数据，一起打包过去，节省时间
Kronos-master/
├── finetune/
│   └── data/
│       └── processed_datasets/    # 预处理好的 pickle 数据
│           ├── train_data.pkl     # 训练集
│           ├── val_data.pkl       # 验证集
│           └── test_data.pkl      # 测试集
│
├── examples/
│   └── data/                      # 导出的单只股票 CSV 数据
│       ├── SH600519_daily.csv    # 贵州茅台
│       └── SZ002507_daily.csv    # 你的股票
```

### 🧠 **预训练模型缓存（可选打包）**

Hugging Face 下载的模型缓存可以一起打包，节省下载时间：
- Windows: `C:\Users\用户名\.cache\huggingface\hub\`
- macOS: `~/.cache/huggingface/hub/`
- Linux: `~/.cache/huggingface/hub/`

包含的模型：
- `models--NeoQuasar--Kronos-mini`
- `models--NeoQuasar--Kronos-small`
- `models--NeoQuasar--Kronos-base`
- `models--NeoQuasar--Kronos-Tokenizer-base`

### ❌ **不需要打包的文件/目录**

```
Kronos-master/
├── .git/                         # Git 版本控制
├── __pycache__/                  # Python 缓存
├── *.pyc                        # 编译文件
├── finetune/__pycache__/
├── examples/__pycache__/
├── model/__pycache__/
│
├── finetune/outputs/backtest_results/  # 回测结果，可以重新生成
│
├── examples/data/*.png           # 生成的预测图，可以重新生成
├── examples/data/*_prediction.csv
│
└── docs/                         # 文档目录，如有
```

---

## 🚀 macOS (Apple Silicon) 部署步骤

### 步骤 1: 环境准备

#### 1.1 安装 Miniconda (Apple Silicon 版本)

```bash
# 下载并安装 Miniconda3 macOS Apple M1 版本
# https://docs.conda.io/en/latest/miniconda.html

# 或者用 brew 安装
brew install miniconda
```

#### 1.2 创建并激活 conda 环境

```bash
cd Kronos-master

# 创建环境
conda create -n kronos python=3.10 -y

# 激活环境
conda activate kronos
```

#### 1.3 安装 PyTorch (Apple Silicon 优化版)

```bash
# 安装支持 MPS 的 PyTorch
conda install pytorch::pytorch torchvision torchaudio -c pytorch

# 验证 MPS 是否可用
python -c "import torch; print(torch.backends.mps.is_available())"
# 应该输出 True
```

#### 1.4 安装其他依赖

```bash
pip install -r requirements.txt

# 验证所有依赖
python -c "import torch; import pandas; import matplotlib; print('OK')"
```

#### 1.5 安装 Qlib (可选，用于A股数据)

```bash
pip install pyqlib yahooquery
```

### 步骤 2: 数据准备 (两种方式)

#### 方式 A: 使用你本机打包的数据

将你打包的 `finetune/data/processed_datasets/*.pkl` 复制到新机器相同位置。

#### 方式 B: 在新机器上重新导出

```bash
# 确保 Qlib 数据目录 ~/.qlib/qlib_data/cn_data 存在
cd finetune
python qlib_data_preprocess.py
```

---

## 🎯 使用流程（macOS）

### 模式 1: 纯未来预测（最常用）

使用你微调好的模型预测未来 60 个交易日：

```bash
cd examples
conda activate kronos

# 1. 先导出股票数据（如果还没有 CSV）
# 编辑 get_stock_data_from_qlib.py 修改 stock_code
python get_stock_data_from_qlib.py

# 2. 运行预测
# 编辑 predict_future_finetuned.py 修改:
#   - stock_code = "SH600519"
#   - USE_LOCAL_CSV = True
#   - lookback = 400
#   - pred_len = 60
python predict_future_finetuned.py

# 3. 查看结果
# 输出在 examples/data/ 目录:
#   - SH600519_future_prediction_finetuned.png  (图像)
#   - SH600519_future_prediction_finetuned.csv  (数据)
```

### 模式 2: 验证回测（有真实值对比）

如果你想验证模型在历史区间的表现：

```bash
cd examples
# 编辑 prediction_qlib_daily.py 修改参数
python prediction_qlib_daily.py
```

### 模式 3: WebUI 界面

```bash
cd webui
conda activate kronos
./start.sh

# 浏览器打开 http://localhost:7070
```

---

## 🔧 微调流程（macOS + MPS 加速）

### 步骤 1: 分词器微调

```bash
cd finetune
conda activate kronos

# 单 GPU / CPU 脚本，自动检测并使用 MPS
python train_tokenizer_single_gpu.py
```

训练过程：
- 每 10 步打印进度、损失、ETA
- 自动保存最佳模型到 `outputs/models/finetune_tokenizer_demo/checkpoints/best_model/`

### 步骤 2: 预测器微调

```bash
cd finetune
# 等待分词器完成后运行
python train_predictor_single_gpu.py
```

### 步骤 3: 回测评估

```bash
cd finetune
python qlib_test.py --device mps
```

---

## ⚙️ 配置说明 (finetune/config.py)

### 关键参数（可根据 macOS 性能调整）

```python
# 数据路径（macOS 路径格式也支持）
self.qlib_data_path = "~/.qlib/qlib_data/cn_data"
self.instrument = 'csi300'  # 股票池: csi300 / csi800 / csi1000

# 时间范围
self.dataset_begin_time = "2011-01-01"
self.dataset_end_time = '2026-04-17'  # 更新到最新日期

# 超参数（根据你的 Mac 性能调整）
self.batch_size = 16         # M1/M2 Pro: 16-32, 基础款: 8
self.epochs = 30            # 训练轮次
self.log_interval = 10      # 每N步打印一次进度

# 训练迭代次数（减少=更快）
self.n_train_iter = 500 * self.batch_size  # 默认 500*8=4000
self.n_val_iter = 100 * self.batch_size    # 验证

# 学习率
self.tokenizer_learning_rate = 2e-4
self.predictor_learning_rate = 4e-5

# 模型保存路径
self.save_path = "./outputs/models"
self.tokenizer_save_folder_name = 'finetune_tokenizer_demo'
self.predictor_save_folder_name = 'finetune_predictor_demo'

# 推理参数
self.inference_T = 0.6
self.inference_top_p = 0.9
self.inference_sample_count = 5
```

---

## 📊 预期性能（Apple Silicon）

| 设备 | M1 / M2 基础款 | M1 Pro / M2 Pro | M1 Max / M2 Max |
|------|---------------|-----------------|-----------------|
| **内存** | 8GB / 16GB | 16GB / 32GB | 32GB / 64GB |
| **batch_size** | 8 | 16-32 | 32-64 |
| **分词器 30轮** | ~3-4 小时 | ~1.5-2 小时 | ~45-60 分钟 |
| **预测器 30轮** | ~4-5 小时 | ~2-3 小时 | ~1-1.5 小时 |
| **单条预测** | ~10-15 秒 | ~5-8 秒 | ~2-4 秒 |

---

## 🔍 常见问题

### Q1: MPS 没有被使用？

```python
# 检查脚本开头是否有
device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
print(f"Using device: {device}")
```

### Q2: "too many open files" 错误？

macOS 默认打开文件数限制低，运行前执行：

```bash
ulimit -n 4096
```

### Q3: 模型找不到？

检查 `finetune/config.py` 中的模型路径是否正确。微调后模型默认保存在：
```
finetune/outputs/models/finetune_tokenizer_demo/checkpoints/best_model/
finetune/outputs/models/finetune_predictor_demo/checkpoints/best_model/
```

### Q4: Qlib 数据找不到？

确保 Qlib 数据目录存在：
```bash
ls -la ~/.qlib/qlib_data/cn_data/
```

如果没有，**请参考 Skill 8: 下载 Qlib A 股训练数据**（推荐浏览器手动下载）

### Q5: 内存不够 OOM？

减小 `config.py` 中的 `batch_size`：
```python
self.batch_size = 4  # 从 16 改到 4 或 8
```

---

## 📁 目录结构（部署后）

```
Kronos-master/
├── requirements.txt               # ✅
├── Kronos-Skill-README.md        # ✅ 本文档
├── CLAUDE.md                      # ✅ 开发文档
│
├── model/                         # ✅ 核心模型
│   ├── __init__.py
│   ├── kronos.py
│   ├── module.py
│   └── utils.py
│
├── examples/                      # ✅ 预测脚本
│   ├── predict_future_finetuned.py  # 微调模型预测
│   ├── predict_future_qlib.py       # 默认模型预测
│   ├── prediction_qlib_daily.py     # 回测验证
│   ├── get_stock_data_from_qlib.py  # 导出单只股票
│   └── data/                        # 输出目录
│       ├── SH600519_daily.csv
│       ├── SH600519_future_prediction_finetuned.png
│       └── SH600519_future_prediction_finetuned.csv
│
├── finetune/                      # ✅ 微调代码
│   ├── config.py
│   ├── dataset.py
│   ├── qlib_data_preprocess.py
│   ├── train_tokenizer_single_gpu.py
│   ├── train_predictor_single_gpu.py
│   ├── qlib_test.py
│   ├── data/processed_datasets/   # 预处理数据
│   │   ├── train_data.pkl
│   │   ├── val_data.pkl
│   │   └── test_data.pkl
│   └── outputs/models/            # 微调后模型
│       ├── finetune_tokenizer_demo/checkpoints/best_model/
│       └── finetune_predictor_demo/checkpoints/best_model/
│
└── webui/                         # ⚙️ 可选，网页界面
```

---

## 🎯 快速启动命令（macOS）

```bash
# ========== 首次运行 ==========
cd Kronos-master
conda activate kronos

# 数据预处理
cd finetune
python qlib_data_preprocess.py

# 微调分词器
python train_tokenizer_single_gpu.py

# 微调预测器
python train_predictor_single_gpu.py

# 回测评估
python qlib_test.py --device mps

# ========== 预测 ==========
cd ../examples
# 编辑 predict_future_finetuned.py 修改股票代码
python predict_future_finetuned.py

# ========== WebUI ==========
cd ../webui
./start.sh
# 访问 http://localhost:7070
```

---

## ⚠️ 注意事项

1. **Apple Silicon MPS 限制**: PyTorch MPS 后端部分操作可能比 CPU 慢，这是正常的。预测推理阶段 MPS 优势明显。

2. **内存交换**: 如果你的 Mac 只有 8GB 内存，训练时可能频繁读写交换，建议减小 `batch_size`。

3. **休眠中断**: 长时间训练时，建议在系统设置中禁止自动休眠，或者用 `caffeinate` 命令保持唤醒：
   ```bash
   caffeinate -i python train_tokenizer_single_gpu.py
   ```

4. **温度控制**: M 芯片训练时温度会升高到 80-90°C，这是正常的，系统会自动降频保护。

---

## 📝 更新日志

- **v1.0**: 初始版本，支持 macOS MPS 加速，单 GPU 微调脚本

> Kronos 是**首个面向金融K线图的开源基础模型**， 基于**全球超过45家交易所**的数据训练而成。

## 📰 最新动态

- 🚩 **[2025.11.10]** Kronos 已被 AAAI 2026 接收。
- 🚩 **[2025.08.17]** 我们已发布微调脚本！欢迎使用这些脚本将 Kronos 适配至您的特定任务。
- 🚩 **[2025.08.02]** 我们的论文现已发布于 [arXiv](https://arxiv.org/abs/2508.02739)！



## 📜 简介

**Kronos** 是一个专为金融市场"语言"——K线序列预训练的 decoder-only 基础模型系列。与通用时间序列预测模型（TSFM）不同，Kronos 专门设计用于处理金融数据独特的高噪声特性。它采用创新的两阶段框架：

1. 专用分词器首先将连续的多维K线数据（OHLCV）量化为**分层离散令牌**。
2. 随后基于这些令牌预训练大型自回归Transformer，使其成为适用于多种量化任务的统一模型。

![img](https://raw.githubusercontent.com/shiyu-coder/Kronos/master/figures/overview.png)

## ✨ 实时演示

我们搭建了实时演示页面以可视化 Kronos 的预测结果。该网页展示了 **BTC/USDT** 交易对未来24小时的预测。

**👉 [点击访问实时演示](https://shiyu-coder.github.io/Kronos-demo/)**

## 📦 模型库

我们发布了一系列不同容量的预训练模型，以满足不同的计算和应用需求。所有模型都可以从 Hugging Face Hub 轻松获取。

| 模型         | 分词器                                                       | 上下文长度 | 参数量 | 开源状态                                                     |
| ------------ | ------------------------------------------------------------ | ---------- | ------ | ------------------------------------------------------------ |
| Kronos-mini  | [Kronos-Tokenizer-2k](https://huggingface.co/NeoQuasar/Kronos-Tokenizer-2k) | 2048       | 4.1M   | ✅ [NeoQuasar/Kronos-mini](https://huggingface.co/NeoQuasar/Kronos-mini) |
| Kronos-small | [Kronos-Tokenizer-base](https://huggingface.co/NeoQuasar/Kronos-Tokenizer-base) | 512        | 24.7M  | ✅ [NeoQuasar/Kronos-small](https://huggingface.co/NeoQuasar/Kronos-small) |
| Kronos-base  | [Kronos-Tokenizer-base](https://huggingface.co/NeoQuasar/Kronos-Tokenizer-base) | 512        | 102.3M | ✅ [NeoQuasar/Kronos-base](https://huggingface.co/NeoQuasar/Kronos-base) |
| Kronos-large | [Kronos-Tokenizer-base](https://huggingface.co/NeoQuasar/Kronos-Tokenizer-base) | 512        | 499.2M | ❌                                                            |

## 🚀 快速开始

### 安装

1. 安装 Python 3.10+，然后安装依赖项：

```shell
pip install -r requirements.txt
```

### 📈 进行预测

使用 Kronos 进行预测非常简单，只需通过 `KronosPredictor` 类即可完成。该类处理数据预处理、归一化、预测和反归一化等步骤，让你仅用几行代码就能从原始数据获得预测结果。

**重要提示**：`Kronos-small` 和 `Kronos-base` 的 `max_context` 值为 **512**。这是模型能处理的最大序列长度。为获得最佳性能，建议输入数据长度（即 `lookback`）不要超过此限制。`KronosPredictor` 会自动处理较长上下文的截断。

以下是进行首次预测的逐步指南。

#### 1. 加载分词器和模型

首先，从 Hugging Face Hub 加载预训练的 Kronos 模型及其对应的分词器。

```python
from model import Kronos, KronosTokenizer, KronosPredictor

# Load from Hugging Face Hub
tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
```

#### 2. 实例化预测器

创建 `KronosPredictor` 的实例，传入模型、分词器以及所需的设备。

```python
# Initialize the predictor
predictor = KronosPredictor(model, tokenizer, max_context=512)
```

#### 3. 准备输入数据

`predict` 方法需要三个主要输入：

- `df`：包含历史 K 线数据的 pandas DataFrame。必须包含列 `['open', 'high', 'low', 'close']`。`volume` 和 `amount` 为可选列。
- `x_timestamp`：与 `df` 中历史数据对应的时间戳 pandas Series。
- `y_timestamp`：你想要预测的未来时间段的时间戳 pandas Series。

```python
import pandas as pd

# Load your data
df = pd.read_csv("./data/XSHG_5min_600977.csv")
df['timestamps'] = pd.to_datetime(df['timestamps'])

# Define context window and prediction length
lookback = 400
pred_len = 120

# Prepare inputs for the predictor
x_df = df.loc[:lookback-1, ['open', 'high', 'low', 'close', 'volume', 'amount']]
x_timestamp = df.loc[:lookback-1, 'timestamps']
y_timestamp = df.loc[lookback:lookback+pred_len-1, 'timestamps']
```

#### 4. 生成预测

调用 `predict` 方法生成预测。您可以通过 `T`、`top_p` 和 `sample_count` 等参数控制概率性预测的采样过程。

```python
# Generate predictions
pred_df = predictor.predict(
    df=x_df,
    x_timestamp=x_timestamp,
    y_timestamp=y_timestamp,
    pred_len=pred_len,
    T=1.0,          # Temperature for sampling
    top_p=0.9,      # Nucleus sampling probability
    sample_count=1  # Number of forecast paths to generate and average
)

print("Forecasted Data Head:")
print(pred_df.head())
```

`predict` 方法返回一个 pandas DataFrame，包含 `open`、`high`、`low`、`close`、`volume` 和 `amount` 的预测值，并以您提供的 `y_timestamp` 作为索引。

为实现多时间序列的高效处理，Kronos 提供了 `predict_batch` 方法，支持对多个数据集同时进行并行预测。这在需要一次性预测多个资产或时间段时尤为实用。

```python
# Prepare multiple datasets for batch prediction
df_list = [df1, df2, df3]  # List of DataFrames
x_timestamp_list = [x_ts1, x_ts2, x_ts3]  # List of historical timestamps
y_timestamp_list = [y_ts1, y_ts2, y_ts3]  # List of future timestamps

# Generate batch predictions
pred_df_list = predictor.predict_batch(
    df_list=df_list,
    x_timestamp_list=x_timestamp_list,
    y_timestamp_list=y_timestamp_list,
    pred_len=pred_len,
    T=1.0,
    top_p=0.9,
    sample_count=1,
    verbose=True
)

# pred_df_list contains prediction results in the same order as input
for i, pred_df in enumerate(pred_df_list):
    print(f"Predictions for series {i}:")
    print(pred_df.head())
```

**批量预测的重要要求：**

- 所有序列必须具有相同的历史长度（回看窗口）
- 所有序列必须具有相同的预测长度（`pred_len`）
- 每个 DataFrame 必须包含必需列：`['open', 'high', 'low', 'close']`
- `volume` 和 `amount` 列为可选列，若缺失将自动填充零值

`predict_batch` 方法利用 GPU 并行机制实现高效处理，并自动为每个序列独立执行归一化与反归一化操作。

#### 5. 示例与可视化

有关包含数据加载、预测和绘图的完整可运行脚本，请参阅 [`examples/prediction_example.py`](https://github.com/shiyu-coder/Kronos/blob/master/examples/prediction_example.py)。

运行此脚本将生成一个对比真实数据与模型预测结果的图表，类似于下图所示：

![Forecast Example](https://raw.githubusercontent.com/shiyu-coder/Kronos/master/figures/prediction_example.png)

此外，我们还提供了一个无需交易量和成交额数据即可进行预测的脚本，可在 [`examples/prediction_wo_vol_example.py`](https://github.com/shiyu-coder/Kronos/blob/master/examples/prediction_wo_vol_example.py) 中找到。

## 🔧 使用自有数据进行微调（A股市场示例）

我们提供了完整的流程，用于在您自己的数据集上对 Kronos 进行微调。作为示例，我们演示了如何使用 [Qlib](https://github.com/microsoft/qlib) 准备中国A股市场数据并进行简单的回测。

> **免责声明：** 本流程旨在演示微调过程，是一个简化示例而非生产就绪的量化交易系统。稳健的量化策略需要更复杂的技术（如投资组合优化和风险因子中性化）才能获得稳定的阿尔法收益。

微调过程分为四个主要步骤：

1. **配置**：设置路径和超参数
2. **数据准备**：使用 Qlib 处理和拆分数据
3. **模型微调**：微调 Tokenizer 和 Predictor 模型
4. **回测**：评估微调后模型的性能

### 环境要求

1. 首先确保已安装 `requirements.txt` 中的所有依赖项

2. 本流程依赖 `qlib`，请通过以下命令安装：

   ```shell
     pip install pyqlib
   ```

3. 需要准备 Qlib 数据。请遵循 [Qlib 官方指南](https://github.com/microsoft/qlib) 下载并在本地设置数据。示例脚本假定您使用日频数据

### 步骤一：配置实验

所有数据、训练和模型路径的设置均集中在 `finetune/config.py` 中。在运行任何脚本前，请根据您的环境**修改以下路径**：

- `qlib_data_path`: 您本地 Qlib 数据目录的路径。
- `dataset_path`: 用于保存处理后的训练/验证/测试 pickle 文件的目录。
- `save_path`: 保存模型检查点的基目录。
- `backtest_result_path`: 用于保存回测结果的目录。
- `pretrained_tokenizer_path` 和 `pretrained_predictor_path`: 您希望从中开始训练的预训练模型路径（可以是本地路径或 Hugging Face 模型名称）。

您还可以调整其他参数，如 `instrument`、`train_time_range`、`epochs` 和 `batch_size`，以适应您的具体任务。如果不使用 [Comet.ml](https://www.comet.com/)，请设置 `use_comet = False`。

### 步骤 2：准备数据集

运行数据预处理脚本。该脚本将从您的 Qlib 目录加载原始市场数据，进行处理，将其分割为训练集、验证集和测试集，并保存为 pickle 文件。

```shell
python finetune/qlib_data_preprocess.py
```

运行后，您将在配置文件中 `dataset_path` 指定的目录中找到 `train_data.pkl`、`val_data.pkl` 和 `test_data.pkl`。

### 步骤 3：运行微调

微调过程包含两个阶段：首先微调分词器，然后微调预测器。两个训练脚本均设计为使用 `torchrun` 进行多 GPU 训练。

#### 3.1 微调分词器

此步骤调整分词器以适应您特定领域的数据分布。

```shell
# Replace NUM_GPUS with the number of GPUs you want to use (e.g., 2)
torchrun --standalone --nproc_per_node=NUM_GPUS finetune/train_tokenizer.py
```

最佳分词器检查点将被保存到 `config.py` 中配置的路径（该路径由 `save_path` 和 `tokenizer_save_folder_name` 派生而来）。

#### 3.2 微调预测器

此步骤针对预测任务微调主要的 Kronos 模型。

```shell
# Replace NUM_GPUS with the number of GPUs you want to use (e.g., 2)
torchrun --standalone --nproc_per_node=NUM_GPUS finetune/train_predictor.py
```

最佳预测器检查点将被保存到 `config.py` 中配置的路径。

### 步骤 4：通过回测进行评估

最后，运行回测脚本来评估您微调后的模型。该脚本会加载模型，在测试集上执行推理，生成预测信号（例如，预测价格变动），并运行一个简单的 Top-K 策略回测。

```shell
# Specify the GPU for inference
python finetune/qlib_test.py --device cuda:0
```

脚本将在控制台输出详细的性能分析，并生成一张图表，显示您的策略相对于基准的累计收益曲线，类似于下图所示：

![Backtest Example](https://raw.githubusercontent.com/shiyu-coder/Kronos/master/figures/backtest_result_example.png)

### 💡 从演示到生产：重要注意事项

- **原始信号 vs. 纯Alpha**: 本演示中模型生成的信号为原始预测。在实际量化工作流中，这些信号通常会被输入投资组合优化模型。该模型会施加约束以对冲常见风险因子（如市场Beta、规模和价值等风格因子）的敞口，从而分离出**"纯Alpha"**并提升策略的稳健性。
- **数据处理**: 提供的 `QlibDataset` 是一个示例。对于不同的数据源或格式，您需要调整数据加载和预处理逻辑。
- **策略与回测复杂性**: 此处使用的简单Top-K策略是一个基础起点。生产级策略通常包含更复杂的投资组合构建逻辑、动态头寸规模调整和风险管理（如止盈止损规则）。此外，高保真度的回测应精细地模拟交易成本、滑点及市场冲击，以更准确地评估实际表现。

> **📝 AI生成的注释**: 请注意，`finetune/` 目录中的许多代码注释由AI助手（Gemini 2.5 Pro）生成，仅用于解释说明。虽然这些注释旨在提供帮助，但可能存在不准确之处。我们建议将代码本身视为逻辑的最终权威来源。

## 📖 引用

如果您在研究中使用 Kronos，我们恳请您引用我们的[论文](https://arxiv.org/abs/2508.02739)：

```
@misc{shi2025kronos,
      title={Kronos: A Foundation Model for the Language of Financial Markets}, 
      author={Yu Shi and Zongliang Fu and Shuo Chen and Bohan Zhao and Wei Xu and Changshui Zhang and Jian Li},
      year={2025},
      eprint={2508.02739},
      archivePrefix={arXiv},
      primaryClass={q-fin.ST},
      url={https://arxiv.org/abs/2508.02739}, 
}
```

## 📜 许可证

本项目采用 [MIT 许可证](https://github.com/shiyu-coder/Kronos/blob/master/LICENSE) 进行授权。

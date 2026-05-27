# 使用微调后模型进行未来预测 - 使用说明

## 脚本区别

| 脚本 | 模型来源 | 用途 |
|------|----------|------|
| `predict_future_qlib.py` | Hugging Face 下载**默认预训练模型** (Kronos-small/base) | 直接使用作者提供的全球数据预训练模型 |
| **`predict_future_finetuned.py`** (本脚本) | 你**本地微调后保存的模型** | 使用你在 A 股数据上微调后的模型进行预测 |

## 使用前提

你需要已经完成完整微调流程：
1. ✓ 数据预处理 `python qlib_data_preprocess.py`
2. ✓ 分词器微调 `python train_tokenizer_single_gpu.py`
3. ✓ 预测器微调 `python train_predictor_single_gpu.py`

模型会自动从 `finetune/config.py` 配置的路径加载：
- 分词器: `finetune/outputs/models/finetune_tokenizer_demo/checkpoints/best_model`
- 预测器: `finetune/outputs/models/finetune_predictor_demo/checkpoints/best_model`

## 使用方法

### 方式一：使用本地 CSV（推荐，你已经通过 get_stock_data_from_qlib.py 导出数据）

如果你已经通过 `get_stock_data_from_qlib.py` 将股票数据导出为 CSV 文件保存到 `examples/data/`，设置 `USE_LOCAL_CSV = True` 直接读取：

```python
# 在脚本开头修改：
stock_code = "SH600519"          # 改成你要预测的股票
USE_LOCAL_CSV = True             # 使用本地 CSV
local_csv_path = f"./data/{stock_code}_daily.csv"  # CSV 文件路径
```

然后运行：
```bash
cd examples
conda activate kronos
python predict_future_finetuned.py
```

### 方式二：直接从 Qlib 获取

如果你想每次预测重新从 Qlib 获取最新数据，设置 `USE_LOCAL_CSV = False`：

```python
stock_code = "SH600519"
USE_LOCAL_CSV = False
```

然后运行同上。

## 配置参数

在脚本开头 `if __name__ == "__main__":` 部分修改：

```python
# 股票代码（Qlib 格式：SH 表示上证，SZ 表示深证）
# 示例: SH600519（贵州茅台）, SH000001（上证指数）, SZ000001（平安银行）
stock_code = "SH600519"

# ========== 数据来源选择 ==========
# USE_LOCAL_CSV = False: 从 Qlib 直接获取最新数据（需要 Qlib 数据目录）
# USE_LOCAL_CSV = True: 从本地 CSV 读取数据（文件: ./data/{stock_code}_daily.csv）
#   本地 CSV 由 get_stock_data_from_qlib.py 导出，适合网络不好不想重复获取
USE_LOCAL_CSV = True
local_csv_path = f"./data/{stock_code}_daily.csv"

# 超参数设置:
# lookback: 使用多少历史 K 线作为上下文（回看窗口）
# 注意: 不超过 max_context (对于 small/base 是 512)
lookback = 400
# pred_len: 预测未来多少个时间步（日线）
pred_len = 60

# 采样参数
T = 1.0           # 采样温度，1.0 表示不调整，值越小越确定，值越大越多样
top_p = 0.9       # nucleus 采样参数，保留累积概率达到 top_p 的 tokens
sample_count = 1  # 生成多少条预测路径，多条路径会被平均得到最终预测
```

## 使用工作流（配合 get_stock_data_from_qlib.py）

推荐工作流（适合网络不好，手动下载了 Qlib 全量数据）：

1. **第一步：导出股票数据到 CSV**
   ```bash
   cd examples
   conda activate kronos
   # 编辑 get_stock_data_from_qlib.py 修改 stock_code，然后运行
   python get_stock_data_from_qlib.py
   ```
   这会导出 `examples/data/{stock_code}_daily.csv`

2. **第二步：使用微调模型预测**
   ```bash
   # 在 predict_future_finetuned.py 中设置：
   stock_code = "你的股票代码"
   USE_LOCAL_CSV = True
   # 运行预测
   python predict_future_finetuned.py
   ```

## 输出结果

运行完成后会生成两个文件保存到 `examples/data/` 目录：

| 文件 | 说明 |
|------|------|
| `{stock_code}_future_prediction_finetuned.png` | 预测结果图像，三幅子图：前复权历史+预测、成交量、不复权历史+预测 |
| `{stock_code}_future_prediction_finetuned.csv` | 预测数据 CSV，包含 open/high/low/close/volume/amount |

## 输出示例

脚本运行时会打印：
```
股票: SH600519
使用微调后模型:
  分词器: ./outputs/models/finetune_tokenizer_demo/checkpoints/best_model
  预测器: ./outputs/models/finetune_predictor_demo/checkpoints/best_model
  数据来源: 本地 CSV (./data/SH600519_daily.csv)

 数据处理完成，最终 X 条记录
  时间范围: 2018-01-02 00:00:00 → 2026-04-17 00:00:00
  价格范围 (前复权): xxx → xxx (最新价: xxx)
  价格范围 (不复权): xxx → xxx (最新价: xxx)

数据分割 (纯预测模式):
  历史窗口 (lookback): 400 条
  预测长度 (pred_len): 60 条
  历史时间: 20xx-xx-xx → 20xx-xx-xx
  预测时间: 20xx-xx-xx → 20xx-xx-xx

加载微调后的模型...
  分词器路径: ...
  预测器路径: ...
  模型加载完成
  预测器初始化完成

开始预测...
...预测过程日志...

预测完成！Forecasted Data Head:
...打印预测数据前几行...

未来预测图像已保存: ./data/SH600519_future_prediction_finetuned.png
未来预测数据已保存: ./data/SH600519_future_prediction_finetuned.csv
```

## 和默认预训练模型预测对比

如果你想对比默认预训练模型和你微调后模型的预测差异，可以分别运行：

```bash
# 默认预训练模型（Hugging Face 下载）
python predict_future_qlib.py
# 本地微调后模型（你训练出来的）
python predict_future_finetuned.py
```

两个脚本会生成不同的输出文件，不会互相覆盖：
- 默认: `{stock}_future_prediction.png` + `{stock}_future_prediction.csv`
- 微调: `{stock}_future_prediction_finetuned.png` + `{stock}_future_prediction_finetuned.csv`

## 注意事项

1. **模型路径**：由 `finetune/config.py` 自动读取，不需要手动修改
   - 分词器: `finetune/outputs/models/finetune_tokenizer_demo/checkpoints/best_model`
   - 预测器: `finetune/outputs/models/finetune_predictor_demo/checkpoints/best_model`
2. **Qlib 数据路径**：和 finetune 保持一致，不需要重复配置
3. **上下文限制**：保持 `lookback ≤ 512`，因为 Kronos-small/base 的最大上下文长度是 512
4. **必须先完成微调**：如果没有完成微调直接运行脚本会报错，提示找不到模型文件
5. **不复权价格计算**：脚本自动计算，和 `predict_future_qlib.py` 保持一致，显示和行情软件一致的价格

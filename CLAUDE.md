# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview
Kronos is the first open-source foundation model for financial candlestick (K-line) data. It uses a two-stage approach:
1. A specialized tokenizer quantizes continuous multi-dimensional OHLCV data into hierarchical discrete tokens
2. An autoregressive Transformer is pre-trained on these tokens for diverse quantitative finance tasks

**Local Documentation**:
- `README-CN.md`: Chinese README
- `00-AKShare获取A股K线数据教程.md`: Step-by-step guide to fetch A-share K-line data using AKShare
- `01-Kronos论文中文翻译.md`: Complete Chinese translation of the paper
- `03-赵鑫海的微调预测方案.md`: Custom "periodic fine-tuning + daily sliding prediction" workflow for personal use
- `Qlib获取A股日线数据教程.md`: Qlib download and initial setup guide (alternative to AKShare when Eastmoney API is blocked)
- `Qlib数据源更新和预测使用手册.md`: Complete guide for updating Qlib data and running prediction

## Environment Setup
```bash
# Create conda environment (recommended)
conda create -n kronos python=3.10 -y
conda activate kronos

# Install dependencies
pip install -r requirements.txt
```

## Commands
- **Install dependencies**: `pip install -r requirements.txt`
- **Install Qlib (for A-share data)**: `pip install pyqlib yahooquery`
- **Run quickstart prediction example**: `cd examples && python prediction_example.py`
- **Run Qlib-based A-share daily prediction (recommended when AKShare is blocked)**: `cd examples && python prediction_qlib_daily.py`
- **Update single stock to latest date from Yahoo Finance**: `cd examples && python update_single_stock_qlib.py` (edit `STOCK_CODE` first)
- **Export single stock from local Qlib cache**: `cd examples && python get_stock_data_from_qlib.py` (edit `STOCK_CODE` first)
- **Run tests**: `python -m pytest tests/test_kronos_regression.py -v`
- **Download example data with AKShare**: `cd examples && python download_example_data.py`
- **Generate random test data (when offline)**: `cd examples && python generate_random_data.py`
- **Finetune data preprocessing**: `python finetune/qlib_data_preprocess.py` (requires qlib: `pip install pyqlib`)
- **Finetune tokenizer (multi-GPU)**: `torchrun --standalone --nproc_per_node=NUM_GPUS finetune/train_tokenizer.py`
- **Finetune predictor (multi-GPU)**: `torchrun --standalone --nproc_per_node=NUM_GPUS finetune/train_predictor.py`
- **Run backtest**: `python finetune/qlib_test.py --device cuda:0`
- **Start web UI (Linux/macOS)**: `cd webui && bash start.sh`
- **Start web UI (Windows PowerShell)**: `cd webui; .\start.ps1`

## Architecture
- `model/__init__.py`: Exports the three main classes: `Kronos`, `KronosTokenizer`, `KronosPredictor`
- `model/kronos.py`: Main classes - `Kronos` (autoregressive Transformer model), `KronosTokenizer` (hybrid quantization with Binary Spherical Quantization), `KronosPredictor` (high-level API for inference that handles normalization/tokenization/prediction/denormalization automatically)
- `model/module.py`: Core Transformer components - TransformerBlock, Attention, RMSNorm, MLP, BSQuantizer
- `finetune/`: Qlib-based end-to-end finetuning pipeline for A-share market
  - `config.py`: Configuration for paths, instruments, and hyperparameters
  - `dataset.py`: Qlib dataset implementation
  - `qlib_data_preprocess.py`: Convert Qlib data to training format
  - `train_tokenizer.py`: Tokenizer fine-tuning script
  - `train_predictor.py`: Predictor fine-tuning script
  - `qlib_test.py`: Backtesting evaluation with cumulative return visualization
- `examples/`: Example prediction scripts
  - `prediction_example.py`: Basic single-series prediction with visualization (uses Kronos-base by default)
  - `prediction_qlib_daily.py`: All-in-one A-share daily prediction with Qlib data (Qlib → Kronos → visualization)
  - `prediction_batch_example.py`: Batch prediction for multiple series
  - `prediction_wo_vol_example.py`: Prediction when volume/amount data is missing
  - `download_example_data.py`: Download real 600977 5-minute data via AKShare
  - `generate_random_data.py`: Generate random walk test data when offline
  - `get_stock_data_from_qlib.py`: Export single stock from local Qlib cache to Kronos-compatible CSV
  - `update_single_stock_qlib.py`: Update single stock to latest date directly from Yahoo Finance (no Qlib required)
- `finetune_csv/`: Examples of fine-tuning with CSV format data
- `tests/`: Regression tests
- `webui/`: Gradio web UI for interactive prediction visualization
  - `start.sh`: Linux/macOS startup script
  - `start.ps1`: Windows PowerShell startup script

## Model Variants
| Model        | Params   | Context | Tokenizer             | Hugging Face ID |
|--------------|----------|---------|-----------------------|-----------------|
| Kronos-mini  | 4.1M     | 2048    | NeoQuasar/Kronos-Tokenizer-2k | NeoQuasar/Kronos-mini |
| Kronos-small | 24.7M    | 512     | NeoQuasar/Kronos-Tokenizer-base | NeoQuasar/Kronos-small |
| Kronos-base  | 102.3M   | 512     | NeoQuasar/Kronos-Tokenizer-base | NeoQuasar/Kronos-base |
| Kronos-large | 499.2M   | 512     | NeoQuasar/Kronos-Tokenizer-base | Not open-sourced |

## Key Concepts
- **lookback**: Number of historical K-lines used as context for prediction (must not exceed max context length: 512 for small/base)
- **pred_len**: Number of future time steps to predict
- **two-stage framework**: Tokenizer quantizes continuous OHLCV → discrete tokens → Transformer predicts next token autoregressively
- **max_context**: Maximum sequence length the model can handle
- **sample_count**: Number of prediction paths to generate (multiple paths are averaged for better results and uncertainty estimation)

## Qlib Integration for A-Share Data
When AKShare cannot access Eastmoney API due to network restrictions, use Qlib as an alternative data source. Three usage scenarios:

1. **All-in-one prediction**: Use `prediction_qlib_daily.py` - reads directly from local Qlib cache, automatically adjusts forward split prices, runs prediction, outputs visualization with properly formatted timestamps.

2. **Export from local Qlib**: Use `get_stock_data_from_qlib.py` - when you already have full Qlib data downloaded locally, exports single stock to CSV for Kronos prediction.

3. **Direct download single stock**: Use `update_single_stock_qlib.py` - no local Qlib data required, downloads directly from Yahoo Finance to CSV format ready for prediction.

**Data Format**: All Qlib integration scripts automatically handle forward split adjustment (Qlib stores unadjusted prices + adjustment factor, scripts multiply to get forward-adjusted prices) and output CSV in Kronos-compatible format: `timestamps,open,high,low,close,volume,amount`.

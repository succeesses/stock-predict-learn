#!/bin/bash
# ==============================================================================
# Kronos macOS 完整微调流水线脚本
# 功能: 一键运行分词器微调 -> 预测器微调 -> 回测评估
# ==============================================================================

set -e  # 遇到错误立即退出

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ==============================================================================
# 启动信息
# ==============================================================================
echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║           Kronos macOS 完整微调流水线 (MPS 加速)              ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# ==============================================================================
# 环境检查
# ==============================================================================
print_info "检查运行环境..."

# 检查 Conda 环境是否激活
if [[ -z "$CONDA_DEFAULT_ENV" || "$CONDA_DEFAULT_ENV" != "kronos" ]]; then
    print_error "请先激活 kronos 环境: conda activate kronos"
    exit 1
fi
print_success "Conda 环境已激活: $CONDA_DEFAULT_ENV"

# 检查 MPS 可用性
MPS_AVAILABLE=$(python -c "import torch; print(torch.backends.mps.is_available())" 2>/dev/null || echo "False")
if [[ "$MPS_AVAILABLE" == "True" ]]; then
    print_success "MPS 加速可用 ✓"
else
    print_warning "MPS 不可用，将使用 CPU 运行 (较慢)"
fi

# 增加打开文件限制
ulimit -n 4096
print_info "设置打开文件限制: $(ulimit -n)"

# ==============================================================================
# 步骤 1: 检查数据
# ==============================================================================
echo ""
echo "┌─────────────────────────────────────────────────────────────┐"
echo "│ 步骤 1/3: 检查预处理数据                                    │"
echo "└─────────────────────────────────────────────────────────────┘"
echo ""

DATA_PATH="./data/processed_datasets"
if [[ ! -f "$DATA_PATH/train_data.pkl" ]]; then
    print_warning "预处理数据不存在，将运行数据预处理..."
    python qlib_data_preprocess.py
    print_success "数据预处理完成"
else
    print_success "预处理数据已存在，跳过此步骤"
fi

# ==============================================================================
# 步骤 2: 分词器微调
# ==============================================================================
echo ""
echo "┌─────────────────────────────────────────────────────────────┐"
echo "│ 步骤 2/3: 微调分词器 (Tokenizer)                            │"
echo "└─────────────────────────────────────────────────────────────┘"
echo ""

START_TIME=$(date +%s)

python train_tokenizer_single_gpu.py

TOKENIZER_TIME=$(( $(date +%s) - START_TIME ))
print_success "分词器微调完成，用时: $((TOKENIZER_TIME / 60)) 分 $((TOKENIZER_TIME % 60)) 秒"

# ==============================================================================
# 步骤 3: 预测器微调
# ==============================================================================
echo ""
echo "┌─────────────────────────────────────────────────────────────┐"
echo "│ 步骤 3/3: 微调预测器 (Predictor)                            │"
echo "└─────────────────────────────────────────────────────────────┘"
echo ""

START_TIME=$(date +%s)

python train_predictor_single_gpu.py

PREDICTOR_TIME=$(( $(date +%s) - START_TIME ))
print_success "预测器微调完成，用时: $((PREDICTOR_TIME / 60)) 分 $((PREDICTOR_TIME % 60)) 秒"

# ==============================================================================
# 回测评估 (可选)
# ==============================================================================
echo ""
read -p "是否运行回测评估？(y/n, 默认: y): " RUN_BACKTEST
RUN_BACKTEST=${RUN_BACKTEST:-y}

if [[ "$RUN_BACKTEST" == "y" || "$RUN_BACKTEST" == "Y" ]]; then
    echo ""
    echo "┌─────────────────────────────────────────────────────────────┐"
    echo "│ 回测评估 (Backtesting)                                      │"
    echo "└─────────────────────────────────────────────────────────────┘"
    echo ""

    python qlib_test.py --device auto

    print_success "回测评估完成"
fi

# ==============================================================================
# 完成摘要
# ==============================================================================
TOTAL_TIME=$(( $(date +%s) - START_TIME ))

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                        所有任务完成！                          ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "耗时统计:"
echo "  - 分词器微调: $((TOKENIZER_TIME / 60)) 分 $((TOKENIZER_TIME % 60)) 秒"
echo "  - 预测器微调: $((PREDICTOR_TIME / 60)) 分 $((PREDICTOR_TIME % 60)) 秒"
echo ""
echo "输出文件位置:"
echo "  - 微调分词器: ./outputs/models/finetune_tokenizer_demo/checkpoints/best_model/"
echo "  - 微调预测器: ./outputs/models/finetune_predictor_demo/checkpoints/best_model/"
echo "  - 回测结果: ./outputs/backtest_results/"
echo ""
echo "下一步:"
echo "  cd examples && python predict_future_finetuned.py"
echo ""
print_success "Kronos 微调完成！可以开始预测了。"

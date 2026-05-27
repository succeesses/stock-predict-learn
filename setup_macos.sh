#!/bin/bash
# ==============================================================================
# Kronos macOS 环境设置脚本
# 功能: 自动检查并设置 macOS Apple Silicon 优化的运行环境
# ==============================================================================

set -e  # 遇到错误立即退出

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ==============================================================================
# 打印带颜色的消息
# ==============================================================================
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
# 系统检查
# ==============================================================================
echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║          Kronos macOS 环境设置 (Apple Silicon 优化)           ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# 检查是否为 macOS
if [[ "$(uname)" != "Darwin" ]]; then
    print_error "此脚本仅适用于 macOS 系统"
    exit 1
fi

# 检查架构
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]]; then
    print_success "检测到 Apple Silicon (arm64) 架构 - 完全支持 MPS 加速"
else
    print_warning "检测到 Intel 架构 ($ARCH) - 不支持 MPS 加速，将使用 CPU"
fi

# ==============================================================================
# 检查 Miniconda/Conda
# ==============================================================================
print_info "检查 Conda 环境..."

if ! command -v conda &> /dev/null; then
    print_warning "Conda 未找到，建议安装 Miniconda"
    echo "  下载地址: https://docs.conda.io/en/latest/miniconda.html"
    echo "  选择 macOS Apple M1 版本"
    read -p "按 Enter 继续，或 Ctrl+C 退出后安装 Conda..."
else
    print_success "Conda 已安装"
fi

# ==============================================================================
# 创建/激活 Conda 环境
# ==============================================================================
ENV_NAME="kronos"

if conda info --envs | grep -q "^$ENV_NAME "; then
    print_info "Conda 环境 '$ENV_NAME' 已存在，将直接使用"
else
    print_info "正在创建 Conda 环境 '$ENV_NAME' (Python 3.10)..."
    conda create -n $ENV_NAME python=3.10 -y
    print_success "Conda 环境创建完成"
fi

# 激活环境
print_info "激活 Conda 环境..."
source $(conda info --base)/etc/profile.d/conda.sh
conda activate $ENV_NAME

# ==============================================================================
# 安装 PyTorch (支持 MPS)
# ==============================================================================
print_info "检查 PyTorch MPS 支持..."

python -c "import torch; print('PyTorch 版本:', torch.__version__)" 2>/dev/null || {
    print_info "正在安装支持 MPS 的 PyTorch..."
    conda install pytorch::pytorch torchvision torchaudio -c pytorch -y
}

# 验证 MPS
MPS_AVAILABLE=$(python -c "import torch; print(torch.backends.mps.is_available())" 2>/dev/null || echo "False")

if [[ "$MPS_AVAILABLE" == "True" ]]; then
    print_success "MPS (Metal Performance Shaders) 加速可用 ✓"
else
    print_warning "MPS 不可用，将使用 CPU 运行"
fi

# ==============================================================================
# 安装依赖
# ==============================================================================
print_info "安装 Python 依赖..."
pip install -r requirements.txt

# ==============================================================================
# 增加打开文件限制 (macOS 默认较低)
# ==============================================================================
CURRENT_ULIMIT=$(ulimit -n)
if [[ "$CURRENT_ULIMIT" -lt 4096 ]]; then
    print_warning "当前打开文件限制 ($CURRENT_ULIMIT) 较低，训练时可能出错"
    print_info "正在增加限制到 4096 (仅当前会话有效)..."
    ulimit -n 4096
    echo "  永久设置方法: 在 ~/.zshrc 或 ~/.bash_profile 中添加 'ulimit -n 4096'"
else
    print_success "打开文件限制 ($CURRENT_ULIMIT) 足够"
fi

# ==============================================================================
# 环境摘要
# ==============================================================================
echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                       环境设置完成                              ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "系统信息:"
echo "  - 架构: $ARCH"
echo "  - macOS: $(sw_vers -productVersion)"
echo ""
echo "Python 环境:"
echo "  - Conda 环境: $ENV_NAME"
echo "  - Python: $(python --version | awk '{print $2}')"
echo "  - PyTorch: $(python -c 'import torch; print(torch.__version__)')"
echo "  - MPS 可用: $MPS_AVAILABLE"
echo ""
echo "快速命令:"
echo "  激活环境:  conda activate $ENV_NAME"
echo "  微调分词器: cd finetune && python train_tokenizer_single_gpu.py"
echo "  微调预测器: cd finetune && python train_predictor_single_gpu.py"
echo "  回测评估:   cd finetune && python qlib_test.py --device auto"
echo "  运行预测:   cd examples && python predict_future_finetuned.py"
echo "  启动 WebUI: cd webui && ./start.sh"
echo ""
print_success "环境设置完成！可以开始使用 Kronos 了。"

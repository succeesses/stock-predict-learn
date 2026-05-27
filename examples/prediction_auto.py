"""
Kronos 自动预测脚本 — 无需手动准备数据。

用法:
  conda activate kronos
  cd examples

  # 基本用法（贵州茅台，预测 30 天）
  python prediction_auto.py --code 600519 --pred-len 30

  # 指定模型和 lookback
  python prediction_auto.py --code 000001 --pred-len 20 --lookback 256 --model small

  # 指定输出路径
  python prediction_auto.py --code 300750 --pred-len 60 --output ./my_pred.png
"""

import argparse
import logging
import os
import ssl
import sys
from datetime import datetime, timedelta

ssl._create_default_https_context = ssl._create_unverified_context
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model import Kronos, KronosTokenizer, KronosPredictor
from kronos_data_provider import KronosDataManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("prediction_auto")

plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

MODEL_MAP = {
    "mini": ("NeoQuasar/Kronos-Tokenizer-2k", "NeoQuasar/Kronos-mini", 2048),
    "small": ("NeoQuasar/Kronos-Tokenizer-base", "NeoQuasar/Kronos-small", 512),
    "base": ("NeoQuasar/Kronos-Tokenizer-base", "NeoQuasar/Kronos-base", 512),
}


def parse_args():
    parser = argparse.ArgumentParser(description="Kronos 自动预测")
    parser.add_argument("--code", type=str, default="600519", help="股票代码")
    parser.add_argument("--pred-len", type=int, default=30, help="预测天数")
    parser.add_argument("--lookback", type=int, default=0, help="回看天数 (0=自动)")
    parser.add_argument("--model", type=str, default="base", choices=list(MODEL_MAP),
                        help="模型大小")
    parser.add_argument("--output", type=str, default="", help="输出图片路径")
    parser.add_argument("--cache-dir", type=str, default="./data_cache",
                        help="数据缓存目录")
    parser.add_argument("--no-cache", action="store_true", help="不使用缓存")
    parser.add_argument("--save-csv", action="store_true", help="同时保存预测 CSV")
    return parser.parse_args()


def plot_prediction(kline_df, pred_df, code, output_path):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True)

    pred_df.index = kline_df.index[-pred_df.shape[0]:]

    ax1.plot(kline_df.index, kline_df["close"], label="历史收盘价",
             color="blue", linewidth=1.5)
    ax1.plot(pred_df.index, pred_df["close"], label="预测收盘价",
             color="red", linewidth=1.5, linestyle="--")
    ax1.set_ylabel("收盘价", fontsize=13)
    ax1.set_title(f"Kronos 自动预测 — {code}", fontsize=14)
    ax1.legend(loc="upper left", fontsize=11)
    ax1.grid(True, alpha=0.3)

    ax2.plot(kline_df.index, kline_df["volume"], label="历史成交量",
             color="blue", linewidth=1.5)
    ax2.plot(pred_df.index, pred_df["volume"], label="预测成交量",
             color="red", linewidth=1.5, linestyle="--")
    ax2.set_ylabel("成交量", fontsize=13)
    ax2.legend(loc="upper left", fontsize=11)
    ax2.grid(True, alpha=0.3)

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    plt.xticks(rotation=30)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close()
    logger.info(f"预测图已保存: {output_path}")


def main():
    args = parse_args()
    code = args.code.strip().upper()
    pred_len = args.pred_len
    model_key = args.model

    tokenizer_name, model_name, max_ctx = MODEL_MAP[model_key]
    lookback = args.lookback if args.lookback > 0 else max_ctx

    logger.info(f"股票: {code}  模型: {model_key}(ctx={max_ctx})  预测: {pred_len}天  lookback: {lookback}")

    logger.info("加载模型...")
    tokenizer = KronosTokenizer.from_pretrained(tokenizer_name)
    model = Kronos.from_pretrained(model_name)
    predictor = KronosPredictor(model, tokenizer, max_context=max_ctx)

    logger.info("自动获取数据...")
    manager = KronosDataManager(cache_dir=args.cache_dir)
    df = manager.get_daily_data(
        code,
        days=lookback + pred_len + 20,
        use_cache=not args.no_cache,
    )

    if df.empty or len(df) < lookback + 1:
        logger.error(f"数据不足: 需要 {lookback + 1} 条, 仅有 {len(df)} 条")
        sys.exit(1)

    df["timestamps"] = pd.to_datetime(df["date"])
    df_all = df.tail(lookback + pred_len).reset_index(drop=True)

    x_df = df_all.iloc[:lookback][["open", "high", "low", "close", "volume", "amount"]]
    x_ts = df_all.iloc[:lookback]["timestamps"]
    y_ts = df_all.iloc[lookback: lookback + pred_len]["timestamps"]

    logger.info(f"预测区间: {y_ts.iloc[0].date()} ~ {y_ts.iloc[-1].date()}")

    logger.info("执行预测...")
    pred_df = predictor.predict(
        df=x_df,
        x_timestamp=x_ts,
        y_timestamp=y_ts,
        pred_len=pred_len,
        T=1.0,
        top_k=1,
        top_p=1.0,
        verbose=False,
        sample_count=1,
    )

    logger.info("预测完成，可视化...")
    output = args.output or f"./data/{code}_prediction_auto.png"
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    plot_prediction(df_all, pred_df, code, output)

    if args.save_csv:
        csv_path = output.replace(".png", ".csv")
        pred_df.to_csv(csv_path, index=False)
        logger.info(f"预测 CSV 已保存: {csv_path}")

    pred_close = pred_df["close"].values
    print(f"\n{'=' * 50}")
    print(f"  {code} 预测结果摘要")
    print(f"{'=' * 50}")
    print(f"  最新收盘价: {df_all['close'].iloc[lookback - 1]:.2f}")
    print(f"  预测最高价: {pred_df['high'].max():.2f}")
    print(f"  预测最低价: {pred_df['low'].min():.2f}")
    print(f"  预测均价:   {pred_close.mean():.2f}")
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    main()

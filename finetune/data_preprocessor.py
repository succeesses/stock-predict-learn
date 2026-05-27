"""
Kronos 数据预处理器 — 替代 Qlib 版本，使用 kronos_data_provider 自动获取数据。

输出 pickle 格式与 QlibDataset 完全兼容：
  {symbol: DataFrame(datetime index, columns=[open,high,low,close,vol,amt])}
"""

import os
import pickle
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from tqdm import trange

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from kronos_data_provider import KronosDataManager
from kronos_data_provider.stock_list import get_stock_list


class DataPreprocessor:

    def __init__(self):
        self.config = Config()
        self.data: dict[str, pd.DataFrame] = {}
        self.manager = KronosDataManager(cache_dir=self.config.data_cache_dir)

    def fetch_data(self):
        print("获取成分股列表...")
        codes = get_stock_list(self.config.stock_list_source)
        print(f"共 {len(codes)} 只股票")

        self.data = {}
        for i, code in enumerate(codes):
            print(f"[{i + 1}/{len(codes)}] {code}...")
            try:
                df = self.manager.get_daily_data(
                    code,
                    start=self.config.dataset_begin_time,
                    end=self.config.dataset_end_time,
                    use_cache=True,
                )
                if df.empty or len(df) < self.config.lookback_window + self.config.predict_window + 1:
                    print(f"  跳过 {code}: 数据不足")
                    continue
                df = df.set_index("date")
                df.index.name = "datetime"
                df["vol"] = df["volume"].astype(np.float32)
                df["amt"] = df["amount"].astype(np.float32)
                self.data[code] = df[["open", "high", "low", "close", "vol", "amt"]]
                print(f"  ✓ {len(df)} 条")
            except Exception as e:
                print(f"  ✗ {code}: {e}")

        print(f"\n成功获取 {len(self.data)} / {len(codes)} 只股票")

    def prepare_dataset(self):
        print("按时间范围切分 train/val/test...")
        train_data, val_data, test_data = {}, {}, {}
        symbols = list(self.data.keys())

        for symbol in symbols:
            df = self.data[symbol]
            train_start, train_end = self.config.train_time_range
            val_start, val_end = self.config.val_time_range
            test_start, test_end = self.config.test_time_range

            train_mask = (df.index >= train_start) & (df.index <= train_end)
            val_mask = (df.index >= val_start) & (df.index <= val_end)
            test_mask = (df.index >= test_start) & (df.index <= test_end)

            train_sub = df[train_mask]
            val_sub = df[val_mask]
            test_sub = df[test_mask]

            if len(train_sub) >= self.config.lookback_window + 1:
                train_data[symbol] = train_sub
            if len(val_sub) >= self.config.lookback_window + 1:
                val_data[symbol] = val_sub
            if len(test_sub) >= self.config.lookback_window + 1:
                test_data[symbol] = test_sub

        os.makedirs(self.config.dataset_path, exist_ok=True)
        for name, data in [("train_data", train_data), ("val_data", val_data), ("test_data", test_data)]:
            path = f"{self.config.dataset_path}/{name}.pkl"
            with open(path, "wb") as f:
                pickle.dump(data, f)
            print(f"  {name}.pkl: {len(data)} symbols")

        print("数据集准备完成")


if __name__ == "__main__":
    preprocessor = DataPreprocessor()
    preprocessor.fetch_data()
    preprocessor.prepare_dataset()

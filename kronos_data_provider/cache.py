"""本地 CSV 缓存管理。支持增量更新、断点续传。"""

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


_CHINESE_HOLIDAYS_2026 = frozenset({
    "2026-01-01", "2026-01-02",
    "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20",
    "2026-04-06",
    "2026-05-01", "2026-05-04", "2026-05-05",
    "2026-06-22",
    "2026-09-28", "2026-09-29", "2026-09-30",
    "2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07",
})


def _is_trading_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    return d.isoformat() not in _CHINESE_HOLIDAYS_2026


def _last_trading_day(ref: Optional[date] = None) -> date:
    """返回最近一个已完成交易日（今天若为交易日则返回今天）。"""
    d = ref or date.today()
    while not _is_trading_day(d):
        d -= timedelta(days=1)
    return d


def _latest_trading_day() -> date:
    """别名，同 _last_trading_day。"""
    return _last_trading_day()


class DataCache:

    def __init__(self, cache_dir: str = "./data_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[Cache] 目录: {self.cache_dir.resolve()}")

    def _cache_path(self, code: str) -> Path:
        return self.cache_dir / f"{self._normalize(code)}.csv"

    @staticmethod
    def _normalize(code: str) -> str:
        c = code.strip().upper()
        for pf in ["SH", "SZ", "BJ"]:
            if c.startswith(pf) and c[len(pf):].isdigit():
                return c[len(pf):]
        if "." in c:
            c = c.split(".")[0]
        return c

    def get(self, code: str) -> Optional[pd.DataFrame]:
        path = self._cache_path(code)
        if not path.exists():
            return None
        df = pd.read_csv(path, parse_dates=["date"])
        logger.debug(f"[Cache] 读取 {code}: {len(df)} 条")
        return df

    def save(self, code: str, df: pd.DataFrame):
        if df.empty:
            logger.warning(f"[Cache] {code} 数据为空，跳过保存")
            return
        path = self._cache_path(code)
        cols = [c for c in ["date", "open", "high", "low", "close", "volume", "amount"] if c in df.columns]
        df[cols].to_csv(path, index=False)
        logger.info(f"[Cache] 保存 {code}: {len(df)} 条 -> {path.name}")

    def update(self, code: str, new_df: pd.DataFrame):
        if new_df.empty:
            logger.info(f"[Cache] {code} 新数据为空，跳过")
            return
        existing = self.get(code)
        if existing is None:
            self.save(code, new_df)
            return
        new_df["date"] = pd.to_datetime(new_df["date"])
        existing["date"] = pd.to_datetime(existing["date"])
        append = new_df[new_df["date"] > existing["date"].max()]
        if append.empty:
            logger.info(f"[Cache] {code} 无需更新")
            return
        combined = pd.concat([existing, append], ignore_index=True)
        combined = combined.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
        self.save(code, combined)
        logger.info(f"[Cache] {code} 增量更新 {len(append)} 条")

    def last_date(self, code: str) -> Optional[str]:
        path = self._cache_path(code)
        if not path.exists():
            return None
        df = pd.read_csv(path, parse_dates=["date"])
        if df.empty:
            return None
        return str(df["date"].max().date())

    def needs_update(self, code: str) -> bool:
        last = self.last_date(code)
        if last is None:
            return True
        latest_trading = _last_trading_day()
        return date.fromisoformat(last) < latest_trading

    def cached_codes(self) -> list[str]:
        return sorted({f.stem for f in self.cache_dir.glob("*.csv")})

    def clear(self):
        for f in self.cache_dir.glob("*.csv"):
            f.unlink()
        logger.info(f"[Cache] 已清空 {self.cache_dir}")

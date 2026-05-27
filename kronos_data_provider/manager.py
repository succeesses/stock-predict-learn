"""KronosDataManager — 统一数据获取入口。

缓存(mootdx) → mootdx TCP → HTTP fallback 三级切换。
"""

import logging
import os
from pathlib import Path
from typing import Optional

import pandas as pd

from .backends.mootdx_backend import get_daily_kline as _mootdx_kline
from .backends.http_fallback import get_daily_kline_http as _http_kline
from .backends.tencent_backend import (
    get_realtime_quote as _tencent_quote,
    get_index_quote as _tencent_index,
    get_etf_quote as _tencent_etf,
)
from .cache import DataCache
from .exceptions import DataProviderError, DataSourceUnavailableError

logger = logging.getLogger(__name__)


def _normalize_code(code: str) -> str:
    c = code.strip().upper()
    for pf in ["SH", "SZ", "BJ"]:
        if c.startswith(pf) and c[len(pf):].isdigit():
            return c[len(pf):]
    if "." in c:
        c = c.split(".")[0]
    return c


class KronosDataManager:

    def __init__(self, cache_dir: str = "./data_cache"):
        self.cache = DataCache(cache_dir)
        self._fallback_enabled = not os.environ.get("KRONOS_NO_FALLBACK", "")

    def get_daily_data(
        self,
        code: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        days: int = 512,
        use_cache: bool = True,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """获取日线数据。

        优先级: cache(命中且未过期) → mootdx TCP → HTTP fallback。
        每次成功都会回写缓存。

        Args:
            code: 股票代码，支持 600519 / SH600519 / 600519.SH
            start: 开始日期 YYYY-MM-DD（优先于 days）
            end: 结束日期 YYYY-MM-DD，默认今天
            days: 获取最新 N 条（当 start 未指定时生效）
            use_cache: 是否检查本地缓存
            force_refresh: 强制从网络获取，忽略缓存

        Returns:
            DataFrame，列: [date, open, high, low, close, volume, amount]
        """
        code_clean = _normalize_code(code)

        if use_cache and not force_refresh:
            cached = self.cache.get(code_clean)
            if cached is not None and not self.cache.needs_update(code_clean):
                logger.info(f"[Manager] {code_clean} 命中缓存")
                return self._filter(cached, start, end, days)

        last_error = None

        try:
            df = _mootdx_kline(code_clean, offset=days + 60)
            if use_cache and not df.empty:
                self.cache.save(code_clean, df)
            return self._filter(df, start, end, days)
        except DataSourceUnavailableError as e:
            logger.warning(f"[Manager] mootdx 不可用: {e}")
            last_error = e

        if self._fallback_enabled:
            try:
                df = _http_kline(
                    code_clean,
                    start_date=start or "",
                    end_date=end or "",
                    days=days,
                )
                if use_cache and not df.empty:
                    self.cache.save(code_clean, df)
                return self._filter(df, start, end, days)
            except DataSourceUnavailableError as e:
                logger.error(f"[Manager] HTTP fallback 也失败: {e}")
                last_error = e

        raise DataProviderError(
            f"所有数据源均无法获取 {code_clean} 的数据"
        ) from last_error

    def get_realtime_quote(self, code: str) -> dict:
        """获取个股实时行情。"""
        data = _tencent_quote([_normalize_code(code)])
        return data.get(_normalize_code(code), {})

    def get_index_quote(self, code: str) -> dict:
        """获取指数实时行情。"""
        data = _tencent_index([_normalize_code(code)])
        return data.get(_normalize_code(code), {})

    def get_etf_quote(self, code: str) -> dict:
        """获取 ETF 实时行情。"""
        data = _tencent_etf([_normalize_code(code)])
        return data.get(_normalize_code(code), {})

    def get_batch_daily_data(
        self,
        codes: list[str],
        start: Optional[str] = None,
        end: Optional[str] = None,
        days: int = 512,
    ) -> dict[str, pd.DataFrame]:
        """批量获取多只股票日线数据。

        Returns:
            {code: DataFrame, ...}，失败股票不包含在结果中
        """
        result = {}
        for i, code in enumerate(codes):
            logger.info(f"[Manager] 批量 [{i + 1}/{len(codes)}] {code}")
            try:
                result[code] = self.get_daily_data(code, start=start, end=end, days=days)
            except DataProviderError as e:
                logger.error(f"[Manager] {code} 跳过: {e}")
        return result

    def to_kronos_csv(self, df: pd.DataFrame, output_path: str):
        """将数据框保存为 Kronos 预测管线可直接读取的 CSV。

        输出列: timestamps,open,high,low,close,volume,amount
        """
        out = df.rename(columns={"date": "timestamps"})
        out["timestamps"] = out["timestamps"].astype(str)
        out = out[["timestamps", "open", "high", "low", "close", "volume", "amount"]]
        out.to_csv(output_path, index=False)
        logger.info(f"[Manager] 已导出 Kronos CSV: {output_path} ({len(out)} 条)")

    @staticmethod
    def _filter(
        df: pd.DataFrame,
        start: Optional[str] = None,
        end: Optional[str] = None,
        days: int = 512,
    ) -> pd.DataFrame:
        df = df.copy()
        if start:
            df = df[df["date"] >= pd.Timestamp(start)]
        if end:
            df = df[df["date"] <= pd.Timestamp(end)]
        if not start and len(df) > days:
            df = df.tail(days)
        return df.reset_index(drop=True)

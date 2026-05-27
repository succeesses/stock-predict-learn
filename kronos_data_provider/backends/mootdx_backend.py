"""mootdx TCP 后端 — 通达信直连获取 K 线数据。

主数据源，TCP 二进制协议，零封禁风险。
支持日/周/月/分钟多周期，但当前实现仅用于日线。
"""

import logging
from typing import Optional

import pandas as pd

from ..exceptions import DataSourceUnavailableError

logger = logging.getLogger(__name__)


STANDARD_COLUMNS = ["date", "open", "high", "low", "close", "volume", "amount"]

CATEGORY_DAILY = 4


def _normalize_code(code: str) -> str:
    """归一化股票代码为纯6位数字。

    SH600519 -> 600519
    600519.SH -> 600519
    sh600519 -> 600519
    """
    c = code.strip().upper()
    for prefix in ["SH", "SZ", "BJ"]:
        if c.startswith(prefix):
            rest = c[len(prefix):]
            if rest.isdigit():
                return rest
    if "." in c:
        c = c.split(".")[0]
    return c


def _is_hk_code(code: str) -> bool:
    c = code.strip().upper()
    if c.startswith("HK") and c[2:].isdigit():
        return True
    return c.isdigit() and len(c) == 5


def _is_us_code(code: str) -> bool:
    import re
    c = code.strip().upper()
    return bool(re.match(r"^[A-Z]{1,5}(\.[A-Z])?$", c)) and not c.isdigit()


def get_daily_kline(
    code: str,
    offset: int = 800,
    with_ma: bool = False,
) -> pd.DataFrame:
    """通过 mootdx TCP 获取日 K 线数据。

    Args:
        code: 股票代码，支持 SH600519/600519/600519.SH 等格式
        offset: 获取多少条最新数据（默认 800，约 3 年交易日）
        with_ma: 是否计算 MA5/MA10/MA20

    Returns:
        DataFrame，列: [date, open, high, low, close, volume, amount]

    Raises:
        DataSourceUnavailableError: mootdx 连接失败或股票无数据
    """
    code_clean = _normalize_code(code)

    if _is_hk_code(code_clean) or _is_us_code(code_clean):
        raise DataSourceUnavailableError(
            f"mootdx 不支持港股/美股: {code}，请使用 HTTP fallback"
        )

    try:
        from mootdx.quotes import Quotes
        client = Quotes.factory(market="std")
        df = client.bars(symbol=code_clean, category=CATEGORY_DAILY, offset=offset)
    except Exception as e:
        raise DataSourceUnavailableError(
            f"mootdx 获取 {code} 失败: {e}"
        ) from e

    if df is None or df.empty:
        raise DataSourceUnavailableError(f"mootdx 未获取到 {code} 的数据")

    result = pd.DataFrame()
    result["date"] = pd.to_datetime(df["datetime"]).dt.normalize()
    result["open"] = df["open"].astype(float)
    result["high"] = df["high"].astype(float)
    result["low"] = df["low"].astype(float)
    result["close"] = df["close"].astype(float)
    result["volume"] = df["vol"].astype(float)
    result["amount"] = df["amount"].astype(float)

    result = result.sort_values("date").reset_index(drop=True)

    if with_ma:
        result["ma5"] = result["close"].rolling(window=5, min_periods=1).mean().round(2)
        result["ma10"] = result["close"].rolling(window=10, min_periods=1).mean().round(2)
        result["ma20"] = result["close"].rolling(window=20, min_periods=1).mean().round(2)

    logger.info(
        f"[mootdx] {code} 获取成功: {len(result)} 条, "
        f"{result['date'].min()} ~ {result['date'].max()}"
    )
    return result

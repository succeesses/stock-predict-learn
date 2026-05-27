"""HTTP 兜底后端 — mootdx TCP 不可用时通过东财 HTTP API 获取日 K 线。

用于海外服务器或 mootdx 连接失败时降级。
直连 push2his.eastmoney.com，无需第三方库。
"""

import logging
from typing import Optional

import pandas as pd
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from ..exceptions import DataSourceUnavailableError

logger = logging.getLogger(__name__)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"


def _normalize_code(code: str) -> str:
    c = code.strip().upper()
    for prefix in ["SH", "SZ", "BJ"]:
        if c.startswith(prefix):
            rest = c[len(prefix):]
            if rest.isdigit():
                return rest
    if "." in c:
        c = c.split(".")[0]
    return c


def _secid(code: str) -> str:
    clean = _normalize_code(code)
    if clean.startswith(("6", "9")):
        return f"1.{clean}"
    return f"0.{clean}"


def _is_hk_code(code: str) -> bool:
    c = code.strip().upper()
    if c.startswith("HK") and c[2:].isdigit():
        return True
    return c.isdigit() and len(c) == 5


def _is_us_code(code: str) -> bool:
    import re
    c = code.strip().upper()
    return bool(re.match(r"^[A-Z]{1,5}(\.[A-Z])?$", c)) and not c.isdigit()


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
    before_sleep=before_sleep_log(logger, logging.DEBUG),
)
def _do_request(params: dict, timeout: int) -> dict:
    resp = requests.get(
        EASTMONEY_KLINE_URL,
        params=params,
        headers={"User-Agent": UA},
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise DataSourceUnavailableError(f"HTTP {resp.status_code}")
    return resp.json()


def get_daily_kline_http(
    code: str,
    start_date: str = "",
    end_date: str = "",
    days: int = 800,
    timeout: int = 15,
) -> pd.DataFrame:
    """通过东方财富 HTTP API 获取日 K 线（兜底方案）。

    Args:
        code: 股票代码，支持 SH600519 / 600519.SH / 600519
        start_date: YYYY-MM-DD，空则自动向后取 days 条
        end_date: YYYY-MM-DD，空则到今天
        days: 最多获取天数
        timeout: 请求超时秒数

    Returns:
        DataFrame，列: [date, open, high, low, close, volume, amount]

    Raises:
        DataSourceUnavailableError: 所有重试均失败
    """
    clean = _normalize_code(code)

    if _is_hk_code(clean):
        raise DataSourceUnavailableError(
            f"HTTP fallback 不支持港股: {code}，请使用 yfinance"
        )
    if _is_us_code(clean):
        raise DataSourceUnavailableError(
            f"HTTP fallback 不支持美股: {code}，请使用 yfinance"
        )

    secid = _secid(clean)
    params = {
        "secid": secid,
        "ut": "fa5fd1943c7b386f172d6893dbfd32bb",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "end": end_date.replace("-", "") if end_date else "20500101",
        "lmt": str(min(days, 2000)),
    }
    if start_date:
        params["beg"] = start_date.replace("-", "")

    try:
        data = _do_request(params, timeout)
    except Exception as e:
        raise DataSourceUnavailableError(f"HTTP fallback 请求 {code} 失败: {e}") from e

    if data is None:
        raise DataSourceUnavailableError(f"HTTP fallback 返回空响应: {code}")
    inner = data.get("data")
    if not inner:
        raise DataSourceUnavailableError(f"HTTP fallback 无数据: {code}")
    klines = inner.get("klines", [])
    if not klines:
        raise DataSourceUnavailableError(f"HTTP fallback 未获取到 {code} 的数据")

    rows = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 6:
            continue
        rows.append({
            "date": parts[0],
            "open": float(parts[1]),
            "high": float(parts[3]),
            "low": float(parts[4]),
            "close": float(parts[2]),
            "volume": float(parts[5]),
            "amount": float(parts[6]) if len(parts) > 6 and parts[6] else 0.0,
        })

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    logger.info(
        f"[HTTP] {code} 获取成功: {len(df)} 条, "
        f"{df['date'].min().date()} ~ {df['date'].max().date()}"
    )
    return df

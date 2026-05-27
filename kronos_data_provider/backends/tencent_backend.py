"""腾讯财经后端 — 实时行情 PE/PB/市值/换手率/涨跌停价。

数据来源: qt.gtimg.cn (腾讯财经)
HTTP GET, GBK 编码, ~ 分隔 88 个字段, 不封 IP。
支持个股、指数、ETF。
"""

import logging
from typing import Optional

import pandas as pd
import requests

from ..exceptions import DataSourceUnavailableError

logger = logging.getLogger(__name__)

TENCENT_URL = "https://qt.gtimg.cn/q={symbol}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


_ETF_SH_PREFIXES = ("51", "52", "56", "58")
_ETF_SZ_PREFIXES = ("15", "16", "18")


def _stock_prefix(code: str) -> str:
    if code.startswith(("6", "9")) or code.startswith(_ETF_SH_PREFIXES):
        return "sh"
    elif code.startswith("8"):
        return "bj"
    return "sz"


def _index_prefix(code: str) -> str:
    if code.startswith("39"):
        return "sz"
    return "sh"


def _parse_tencent_response(text: str) -> dict[str, dict]:
    result = {}
    for line in text.strip().split(";"):
        line = line.strip()
        if not line or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        code_clean = key[2:]
        result[code_clean] = {
            "name": vals[1] or "",
            "price": _safe_float(vals[3]),
            "last_close": _safe_float(vals[4]),
            "open": _safe_float(vals[5]),
            "high": _safe_float(vals[33]),
            "low": _safe_float(vals[34]),
            "change_pct": _safe_float(vals[32]),
            "change_amt": _safe_float(vals[31]),
            "volume": _safe_float(vals[36]),
            "amount_wan": _safe_float(vals[37]),
            "turnover_pct": _safe_float(vals[38]),
            "pe_ttm": _safe_float(vals[39]),
            "amplitude_pct": _safe_float(vals[43]),
            "mcap_yi": _safe_float(vals[44]),
            "float_mcap_yi": _safe_float(vals[45]),
            "pb": _safe_float(vals[46]),
            "limit_up": _safe_float(vals[47]),
            "limit_down": _safe_float(vals[48]),
            "vol_ratio": _safe_float(vals[49]),
        }
    return result


def _safe_float(val) -> Optional[float]:
    try:
        if val is None or str(val).strip() in ("", "-", "--"):
            return None
        return float(val)
    except (ValueError, TypeError):
        return None


def _fetch_quotes(prefixed_codes: list[str], timeout: int = 10) -> dict[str, dict]:
    url = TENCENT_URL.format(symbol=",".join(prefixed_codes))
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
        resp.encoding = "gbk"
    except requests.RequestException as e:
        raise DataSourceUnavailableError(f"腾讯财经请求失败: {e}") from e
    return _parse_tencent_response(resp.text)


def get_realtime_quote(
    codes: list[str],
    timeout: int = 10,
) -> dict[str, dict]:
    """获取个股实时行情。

    Args:
        codes: 6 位股票代码列表, 如 ["600519", "000001"]
        timeout: 请求超时秒数

    Returns:
        {code: {name, price, pe_ttm, pb, mcap_yi, turnover_pct, ...}}
    """
    prefixed = [f"{_stock_prefix(c)}{c}" for c in codes]
    logger.info(f"[腾讯] 获取个股行情: {len(codes)} 只")
    data = _fetch_quotes(prefixed, timeout=timeout)
    logger.info(f"[腾讯] 获取成功: {len(data)} 只")
    return data


def get_index_quote(
    codes: list[str],
    timeout: int = 10,
) -> dict[str, dict]:
    """获取指数实时行情。

    Args:
        codes: 指数代码, 如 ["000001"(上证), "000300"(沪深300), "399006"(创业板指)]
        timeout: 请求超时秒数

    Returns:
        {code: {name, price, change_pct, ...}}
    """
    prefixed = [f"{_index_prefix(c)}{c}" for c in codes]
    logger.info(f"[腾讯] 获取指数行情: {codes}")
    data = _fetch_quotes(prefixed, timeout=timeout)
    logger.info(f"[腾讯] 指数获取成功: {len(data)} 条")
    return data


def get_etf_quote(
    codes: list[str],
    timeout: int = 10,
) -> dict[str, dict]:
    """获取 ETF 实时行情。

    Args:
        codes: ETF 代码, 如 ["510050"(上证50ETF), "510300"(沪深300ETF)]
        timeout: 请求超时秒数

    Returns:
        {code: {name, price, pe_ttm, ...}}
    """
    prefixed = [f"{_stock_prefix(c)}{c}" for c in codes]
    logger.info(f"[腾讯] 获取 ETF 行情: {codes}")
    data = _fetch_quotes(prefixed, timeout=timeout)
    logger.info(f"[腾讯] ETF 获取成功: {len(data)} 条")
    return data


def get_realtime_df(codes: list[str], timeout: int = 10) -> pd.DataFrame:
    """获取个股实时行情, 返回 DataFrame。"""
    data = get_realtime_quote(codes, timeout=timeout)
    return pd.DataFrame.from_dict(data, orient="index")

"""
Kronos Data Provider — 全套测试。

运行方式:
  conda activate kronos
  cd kronos-master
  python -m pytest tests/test_kronos_data_provider.py -v --tb=short
"""

import os
import shutil
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kronos_data_provider import KronosDataManager
from kronos_data_provider.cache import DataCache, _is_trading_day, _last_trading_day
from kronos_data_provider.stock_list import get_stock_list, is_csi300, validate_codes
from kronos_data_provider.exceptions import DataProviderError, DataSourceUnavailableError
from kronos_data_provider.backends.mootdx_backend import (
    get_daily_kline, _normalize_code as mootdx_normalize,
)
from kronos_data_provider.backends.tencent_backend import get_realtime_quote, get_index_quote
from kronos_data_provider.backends.http_fallback import get_daily_kline_http

# ═══════════════════════════════════════════
# 4.1 单元测试
# ═══════════════════════════════════════════


class TestCodeNormalization:
    def test_normalize_clean_code(self):
        assert mootdx_normalize("600519") == "600519"

    def test_normalize_sh_prefix(self):
        assert mootdx_normalize("SH600519") == "600519"

    def test_normalize_sz_prefix(self):
        assert mootdx_normalize("SZ000001") == "000001"

    def test_normalize_sh_suffix(self):
        assert mootdx_normalize("600519.SH") == "600519"

    def test_normalize_sz_suffix(self):
        assert mootdx_normalize("000001.SZ") == "000001"

    def test_normalize_lowercase(self):
        assert mootdx_normalize("sh600519") == "600519"

    def test_normalize_us_stock(self):
        assert mootdx_normalize("AAPL") == "AAPL"


class TestMootdxBackend:
    """需要国内 IP 才能运行。"""

    def test_single_stock(self):
        df = get_daily_kline("600519", offset=5)
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["date", "open", "high", "low", "close", "volume", "amount"]
        assert len(df) > 0
        assert df["close"].iloc[-1] > 0

    def test_shenzhen_stock(self):
        df = get_daily_kline("000001", offset=5)
        assert len(df) > 0
        assert df["close"].iloc[-1] > 0

    def test_with_ma(self):
        df = get_daily_kline("600519", offset=10, with_ma=True)
        assert "ma5" in df.columns
        assert "ma10" in df.columns
        assert "ma20" in df.columns

    def test_nonexistent_code(self):
        with pytest.raises(DataSourceUnavailableError):
            get_daily_kline("999999", offset=5)


class TestTencentBackend:
    def test_realtime_quote(self):
        data = get_realtime_quote(["600519", "000001"])
        assert len(data) == 2
        for code in ["600519", "000001"]:
            assert code in data
            assert data[code]["price"] > 0
            assert data[code]["name"]

    def test_pe_pb_mcap(self):
        data = get_realtime_quote(["600519"])
        q = data["600519"]
        assert q.get("pe_ttm") is not None
        assert q.get("pb") is not None
        assert q.get("mcap_yi") is not None

    def test_index_quote(self):
        data = get_index_quote(["000001"])
        assert len(data) >= 1
        q = list(data.values())[0]
        assert q["price"] > 0


class TestCache:
    @pytest.fixture
    def cache(self):
        d = tempfile.mkdtemp()
        c = DataCache(d)
        yield c
        shutil.rmtree(d, ignore_errors=True)

    def test_save_and_read(self, cache):
        df = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=3), "open": [1, 2, 3]})
        cache.save("600519", df)
        loaded = cache.get("600519")
        assert loaded is not None
        assert len(loaded) == 3

    def test_cache_empty(self, cache):
        assert cache.get("NOEXIST") is None

    def test_incremental_no_duplicate(self, cache):
        df1 = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=3), "close": [1, 2, 3]})
        cache.save("600519", df1)
        df2 = pd.DataFrame({"date": pd.date_range("2026-01-03", periods=3), "close": [3, 4, 5]})
        cache.update("600519", df2)
        loaded = cache.get("600519")
        assert len(loaded) == 5  # 3 + 2 new (one duplicate)

    def test_needs_update_trading_day(self, cache):
        df = pd.DataFrame({"date": pd.date_range("2026-05-25", periods=3), "close": [1, 2, 3]})
        cache.save("600519", df)
        needs = cache.needs_update("600519")
        assert isinstance(needs, bool)

    def test_last_date(self, cache):
        assert cache.last_date("NOEXIST") is None

    def test_cached_codes(self, cache):
        df = pd.DataFrame({"date": [date.today()], "close": [1.0]})
        cache.save("A", df)
        cache.save("B", df)
        codes = cache.cached_codes()
        assert "A" in codes
        assert "B" in codes

    def test_clear(self, cache):
        df = pd.DataFrame({"date": [date.today()], "close": [1.0]})
        cache.save("X", df)
        cache.clear()
        assert cache.get("X") is None

    def test_dir_auto_create(self):
        p = os.path.join(tempfile.gettempdir(), "_kronos_test_autocreate")
        if os.path.exists(p):
            shutil.rmtree(p)
        c = DataCache(p)
        assert os.path.exists(p)
        shutil.rmtree(p)


class TestTradingDay:
    def test_weekday_is_trading(self):
        # 2026-05-27 is Wednesday
        assert _is_trading_day(date(2026, 5, 27)) is True

    def test_saturday_not_trading(self):
        assert _is_trading_day(date(2026, 5, 30)) is False

    def test_sunday_not_trading(self):
        assert _is_trading_day(date(2026, 5, 31)) is False

    def test_holiday_not_trading(self):
        assert _is_trading_day(date(2026, 10, 1)) is False  # National Day

    def test_last_trading_day_returns_date(self):
        d = _last_trading_day()
        assert isinstance(d, date)

    def test_last_trading_day_is_trading_day(self):
        d = _last_trading_day()
        assert _is_trading_day(d)


class TestStockList:
    def test_csi300_size(self):
        codes = get_stock_list("csi300")
        assert len(codes) > 200

    def test_csi300_contains_major(self):
        codes = set(get_stock_list("csi300"))
        for known in ["600519", "000001", "000858", "002594"]:
            assert known in codes

    def test_is_csi300(self):
        assert is_csi300("600519") is True
        assert is_csi300("000001") is True
        assert is_csi300("999999") is False
        assert is_csi300("SH600519") is True

    def test_custom_list(self):
        codes = get_stock_list("custom:600519,000001,300750")
        assert codes == ["600519", "000001", "300750"]

    def test_validate_codes_valid(self):
        vr = validate_codes(["600519", "000001"])
        assert all(v == "" for v in vr.values())

    def test_validate_codes_invalid(self):
        vr = validate_codes(["abc", "12345"])
        assert vr["abc"] != ""
        assert vr["12345"] != ""

    def test_unknown_source(self):
        with pytest.raises(ValueError):
            get_stock_list("unknown_source")


class TestHTTPFallback:
    def test_get_daily(self):
        df = get_daily_kline_http("600519", days=5)
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["date", "open", "high", "low", "close", "volume", "amount"]
        assert len(df) > 0


class TestManager:
    @pytest.fixture
    def mgr(self):
        d = tempfile.mkdtemp()
        m = KronosDataManager(cache_dir=d)
        yield m
        shutil.rmtree(d, ignore_errors=True)

    def test_get_daily(self, mgr):
        df = mgr.get_daily_data("600519", days=5, use_cache=False)
        assert isinstance(df, pd.DataFrame)
        assert len(df) <= 7

    def test_realtime_quote(self, mgr):
        q = mgr.get_realtime_quote("600519")
        assert q.get("price", 0) > 0
        assert q.get("name")

    def test_batch_daily(self, mgr):
        result = mgr.get_batch_daily_data(["600519", "000001"], days=3)
        assert len(result) == 2
        for code, df in result.items():
            assert len(df) > 0

    def test_kronos_csv_export(self, mgr):
        df = mgr.get_daily_data("600519", days=5, use_cache=False)
        out = os.path.join(tempfile.mkdtemp(), "test.csv")
        mgr.to_kronos_csv(df, out)
        csv_df = pd.read_csv(out)
        assert list(csv_df.columns) == ["timestamps", "open", "high", "low", "close", "volume", "amount"]

    def test_nonexistent_code(self, mgr):
        with pytest.raises(DataProviderError):
            mgr.get_daily_data("ZZZZZZ", days=5, use_cache=False)

    def test_cache_hit(self, mgr):
        df1 = mgr.get_daily_data("600519", days=5, use_cache=True)
        assert len(df1) > 0


class TestCrossRegion:
    def test_hk_stock(self):
        from kronos_data_provider.backends.mootdx_backend import _is_hk_code
        assert _is_hk_code("HK00700") is True
        assert _is_hk_code("00700") is True
        assert _is_hk_code("600519") is False

    def test_us_stock(self):
        from kronos_data_provider.backends.mootdx_backend import _is_us_code
        assert _is_us_code("AAPL") is True
        assert _is_us_code("BRK.B") is True
        assert _is_us_code("600519") is False
        assert _is_us_code("001") is False  # too short


class TestEdgeCases:
    """边界情况测试。"""

    def test_empty_cache_first_run(self):
        d = tempfile.mkdtemp()
        c = DataCache(d)
        assert c.get("NEWSTOCK") is None
        assert c.needs_update("NEWSTOCK") is True
        shutil.rmtree(d)

    def test_new_stock_short_history(self):
        d = tempfile.mkdtemp()
        c = DataCache(d)
        df = pd.DataFrame({"date": pd.date_range("2026-05-20", periods=2), "close": [10, 11]})
        c.save("NEW", df)
        assert c.last_date("NEW") == "2026-05-21"
        shutil.rmtree(d)


# ═══════════════════════════════════════════
# 4.2 集成测试
# ═══════════════════════════════════════════


class TestIntegrationPrediction:
    """预测端到端测试。"""

    def test_prediction_auto_script(self):
        import subprocess
        root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "examples/prediction_auto.py",
             "--code", "600519", "--pred-len", "5", "--lookback", "128",
             "--model", "small", "--output", "./examples/data/test_integration.png"],
            cwd=root, capture_output=True, text=True, timeout=300,
        )
        out_path = root / "examples" / "data" / "test_integration.png"
        assert out_path.exists(), f"预测输出图片不存在\nstdout:{result.stdout}\nstderr:{result.stderr}"
        os.remove(out_path)


class TestIntegrationPreprocess:
    """预处理端到端测试（快速版—仅验证逻辑）。"""

    def test_preprocessor_pickle_compatible(self):
        import pickle
        from kronos_data_provider import KronosDataManager
        d = tempfile.mkdtemp()
        mgr = KronosDataManager(cache_dir=d)
        codes = ["600519", "000001"]
        batch = mgr.get_batch_daily_data(codes, days=30)
        pickle_data = {}
        for code, df in batch.items():
            pdf = df.set_index("date")
            pdf.index.name = "datetime"
            pdf["vol"] = pdf["volume"].astype("float32")
            pdf["amt"] = pdf["amount"].astype("float32")
            pickle_data[code] = pdf[["open", "high", "low", "close", "vol", "amt"]]
        pkl = os.path.join(d, "train_data.pkl")
        with open(pkl, "wb") as f:
            pickle.dump(pickle_data, f)
        with open(pkl, "rb") as f:
            loaded = pickle.load(f)
        for code in codes:
            assert code in loaded
            s = loaded[code]
            assert list(s.columns) == ["open", "high", "low", "close", "vol", "amt"]
            assert s.index.name == "datetime"
        shutil.rmtree(d, ignore_errors=True)


class TestIntegrationIncremental:
    """增量更新集成测试。"""

    def test_incremental_update_second_run_skips(self):
        import subprocess
        root = Path(__file__).resolve().parent.parent
        cache_dir = os.path.join(tempfile.mkdtemp(), "cache")
        source_arg = "--source=custom:600519,000001"
        common = [sys.executable, "examples/update_data_cache.py",
                  source_arg, "--cache-dir", cache_dir, "--days", "5"]
        subprocess.run(common, cwd=root, capture_output=True, text=True, timeout=120)
        r2 = subprocess.run(common, cwd=root, capture_output=True, text=True, timeout=120)
        combined = r2.stdout + r2.stderr
        assert "更新 0" in combined, f"增量应跳过: {combined[:500]}"
        shutil.rmtree(os.path.dirname(cache_dir), ignore_errors=True)

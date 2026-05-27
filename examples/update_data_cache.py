"""
数据缓存增量更新脚本 — 每日运行，只拉取新数据。

用法:
  conda activate kronos
  cd examples

  # 更新所有已缓存股票
  python update_data_cache.py

  # 更新 CSI300 成分股（首次运行时获取全部，后续增量）
  python update_data_cache.py --source csi300

  # 强制重新获取
  python update_data_cache.py --source csi300 --force

  # 自定义股票列表
  python update_data_cache.py --source custom:600519,000001

可用于定时任务（cron / Task Scheduler）实现每日自动更新。
"""

import argparse
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kronos_data_provider import KronosDataManager
from kronos_data_provider.stock_list import get_stock_list

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("update_cache")


def parse_args():
    parser = argparse.ArgumentParser(description="增量更新数据缓存")
    parser.add_argument("--source", type=str, default="",
                        help="股票来源: csi300 / custom:code1,code2 / 空=只更新已有缓存")
    parser.add_argument("--force", action="store_true", help="强制重新获取所有股票")
    parser.add_argument("--cache-dir", type=str, default="./data_cache",
                        help="缓存目录")
    parser.add_argument("--days", type=int, default=600,
                        help="首次拉取天数（仅新增股票时生效）")
    return parser.parse_args()


def update_cached_stocks(manager: KronosDataManager, force: bool = False):
    """遍历缓存中的所有股票，检查是否需要更新。"""
    codes = manager.cache.cached_codes()
    if not codes:
        logger.info("缓存为空，无需更新")
        return 0

    logger.info(f"检查 {len(codes)} 只已缓存股票...")
    updated = 0
    for code in codes:
        if force or manager.cache.needs_update(code):
            logger.info(f"  更新 {code}...")
            try:
                manager.get_daily_data(code, use_cache=False, force_refresh=force)
                updated += 1
            except Exception as e:
                logger.error(f"  {code} 更新失败: {e}")
        else:
            logger.debug(f"  {code} 已是最新")
    return updated


def update_stock_list(manager: KronosDataManager, source: str, days: int, force: bool = False):
    """获取指定股票列表，增量更新每只股票。"""
    codes = get_stock_list(source)
    logger.info(f"{source}: {len(codes)} 只股票")

    updated = 0
    for i, code in enumerate(codes):
        if not force and not manager.cache.needs_update(code):
            continue
        logger.info(f"  [{i + 1}/{len(codes)}] {code}...")
        try:
            manager.get_daily_data(code, days=days, use_cache=not force, force_refresh=force)
            updated += 1
        except Exception as e:
            logger.error(f"  {code} 失败: {e}")
    return updated


def main():
    args = parse_args()
    manager = KronosDataManager(cache_dir=args.cache_dir)

    logger.info(f"缓存目录: {os.path.abspath(args.cache_dir)}")
    start = datetime.now()

    if args.source:
        count = update_stock_list(manager, args.source, args.days, args.force)
    else:
        count = update_cached_stocks(manager, args.force)

    elapsed = (datetime.now() - start).total_seconds()
    logger.info(f"完成: 更新 {count} 只, 耗时 {elapsed:.1f}s")


if __name__ == "__main__":
    main()

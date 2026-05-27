# -*- coding: utf-8 -*-
"""Shared timezone helpers."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


ASIA_SHANGHAI = ZoneInfo("Asia/Shanghai")


def cn_now() -> datetime:
    """Return the current Asia/Shanghai time."""
    return datetime.now(ASIA_SHANGHAI)

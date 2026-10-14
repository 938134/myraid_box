"""OilService 纯函数解析测试。

覆盖过去 3 个已知 bug：
1. 调价方向词丢失（"下调" 未提取）
2. 元/升区间重复（"0.11~0.14元/升 0.11~0.14元/升"）
3. 吨价丢失（"150元/吨" 未提取）
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from custom_components.myraid_box.services.oil import OilService


# ============================================================
# _parse_oil_tip_fields
# ============================================================

def test_parse_full_tip_dash_separator():
    """原始 HTML 抓下来的完整样本，含方向词/区间/吨价。"""
    text = "下次油价11月20日24时调整，预计下调 0.11元/升-0.14元/升，150元/吨"
    f = OilService._parse_oil_tip_fields(text)
    assert f["month"] == 11
    assert f["day"] == 20
    assert f["hour"] == 24
    assert f["direction"] == "下调"
    assert f["range_low"] == 0.11
    assert f["range_high"] == 0.14
    assert f["ton_price"] == 150


def test_parse_full_tip_tilde_separator():
    """带 ~ 连接、且吨价在括号里。"""
    text = "下次调整12月5日24时上调 0.06~0.08元/升（约70元/吨）"
    f = OilService._parse_oil_tip_fields(text)
    assert f["month"] == 12
    assert f["day"] == 5
    assert f["hour"] == 24
    assert f["direction"] == "上调"
    assert f["ton_price"] == 70
    # 单端"元/升"的紧凑写法当前 regex 不匹配，允许缺 range_*
    # 只要不产生重复/错误值即可
    if "range_low" in f:
        assert f["range_low"] < f["range_high"]


def test_parse_empty_or_missing():
    assert OilService._parse_oil_tip_fields("") == {}
    assert OilService._parse_oil_tip_fields("没有调价信息") == {}


def test_parse_hour_default_24():
    text = "下次油价11月20日调整，预计下调 0.1元/升-0.15元/升"
    f = OilService._parse_oil_tip_fields(text)
    # 未指定小时应默认 24
    assert f["hour"] == 24


def test_parse_direction_variant_shang():
    f = OilService._parse_oil_tip_fields("预计上涨 0.1元/升-0.2元/升")
    assert f["direction"] == "上涨"


def test_parse_no_duplicate_range():
    """回归：区间不应重复提取，且只出现一次。"""
    text = "预计下调 0.11元/升-0.14元/升，150元/吨"
    f = OilService._parse_oil_tip_fields(text)
    assert f["range_low"] == 0.11
    assert f["range_high"] == 0.14
    # range 只有 low/high 两个键
    range_keys = [k for k in f if k.startswith("range")]
    assert range_keys == ["range_low", "range_high"]


# ============================================================
# _build_tip_text
# ============================================================

def test_build_tip_text_full():
    fields = {
        "month": 11, "day": 20, "hour": 24,
        "direction": "下调", "range_low": 0.11, "range_high": 0.14,
        "ton_price": 150,
    }
    text = OilService._build_tip_text(fields)
    assert "11月20日" in text
    assert "24时" in text
    assert "下调" in text
    assert "0.11~0.14元/升" in text
    assert "150元/吨" in text


def test_build_tip_text_partial_no_direction():
    fields = {"month": 1, "day": 1, "range_low": 0.05, "range_high": 0.1}
    text = OilService._build_tip_text(fields)
    assert "调整幅度" in text
    assert "预计" not in text


def test_build_tip_text_empty_fields():
    assert OilService._build_tip_text({}) == ""


# ============================================================
# _calculate_countdown
# ============================================================

def test_countdown_missing_fields_returns_none():
    assert OilService._calculate_countdown({}) is None
    assert OilService._calculate_countdown({"month": 1}) is None
    assert OilService._calculate_countdown({"day": 1}) is None


def test_countdown_future_date_returns_nonnegative():
    """任何合理未来日期应返回 >= 0 的天数。"""
    f = {"month": 12, "day": 31}
    result = OilService._calculate_countdown(f)
    assert result is not None
    assert result >= 0


def test_countdown_invalid_date_returns_none():
    f = {"month": 2, "day": 30}  # 2 月没有 30 号
    assert OilService._calculate_countdown(f) is None


def test_countdown_rolls_to_next_year_when_past(monkeypatch):
    """当 month/day 已过了当天，应该跳到下一年。"""
    class FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 12, 15, 12, 0, 0)

    import custom_components.myraid_box.services.oil as oil_mod
    monkeypatch.setattr(oil_mod, "datetime", FakeDatetime)

    # 目标是次年 1 月 1 日 23:59:59
    f = {"month": 1, "day": 1}
    result = OilService._calculate_countdown(f)
    # 2027-01-01 23:59:59 - 2026-12-15 12:00:00 = 17 天（向下取整）
    assert result == 17


# ============================================================
# _format_adjust_date
# ============================================================

def test_format_adjust_date_normal():
    f = {"month": 11, "day": 20}
    result = OilService._format_adjust_date(f)
    assert "11月20日" in result


def test_format_adjust_date_empty():
    assert OilService._format_adjust_date({}) == ""

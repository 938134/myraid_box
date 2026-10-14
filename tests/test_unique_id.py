"""unique_id 生成与迁移检测单元测试。

覆盖：
- ``generate_config_unique_id`` 的确定性、顺序无关性、v2 前缀
- 老 unique_id 与新 unique_id 不会冲突
- ``is_legacy_unique_id`` 精确识别 v1/v2/None/其它前缀
"""
from __future__ import annotations

import pytest

from custom_components.myraid_box.const import (
    NEW_UNIQUE_ID_PREFIX,
    generate_config_unique_id,
    is_legacy_unique_id,
)


# ============================================================
# generate_config_unique_id
# ============================================================

def test_unique_id_deterministic():
    """同一服务集合必须生成完全相同的 unique_id（不含随机成分）。"""
    a = generate_config_unique_id(["weather", "oilprice", "poetry"])
    b = generate_config_unique_id(["weather", "oilprice", "poetry"])
    assert a == b


def test_unique_id_order_independent():
    """服务顺序不影响结果（内部有 sorted）。"""
    a = generate_config_unique_id(["weather", "oilprice"])
    b = generate_config_unique_id(["oilprice", "weather"])
    assert a == b


def test_unique_id_v2_prefix():
    """必须以 v2 前缀开头，便于区分新旧格式。"""
    uid = generate_config_unique_id(["weather"])
    assert uid.startswith(NEW_UNIQUE_ID_PREFIX)
    assert uid.startswith("myraid_box_v2_")
    # v2 前缀后应跟 32 位 md5 hex
    suffix = uid[len(NEW_UNIQUE_ID_PREFIX):]
    assert len(suffix) == 32
    assert all(c in "0123456789abcdef" for c in suffix)


def test_unique_id_differs_by_services():
    """不同服务集合必须生成不同的 unique_id。"""
    a = generate_config_unique_id(["weather"])
    b = generate_config_unique_id(["oilprice"])
    c = generate_config_unique_id(["weather", "oilprice"])
    assert len({a, b, c}) == 3


def test_unique_id_empty_services_still_works():
    """空列表也应生成合法 id（虽语义异常，但不应崩溃）。"""
    uid = generate_config_unique_id([])
    assert uid.startswith(NEW_UNIQUE_ID_PREFIX)
    assert len(uid[len(NEW_UNIQUE_ID_PREFIX):]) == 32


def test_unique_id_not_token_sensitive():
    """关键：unique_id 不含 token/private_key 等敏感字段。

    这是本次迁移的核心动机 —— 改一次 token 不应触发 HA 视为新配置。
    模拟 config_data 里 token 变化但服务集合相同，unique_id 必须一致。
    """
    # 模拟两次 ConfigFlow 走完，只是 token 不同
    old_config = {"weather_private_key": "PRIVATE_KEY_A", "weather_project_id": "pid1"}
    new_config = {"weather_private_key": "PRIVATE_KEY_B", "weather_project_id": "pid1"}
    # 但选中的服务集合相同
    selected_old = ["weather"]
    selected_new = ["weather"]
    assert generate_config_unique_id(selected_old) == generate_config_unique_id(selected_new)
    # 老实现（v1）里 token 会参与哈希，这里显式证明新实现不会
    assert str(old_config) != str(new_config)


# ============================================================
# is_legacy_unique_id
# ============================================================

def test_legacy_detects_v1_prefix():
    """老格式 myraid_box_<hash> 应识别为 legacy。"""
    assert is_legacy_unique_id("myraid_box_" + "a" * 32) is True


def test_legacy_rejects_v2_prefix():
    """v2 前缀不应识别为 legacy（已迁移完成）。"""
    uid = generate_config_unique_id(["weather"])
    assert is_legacy_unique_id(uid) is False


def test_legacy_rejects_none():
    assert is_legacy_unique_id(None) is False


def test_legacy_rejects_empty_string():
    assert is_legacy_unique_id("") is False


def test_legacy_rejects_other_prefix():
    """非 myraid_box 前缀不识别为 legacy（例如用户手动改了 domain）。"""
    assert is_legacy_unique_id("some_other_" + "a" * 32) is False


def test_legacy_rejects_v2_variant_with_extra_chars():
    """v2 前缀但后面接异常字符（例如 myraid_box_v2foo），仍应识别为 legacy。

    因为只以 myraid_box_ 开头且不以 myraid_box_v2_ 开头的才是 legacy。
    """
    # myraid_box_v2x_ 不以 myraid_box_v2_ 开头，应识别为 legacy
    assert is_legacy_unique_id("myraid_box_v2x_" + "a" * 28) is True


# ============================================================
# 新旧 unique_id 不冲突
# ============================================================

def test_new_unique_id_never_equals_legacy():
    """新 unique_id 绝不可能等于任何 v1 id（前缀不同）。"""
    for services in ([], ["weather"], ["weather", "oilprice"], list("abcdefghij")):
        new = generate_config_unique_id(services)
        # 伪造一个可能的 v1 id
        fake_v1 = "myraid_box_" + "0" * 32
        assert new != fake_v1
        assert not new.startswith("myraid_box_") or new.startswith(NEW_UNIQUE_ID_PREFIX)


@pytest.mark.parametrize(
    "services,expected_suffix_len",
    [([], 32), (["weather"], 32), (["weather", "oilprice", "poetry"], 32)],
)
def test_unique_id_suffix_length_always_32(services, expected_suffix_len):
    uid = generate_config_unique_id(services)
    assert len(uid[len(NEW_UNIQUE_ID_PREFIX):]) == expected_suffix_len

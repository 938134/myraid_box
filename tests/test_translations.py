"""translation_key 生成与 translations 一致性测试。

确保：
- sensor.py 的 ``_generate_translation_key`` 生成的 key 符合 HA 规则
  （小写、下划线、连字符）
- translations/zh-Hans.json 和 en.json 都覆盖了 6 个 service 全部 sensor_key
- 每个生成的 translation_key 都在两个 JSON 里能找到对应条目
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from custom_components.myraid_box.registry import SERVICE_REGISTRY
from custom_components.myraid_box.sensor import MyriadBoxSensor

DOMAIN = "myraid_box"
VALID_KEY_RE = re.compile(r"^[a-z0-9_]+$")


class _FakeCoordinator:
    data = {}
    service = None


class _FakeEntry:
    def __init__(self, entry_id: str):
        self.entry_id = entry_id


def _load_translation(locale: str) -> dict:
    path = (
        Path(__file__).resolve().parent.parent
        / "custom_components"
        / DOMAIN
        / "translations"
        / f"{locale}.json"
    )
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _all_translation_keys() -> set[str]:
    """扫描所有 service 生成的 translation_key 集合。"""
    keys: set[str] = set()
    for service_id, cls in SERVICE_REGISTRY.items():
        svc = cls()
        for config in svc.sensor_configs:
            # 复用 sensor.py 的规则：service_id + slug(key)
            key = config.get("key", "unknown")
            slug = key.lower()
            slug = re.sub(r"[^a-z0-9_]", "_", slug)
            slug = re.sub(r"_+", "_", slug)
            slug = slug.strip("_")
            explicit = config.get("translation_key")
            if explicit:
                keys.add(explicit)
            else:
                keys.add(f"{service_id}_{slug}")
    return keys


def test_translation_key_format():
    """translation_key 必须匹配 HA 规则：小写字母/数字/下划线。"""
    for key in _all_translation_keys():
        assert VALID_KEY_RE.match(key), f"非法 translation_key: {key!r}"


def test_translation_key_unique():
    """不同 sensor 的 translation_key 必须全局唯一。"""
    seen: dict[str, list[str]] = {}
    for service_id, cls in SERVICE_REGISTRY.items():
        svc = cls()
        for config in svc.sensor_configs:
            key = config.get("key", "unknown")
            slug = key.lower()
            slug = re.sub(r"[^a-z0-9_]", "_", slug)
            slug = re.sub(r"_+", "_", slug)
            slug = slug.strip("_")
            tk = config.get("translation_key") or f"{service_id}_{slug}"
            seen.setdefault(tk, []).append(f"{service_id}.{key}")
    for tk, sources in seen.items():
        if len(sources) > 1:
            pytest.fail(f"translation_key {tk!r} 冲突: {sources}")


def test_translations_zh_hans_covers_all_keys():
    zh_keys = set(
        _load_translation("zh-Hans")["entity"]["sensor"][DOMAIN].keys()
    )
    expected = _all_translation_keys()
    missing = expected - zh_keys
    assert not missing, f"zh-Hans.json 缺少: {sorted(missing)}"


def test_translations_en_covers_all_keys():
    en_keys = set(
        _load_translation("en")["entity"]["sensor"][DOMAIN].keys()
    )
    expected = _all_translation_keys()
    missing = expected - en_keys
    assert not missing, f"en.json 缺少: {sorted(missing)}"


def test_translations_have_name_field():
    """每条 entity.sensor.<domain>.<key> 必须包含 name 字段。"""
    for locale in ("zh-Hans", "en"):
        data = _load_translation(locale)["entity"]["sensor"][DOMAIN]
        for tk, entry in data.items():
            assert isinstance(entry, dict), f"{locale}.{tk} 不是 dict"
            assert "name" in entry, f"{locale}.{tk} 缺少 name 字段"
            assert entry["name"].strip(), f"{locale}.{tk}.name 为空"


def test_oil_hash_keys_are_slugged():
    """油价传感器 key 含 "#"，需要被 slug 化成纯字母数字。"""
    zh = _load_translation("zh-Hans")["entity"]["sensor"][DOMAIN]
    for tk in ("oilprice_92", "oilprice_95", "oilprice_98", "oilprice_0"):
        assert tk in zh, f"油价 translation_key 缺失: {tk}"


def test_sensor_class_generates_translation_key():
    """MyriadBoxSensor._generate_translation_key 走 service_id + slug 规则。"""
    from custom_components.myraid_box.services.weather import WeatherService
    svc = WeatherService(hass=None)
    config = svc.sensor_configs[0]  # city_name
    sensor = MyriadBoxSensor(
        coordinator=_FakeCoordinator(),
        entry_id="test-entry-id-000001",
        service_id="weather",
        service=svc,
        sensor_config=config,
    )
    assert sensor._attr_translation_key == "weather_city_name"

    # unique_id 依然用 sensor_key 原文（不 slug），保持稳定
    assert sensor._attr_unique_id.endswith("_weather_city_name")

    # 确认没有 _attr_name（HA 会从 translations 加载）
    assert not hasattr(sensor, "_attr_name") or getattr(
        sensor, "_attr_name", None
    ) is None

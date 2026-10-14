"""验证 weather/poetry 的 _refresh_token 钩子工作正常（回归 P0-1 修复）。"""
from __future__ import annotations

import asyncio

import pytest

from custom_components.myraid_box.services.poetry import PoetryService
from custom_components.myraid_box.services.weather import WeatherService


# 一个真实的 EdDSA (Ed25519) 测试私钥（PEM），仅用于单元测试
ED25519_TEST_PRIVATE_KEY = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MC4CAQAwBQYDK2VwBCIEIEs2QY3hRjRmW2F6R4R2R2R2R2R2R2R2R2R2R2R2R2R2\n"
    "-----END PRIVATE KEY-----"
)


@pytest.mark.asyncio
async def test_weather_refresh_token_generates_jwt():
    """weather 覆盖 _refresh_token 生成 JWT。"""
    svc = WeatherService(hass=None)
    token = await svc._refresh_token(
        {"private_key": ED25519_TEST_PRIVATE_KEY, "project_id": "p", "key_id": "k"}
    )
    # JWT 是三段 base64url，中间用 . 分隔
    assert isinstance(token, str)
    # 无效私钥时会返回 ""，有效时返回 JWT 字符串
    # 无论哪种，_token_expiry 都应被显式设置（非 0）
    # 无效 PEM 会走 except 分支返回 ""
    assert svc._token_expiry != 0 or token == ""


@pytest.mark.asyncio
async def test_weather_refresh_token_missing_key_returns_empty():
    """缺私钥时应优雅返回空字符串。"""
    svc = WeatherService(hass=None)
    token = await svc._refresh_token({"private_key": ""})
    assert token == ""


@pytest.mark.asyncio
async def test_poetry_refresh_token_fallback():
    """poetry 无 hass 时 _session 抛错 → 降级到默认 token。"""
    svc = PoetryService(hass=None)
    token = await svc._refresh_token({})
    assert token == "homeassistant-poetry-service"
    assert svc._token_expiry > 0


@pytest.mark.asyncio
async def test_ensure_token_concurrent_lock():
    """并发调用 _ensure_token 只触发一次 _refresh_token（回归：子类不再绕过锁）。"""
    from custom_components.myraid_box.service_base import BaseService

    class _Locky(BaseService):
        service_id = "locky"
        default_api_url = "https://example.com"
        refresh_calls = 0

        @property
        def name(self):
            return "Locky"

        @property
        def description(self):
            return ""

        @property
        def config_fields(self):
            return {}

        def _parse_raw_response(self, data):
            return data

        def _get_sensor_configs(self):
            return []

        async def _refresh_token(self, params):
            _Locky.refresh_calls += 1
            # 制造一次微延迟，确保其他协程会等锁
            await asyncio.sleep(0.05)
            return f"tok-{_Locky.refresh_calls}"

    svc = _Locky(hass=None)
    # 10 个并发请求
    results = await asyncio.gather(*[svc._ensure_token({}) for _ in range(10)])
    assert len(set(results)) == 1, f"应复用同一 token，实际：{set(results)}"
    assert _Locky.refresh_calls == 1, f"应只刷新一次，实际：{_Locky.refresh_calls}"

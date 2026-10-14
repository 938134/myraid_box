"""BaseService 相关单测：RequestConfig 校验 + 错误分类。"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

import aiohttp
import pytest

from custom_components.myraid_box.service_base import (
    BaseService,
    RequestConfig,
)


def _make_client_response_error(status: int = 404):
    """构造 aiohttp.ClientResponseError 实例（status 可指定）。

    aiohttp 的 ClientResponseError.__init__ 强制要求 (request_info, history)，
    单测里用 MagicMock + spec 更方便设置 status。
    """
    err = MagicMock(spec=aiohttp.ClientResponseError)
    err.status = status
    return err


# ============================================================
# RequestConfig 校验
# ============================================================

def test_request_config_empty_url_raises():
    with pytest.raises(ValueError, match="url"):
        RequestConfig(url="")


def test_request_config_illegal_method_raises():
    with pytest.raises(ValueError, match="方法"):
        RequestConfig(url="https://example.com", method="TRACE")


def test_request_config_negative_timeout_raises():
    with pytest.raises(ValueError, match="timeout"):
        RequestConfig(url="https://example.com", timeout=-1)


def test_request_config_normalizes_method_to_upper():
    cfg = RequestConfig(url="https://example.com", method="get")
    assert cfg.method == "GET"


def test_request_config_injects_default_user_agent():
    cfg = RequestConfig(
        url="https://example.com",
        user_agent="MyAgent/1.0",
        headers={"Accept": "application/json"},
    )
    assert cfg.headers["User-Agent"] == "MyAgent/1.0"
    assert cfg.headers["Accept"] == "application/json"


def test_request_config_normalizes_empty_fields():
    cfg = RequestConfig(url="https://example.com")
    assert cfg.params == {}
    assert cfg.headers == {}


# ============================================================
# 错误分类
# ============================================================

@pytest.mark.parametrize(
    "exc,expected",
    [
        # 注意：aiohttp.ServerTimeoutError 是 asyncio.TimeoutError 子类，
        # _error_type 用 isinstance 顺序匹配，因此归入 "timeout"
        (asyncio.TimeoutError(), "timeout"),
        (aiohttp.ServerTimeoutError(), "timeout"),
        (aiohttp.ServerDisconnectedError(), "server_disconnected"),
        (_make_client_response_error(404), "http_error"),
        (MagicMock(spec=aiohttp.ClientConnectorError), "connection"),
        (aiohttp.ClientPayloadError(), "payload"),
        (json.JSONDecodeError("x", "", 0), "parse"),
        (ValueError("bad"), "parse"),
        (RuntimeError("boom"), "unknown"),
    ],
)
def test_error_type_classifier(exc, expected):
    assert BaseService._error_type(exc) == expected


def test_error_severity_warning_for_transient():
    assert BaseService._error_severity(asyncio.TimeoutError()) == "warning"
    assert (
        BaseService._error_severity(MagicMock(spec=aiohttp.ClientConnectorError))
        == "warning"
    )


def test_error_severity_error_for_permanent():
    assert BaseService._error_severity(json.JSONDecodeError("x", "", 0)) == "error"
    assert BaseService._error_severity(RuntimeError("boom")) == "error"


# ============================================================
# _refresh_token 默认实现（走 params）
# ============================================================

@pytest.mark.asyncio
async def test_ensure_token_fallback_reads_from_params():
    class _DummyService(BaseService):
        service_id = "dummy"
        default_api_url = "https://example.com"

        @property
        def name(self) -> str:
            return "Dummy"

        @property
        def description(self) -> str:
            return "Dummy desc"

        @property
        def config_fields(self):
            return {}

        def _parse_raw_response(self, data):
            return data

        def _get_sensor_configs(self):
            return []

    svc = _DummyService(hass=None)
    token = await svc._ensure_token({"access_token": "abc123"})
    assert token == "abc123"
    assert svc._token == "abc123"
    assert svc._token_expiry > 0

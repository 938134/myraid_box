from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


class SensorConfig(TypedDict, total=False):
    """传感器配置类型定义。"""

    key: str
    name: str
    icon: str
    unit: Optional[str]
    device_class: Optional[str]
    entity_category: Optional[str]
    is_attribute: bool
    parent_sensor: Optional[str]
    # 可选：稳定 ID，用于 translation_key
    translation_key: Optional[str]


class RequestConfig:
    """请求配置数据类。"""

    __slots__ = (
        "url",
        "method",
        "params",
        "data",
        "json_data",
        "headers",
        "timeout",
    )

    def __init__(
        self,
        url: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        data: Any = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
    ) -> None:
        self.url = url
        self.method = method.upper()
        self.params = params or {}
        self.data = data
        self.json_data = json_data
        self.headers = headers or {}
        self.timeout = timeout


class BaseService(ABC):
    """服务基类。

    HA 2024.6+ 规范：
    - 通过 `async_get_clientsession(hass)` 复用 Home Assistant 管理的
      aiohttp 会话，避免每个实例/服务各建一个 session（连接池膨胀、
      fd 泄漏）。
    - 生命周期完全交给 Home Assistant（hass 的 session 会在 shutdown
      时统一 close），本类不再持有 session 对象，因此也没有
      `async_unload` 需要维护。
    """

    DEFAULT_UPDATE_INTERVAL = 10
    DEFAULT_API_URL = ""
    DEFAULT_TIMEOUT = 30

    def __init__(self, hass: Optional[HomeAssistant] = None) -> None:
        """初始化。

        :param hass: 若需要发网络请求，必须由调用方注入 HomeAssistant 实例；
                     仅读取静态配置（如 config_flow 阶段）时可留空。
        """
        self._hass = hass
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0
        self._sensor_configs_cache: Optional[List[SensorConfig]] = None

    # ============================================================
    # 抽象属性
    # ============================================================
    @property
    @abstractmethod
    def service_id(self) -> str:
        """返回服务的唯一标识符。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """返回服务的用户友好名称。"""

    @property
    @abstractmethod
    def description(self) -> str:
        """返回服务的详细描述。"""

    @property
    @abstractmethod
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        """返回服务的配置字段定义。"""

    # ============================================================
    # 可覆盖属性
    # ============================================================
    @property
    def config_help(self) -> str:
        return f"配置 {self.name} 的相关参数"

    @property
    def device_name(self) -> str:
        return self.name

    @property
    def icon(self) -> str:
        return "mdi:information"

    @property
    def default_api_url(self) -> str:
        return self.DEFAULT_API_URL

    @property
    def default_timeout(self) -> int:
        return self.DEFAULT_TIMEOUT

    @property
    def default_update_interval(self):
        from datetime import timedelta

        interval_minutes = int(
            self.config_fields.get("interval", {}).get(
                "default", self.DEFAULT_UPDATE_INTERVAL
            )
        )
        return timedelta(minutes=interval_minutes)

    # ============================================================
    # 传感器配置
    # ============================================================
    @property
    def sensor_configs(self) -> List[SensorConfig]:
        """传感器配置（惰性缓存，避免每次访问都返回新 list）。"""
        if self._sensor_configs_cache is None:
            self._sensor_configs_cache = self._get_sensor_configs()
        return self._sensor_configs_cache

    def _get_sensor_configs(self) -> List[SensorConfig]:
        return []

    # ============================================================
    # Session 管理
    # ============================================================
    @property
    def _session(self) -> aiohttp.ClientSession:
        """获取 Home Assistant 管理的 aiohttp 会话。

        子类可以直接使用 ``self._session.get(...)``, 生命周期由 HA 控制。
        仅当 ``hass`` 未注入时（例如 config_flow 阶段仅读取静态配置）会抛错。
        """
        if self._hass is None:
            raise RuntimeError(
                f"服务 {self.__class__.__name__} 未注入 HomeAssistant 实例，"
                "无法发起网络请求。请在 ServiceCoordinator 初始化时传入 hass。"
            )
        return async_get_clientsession(self._hass)

    # ============================================================
    # 主入口
    # ============================================================
    async def fetch_data(
        self, coordinator, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """模板方法：prepare → execute → parse → response。"""
        try:
            request_config = await self.prepare_request(params)
            response_data = await self.execute_request(request_config)
            parsed_data = self.parse_response_data(response_data)
            return self._create_success_response(parsed_data)
        except Exception as e:
            return self._handle_error(e)

    # ============================================================
    # 请求准备阶段
    # ============================================================
    async def prepare_request(self, params: Dict[str, Any]) -> RequestConfig:
        token = await self._ensure_token(params)
        base_config = self._build_base_request(params)
        headers = {**base_config.headers, **self._build_auth_headers(token)}

        return RequestConfig(
            url=base_config.url,
            method=base_config.method,
            params=base_config.params,
            data=base_config.data,
            json_data=base_config.json_data,
            headers=headers,
            timeout=self.default_timeout,
        )

    def _build_base_request(self, params: Dict[str, Any]) -> RequestConfig:
        return RequestConfig(
            url=self.default_api_url,
            method="GET",
            params=self._build_request_params(params),
        )

    def _build_request_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    def _build_auth_headers(self, token: str) -> Dict[str, str]:
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

    # ============================================================
    # Token 管理
    # ============================================================
    async def _ensure_token(self, params: Dict[str, Any]) -> str:
        if self._token and time.time() < self._token_expiry:
            return self._token

        token = params.get("token") or params.get("access_token")
        if token:
            self._token = token
            self._token_expiry = time.time() + 3600
            return token

        return ""

    # ============================================================
    # 请求执行阶段
    # ============================================================
    async def execute_request(self, config: RequestConfig) -> Any:
        request_kwargs = self._prepare_request_kwargs(config)
        timeout = aiohttp.ClientTimeout(total=config.timeout)

        async with self._session.request(
            config.method, config.url, timeout=timeout, **request_kwargs
        ) as resp:
            return await self._process_response(resp)

    def _prepare_request_kwargs(self, config: RequestConfig) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"headers": config.headers}
        if config.params:
            kwargs["params"] = config.params
        if config.data:
            kwargs["data"] = config.data
        if config.json_data:
            kwargs["json"] = config.json_data
        return kwargs

    async def _process_response(self, resp: aiohttp.ClientResponse) -> Any:
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "").lower()

        if "application/json" in content_type:
            return await resp.json()

        text_data = await resp.text()
        try:
            return json.loads(text_data)
        except json.JSONDecodeError:
            return text_data

    # ============================================================
    # 数据解析阶段
    # ============================================================
    def parse_response_data(self, response_data: Any) -> Dict[str, Any]:
        try:
            raw_data = self._parse_raw_response(response_data)
            return self._normalize_data(raw_data)
        except Exception as e:
            _LOGGER.error("[%s] 解析响应数据失败: %s", self.service_id, e)
            return self._create_error_data(f"数据解析失败: {e}")

    @abstractmethod
    def _parse_raw_response(self, response_data: Any) -> Dict[str, Any]:
        """解析原始响应数据 —— 子类必须实现。"""

    def _normalize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return self._create_error_data("数据格式无效")

        data.setdefault("status", "success")
        if data["status"] == "success":
            return self._clean_data(data)
        return data

    def _clean_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = data.copy()
        for key, value in data.items():
            if value is None:
                cleaned[key] = self._get_default_value(key)
        return cleaned

    def _get_default_value(self, key: str) -> Any:
        numeric_fields = {"count", "humidity", "pressure", "temperature", "release_count"}
        return None if key in numeric_fields else "未知"

    # ============================================================
    # 响应构建
    # ============================================================
    def _create_success_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "data": data,
            "status": "success",
            "error": None,
            "update_time": datetime.now().isoformat(),
        }

    def _create_error_data(self, error_msg: str) -> Dict[str, Any]:
        return {"status": "error", "error": error_msg}

    def _handle_error(self, error: Exception) -> Dict[str, Any]:
        error_msg = self._format_error(error)
        _LOGGER.error("[%s] %s", self.service_id, error_msg)
        return {
            "data": None,
            "status": "error",
            "error": error_msg,
            "update_time": datetime.now().isoformat(),
        }

    def _format_error(self, error: Exception) -> str:
        if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
            return f"请求超时（{self.default_timeout}秒）"
        if isinstance(error, aiohttp.ClientConnectorError):
            return "连接服务器失败"
        if isinstance(error, aiohttp.ServerTimeoutError):
            return "服务器响应超时"
        if isinstance(error, aiohttp.ClientResponseError):
            return f"HTTP错误 {error.status}"
        return f"请求失败: {error}"

    # ============================================================
    # 传感器数据访问
    # ============================================================
    def get_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """从 coordinator.data 中取出指定传感器的原始值。"""
        if not data or data.get("status") != "success":
            return None
        return data.get("data", {}).get(sensor_key)

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化后的传感器显示值 —— 数值型返回数值，文本型返回 str。"""
        value = self.get_sensor_value(sensor_key, data)
        if value is None:
            return None

        sensor_config = self._find_sensor_config(sensor_key)
        if sensor_config and sensor_config.get("unit"):
            return self._try_to_number(value)

        return str(value)

    @staticmethod
    def _try_to_number(value: Any) -> Optional[float]:
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            match = re.search(r"[-+]?\d*\.?\d+", value)
            if match:
                num = float(match.group())
                return int(num) if num.is_integer() else num
        return None

    def _find_sensor_config(self, sensor_key: str) -> Optional[SensorConfig]:
        for cfg in self.sensor_configs:
            if cfg["key"] == sensor_key:
                return cfg
        return None

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        if not data or data.get("status") != "success":
            return {}
        return {
            "更新时间": data.get("update_time", "未知"),
            "数据状态": "成功",
        }

    def get_sensor_icon(self, sensor_key: str, data: Any) -> str:
        cfg = self._find_sensor_config(sensor_key)
        return cfg.get("icon", "mdi:information") if cfg else "mdi:information"

    # ============================================================
    # 辅助方法
    # ============================================================
    @staticmethod
    def _create_sensor_config(
        key: str,
        name: str,
        icon: str,
        unit: Optional[str] = None,
        device_class: Optional[str] = None,
        is_attribute: bool = False,
        parent_sensor: Optional[str] = None,
    ) -> SensorConfig:
        return {
            "key": key,
            "name": name,
            "icon": icon,
            "unit": unit,
            "device_class": device_class,
            "is_attribute": is_attribute,
            "parent_sensor": parent_sensor,
        }

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """子类可覆盖以添加校验逻辑。默认放行。"""
        pass

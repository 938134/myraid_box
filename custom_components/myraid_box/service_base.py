from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, TypedDict

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


# ============================================================
# 常量 & 类型定义
# ============================================================

DEFAULT_USER_AGENT = "MyriadBox-HA/2.1 (Home Assistant custom integration)"
SUPPORTED_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})


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


class ConfigFieldSpec(TypedDict, total=False):
    """配置字段元数据（config_fields 中每个字段的定义）。

    子类在 ``config_fields`` 属性里可以按此结构组织每个字段的元数据，
    用于驱动 config_flow / options_flow 的表单渲染和校验。
    """

    name: str
    required: bool
    default: Any
    type: str  # "string" | "password" | "number" | "select" | ...
    selector: Optional[Dict[str, Any]]
    help: Optional[str]
    options: Optional[List[Any]]  # 用于 select 字段


@dataclass(slots=True)
class RequestConfig:
    """请求配置数据类。

    使用 dataclass 是为了：
    - 明确字段类型；
    - 支持 ``__slots__``（省内存，实例少）；
    - 提供默认 user_agent 便于服务端识别。

    子类在 ``_build_base_request`` 里可返回任意组合，基类的
    ``prepare_request`` 会保留 ``timeout`` 字段（不再被覆盖）。
    """

    url: str
    method: str = "GET"
    params: Optional[Dict[str, Any]] = None
    data: Any = None
    json_data: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None
    timeout: Optional[int] = None
    user_agent: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.url:
            raise ValueError("RequestConfig.url 不能为空")
        if self.method.upper() not in SUPPORTED_METHODS:
            raise ValueError(
                f"不支持的 HTTP 方法: {self.method}，可用: {sorted(SUPPORTED_METHODS)}"
            )
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError(f"timeout 必须为正数，实际: {self.timeout}")
        # 统一方法大写，headers 归并 user_agent
        self.method = self.method.upper()
        self.params = self.params or {}
        self.headers = dict(self.headers or {})
        if self.user_agent and "User-Agent" not in self.headers:
            self.headers["User-Agent"] = self.user_agent


class BaseService(ABC):
    """服务基类。

    HA 2024.6+ 规范：

    - 通过 `async_get_clientsession(hass)` 复用 Home Assistant 管理的
      aiohttp 会话，避免每个实例/服务各建一个 session（连接池膨胀、
      fd 泄漏）。
    - 生命周期完全交给 Home Assistant（hass 的 session 会在 shutdown
      时统一 close），本类不再持有 session 对象，因此也没有
      `async_unload` 需要维护。
    - Token 获取使用 `asyncio.Lock` 保护，避免并发 fetch 时重复请求。
    """

    DEFAULT_UPDATE_INTERVAL = 10  # 分钟
    DEFAULT_API_URL = ""
    DEFAULT_TIMEOUT = 30  # 秒
    DEFAULT_USER_AGENT = DEFAULT_USER_AGENT
    DEFAULT_TOKEN_TTL = 3600  # 秒，子类可覆盖

    # 需要数字默认值（None）而不是字符串默认值的字段名。
    # 子类可覆盖此集合或调用 `_get_default_value` 扩展。
    numeric_default_fields: Set[str] = frozenset(
        {"count", "humidity", "pressure", "temperature", "release_count"}
    )

    def __init__(self, hass: Optional[HomeAssistant] = None) -> None:
        """初始化。

        :param hass: 若需要发网络请求，必须由调用方注入 HomeAssistant 实例；
                     仅读取静态配置（如 config_flow 阶段）时可留空。
        """
        self._hass = hass
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0
        self._token_lock = asyncio.Lock()
        self._sensor_configs_cache: Optional[List[SensorConfig]] = None

    # ============================================================
    # 抽象属性 & 方法（子类必须实现）
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

    @abstractmethod
    def _parse_raw_response(self, response_data: Any) -> Dict[str, Any]:
        """解析原始响应数据 —— 子类必须实现。"""

    # ============================================================
    # 可覆盖属性（子类按需重写）
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
    def default_update_interval(self) -> timedelta:
        interval_minutes = int(
            self.config_fields.get("interval", {}).get(
                "default", self.DEFAULT_UPDATE_INTERVAL
            )
        )
        return timedelta(minutes=interval_minutes)

    @property
    def hass(self) -> Optional[HomeAssistant]:
        """便捷访问 HomeAssistant 实例（等同 self._hass）。"""
        return self._hass

    # ============================================================
    # 传感器配置（惰性缓存）
    # ============================================================
    @property
    def sensor_configs(self) -> List[SensorConfig]:
        if self._sensor_configs_cache is None:
            self._sensor_configs_cache = self._get_sensor_configs()
        return self._sensor_configs_cache

    def _get_sensor_configs(self) -> List[SensorConfig]:
        return []

    def clear_sensor_configs_cache(self) -> None:
        """强制重建 sensor_configs 缓存（测试 / 热更新时用）。"""
        self._sensor_configs_cache = None

    @staticmethod
    def _create_sensor_config(
        key: str,
        name: str,
        icon: str,
        unit: Optional[str] = None,
        device_class: Optional[str] = None,
        is_attribute: bool = False,
        parent_sensor: Optional[str] = None,
        translation_key: Optional[str] = None,
    ) -> SensorConfig:
        return {
            "key": key,
            "name": name,
            "icon": icon,
            "unit": unit,
            "device_class": device_class,
            "is_attribute": is_attribute,
            "parent_sensor": parent_sensor,
            "translation_key": translation_key,
        }

    # ============================================================
    # Session 管理
    # ============================================================
    @property
    def _session(self) -> aiohttp.ClientSession:
        """获取 Home Assistant 管理的 aiohttp 会话。

        子类可以直接使用 ``self._session.get(...)``，生命周期由 HA 控制。
        仅当 ``hass`` 未注入时（例如 config_flow 阶段仅读取静态配置）会抛错。
        """
        if self._hass is None:
            raise RuntimeError(
                f"服务 {self.__class__.__name__} 未注入 HomeAssistant 实例，"
                "无法发起网络请求。请在 ServiceCoordinator 初始化时传入 hass。"
            )
        return async_get_clientsession(self._hass)

    # ============================================================
    # Token 管理（并发安全）
    # ============================================================
    async def _ensure_token(self, params: Dict[str, Any]) -> str:
        """返回有效 token，过期时通过 ``_refresh_token`` 刷新。

        使用 `asyncio.Lock` 保护临界区：并发 fetch 场景下，只有第一个
        协程会真正发起刷新，其余协程在锁释放后复用缓存结果，避免重复
        请求外部 token 服务。

        子类可覆盖 `_refresh_token` 以实现真实的 token 获取逻辑（比如
        poetry 的今日诗词 token 接口、weather 的 JWT 签名）。
        """
        if self._token and time.time() < self._token_expiry:
            return self._token

        async with self._token_lock:
            # 双重检查：可能已有并发协程刷新完
            if self._token and time.time() < self._token_expiry:
                return self._token
            try:
                token = await self._refresh_token(params)
            except Exception as e:  # pragma: no cover - 由 fetch_data 兜底
                _LOGGER.debug("[%s] token 刷新失败: %s", self.service_id, e)
                return ""
            if token:
                self._token = token
                # 优先用外部 payload 的 exp（weather JWT 自带），否则用 TTL
                if not self._token_expiry or self._token_expiry <= 0:
                    self._token_expiry = time.time() + self.DEFAULT_TOKEN_TTL
        return self._token or ""

    async def _refresh_token(self, params: Dict[str, Any]) -> str:
        """刷新 token 的钩子。子类按需覆盖。

        默认实现：直接返回 params 里已有的 token / access_token（用于
        静态配置型服务，如 weather 直接下发私钥的场景）。
        """
        return params.get("token") or params.get("access_token") or ""

    def invalidate_token(self) -> None:
        """强制让下一次 fetch 触发 token 刷新。"""
        self._token = None
        self._token_expiry = 0.0

    # ============================================================
    # 主入口（模板方法：prepare → execute → parse → response）
    # ============================================================
    async def fetch_data(
        self, coordinator: Any, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """模板方法。所有异常都在此捕获并转换为 error 结构。

        若参数被 CancelledError（HA 停止 / 平台卸载）中断，重新抛出
        而不是吞掉 —— 避免把取消当成业务错误返回给上层导致状态错乱。
        """
        try:
            request_config = await self.prepare_request(params)
            _LOGGER.debug(
                "[%s] %s %s (timeout=%s)",
                self.service_id,
                request_config.method,
                request_config.url,
                request_config.timeout or self.default_timeout,
            )
            response_data = await self.execute_request(request_config)
            parsed_data = self.parse_response_data(response_data)
            return self._create_success_response(parsed_data)
        except asyncio.CancelledError:
            raise  # 取消必须冒泡，让上层 coordinator / HASS 处理
        except Exception as e:
            return self._handle_error(e)

    # ============================================================
    # 请求准备阶段
    # ============================================================
    async def prepare_request(self, params: Dict[str, Any]) -> RequestConfig:
        """默认请求装配流程。

        注意：这里**保留** ``_build_base_request`` 返回的 ``timeout``
        （子类可针对特定请求设独立超时），不再强制用 ``self.default_timeout``
        覆盖。若子类未指定 timeout，则回落到 ``self.default_timeout``。
        """
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
            timeout=base_config.timeout if base_config.timeout is not None else self.default_timeout,
            user_agent=base_config.user_agent or self.DEFAULT_USER_AGENT,
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
    # 请求执行阶段
    # ============================================================
    async def execute_request(self, config: RequestConfig) -> Any:
        total_timeout = config.timeout or self.default_timeout
        timeout = aiohttp.ClientTimeout(total=total_timeout)

        async with self._session.request(
            config.method, config.url, timeout=timeout, **self._prepare_request_kwargs(config)
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

        try:
            text_data = await resp.text()
        except (UnicodeDecodeError, aiohttp.ClientPayloadError) as e:
            _LOGGER.debug("[%s] 响应文本解码失败: %s", self.service_id, e)
            return ""
        try:
            return json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
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
        return None if key in self.numeric_default_fields else "未知"

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
        level = self._error_severity(error)
        log = _LOGGER.error if level == "error" else _LOGGER.warning
        log("[%s] %s: %s", self.service_id, error.__class__.__name__, error_msg)
        return {
            "data": None,
            "status": "error",
            "error": error_msg,
            "error_type": self._error_type(error),
            "update_time": datetime.now().isoformat(),
        }

    def _format_error(self, error: Exception) -> str:
        if isinstance(error, asyncio.TimeoutError):
            return f"请求超时（{self.default_timeout}秒）"
        if isinstance(error, aiohttp.ClientConnectorError):
            return "连接服务器失败"
        if isinstance(error, aiohttp.ServerTimeoutError):
            return "服务器响应超时"
        if isinstance(error, aiohttp.ServerDisconnectedError):
            return "服务器断开连接"
        if isinstance(error, aiohttp.ClientPayloadError):
            return "响应数据接收失败"
        if isinstance(error, aiohttp.ClientResponseError):
            return f"HTTP 错误 {error.status}"
        if isinstance(error, aiohttp.ClientConnectionError):
            return "网络连接失败"
        if isinstance(error, (UnicodeDecodeError, json.JSONDecodeError, ValueError)):
            return f"响应格式错误: {error}"
        if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
            return f"请求超时（{self.default_timeout}秒）"
        return f"请求失败: {error}"

    @staticmethod
    def _error_type(error: Exception) -> str:
        """错误分类标签，方便上层做重试 / 展示逻辑。"""
        if isinstance(error, asyncio.TimeoutError):
            return "timeout"
        if isinstance(error, aiohttp.ServerTimeoutError):
            return "server_timeout"
        if isinstance(error, aiohttp.ServerDisconnectedError):
            return "server_disconnected"
        if isinstance(error, aiohttp.ClientResponseError):
            return "http_error"
        if isinstance(error, aiohttp.ClientConnectorError):
            return "connection"
        if isinstance(error, aiohttp.ClientPayloadError):
            return "payload"
        if isinstance(error, (json.JSONDecodeError, ValueError, UnicodeDecodeError)):
            return "parse"
        return "unknown"

    @staticmethod
    def _error_severity(error: Exception) -> str:
        """错误级别：timeout/connection 用 warning，其他走 error。"""
        if isinstance(error, (asyncio.TimeoutError, aiohttp.ClientConnectorError)):
            return "warning"
        return "error"

    # ============================================================
    # 传感器数据访问
    # ============================================================
    @staticmethod
    def has_valid_response(data: Any) -> bool:
        """判断 coordinator.data 是否是有效的 success 响应。"""
        return isinstance(data, dict) and data.get("status") == "success"

    @staticmethod
    def data_dict(data: Any) -> Dict[str, Any]:
        """从响应包装结构里取出内层数据字典，无效时返回 {}。"""
        if not isinstance(data, dict):
            return {}
        inner = data.get("data")
        return inner if isinstance(inner, dict) else {}

    def get_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """从 coordinator.data 中取出指定传感器的原始值。"""
        if not self.has_valid_response(data):
            return None
        return self.data_dict(data).get(sensor_key)

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
        if not self.has_valid_response(data):
            return {}
        return {
            "更新时间": data.get("update_time", "未知"),
            "数据状态": "成功",
        }

    def get_sensor_icon(self, sensor_key: str, data: Any) -> str:
        cfg = self._find_sensor_config(sensor_key)
        return cfg.get("icon", "mdi:information") if cfg else "mdi:information"

    # ============================================================
    # 配置校验
    # ============================================================
    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """子类可覆盖以添加校验逻辑。默认放行。

        抛出 :class:`ConfigValidationError` 表示配置无效；config_flow
        应捕获并展示 ``.message`` 给用户。
        """
        pass

    @classmethod
    def require_fields(
        cls,
        config: Dict[str, Any],
        fields: tuple[str, ...] | list[str],
        service_name: Optional[str] = None,
    ) -> None:
        """校验必填字段，缺失则抛 ``ConfigValidationError``。

        典型用法::

            @classmethod
            def validate_config(cls, config):
                cls.require_fields(config, ("api_key", "city_id"))
        """
        missing = [f for f in fields if not config.get(f)]
        if missing:
            name = service_name or "服务"
            raise ConfigValidationError(
                f"{name} 配置缺失字段: {', '.join(missing)}"
            )


# ============================================================
# 异常
# ============================================================
class ConfigValidationError(ValueError):
    """配置校验失败。message 可直接展示给用户。"""

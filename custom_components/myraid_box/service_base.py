from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TypedDict, List
from datetime import timedelta, datetime
import logging
import aiohttp
import time
import json
import asyncio
import re

_LOGGER = logging.getLogger(__name__)


class SensorConfig(TypedDict, total=False):
    """传感器配置类型定义 - 2026规范"""
    key: str
    name: str
    icon: str
    unit: str | None
    device_class: str | None
    entity_category: str | None
    is_attribute: bool
    parent_sensor: str


class RequestConfig:
    """请求配置类"""
    
    def __init__(
        self,
        url: str,
        method: str = "GET",
        params: Dict[str, Any] = None,
        data: Any = None,
        json_data: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        timeout: int = 30
    ):
        self.url = url
        self.method = method.upper()
        self.params = params or {}
        self.data = data
        self.json_data = json_data
        self.headers = headers or {}
        self.timeout = timeout


class BaseService(ABC):
    """服务基类 - 重构优化版本"""
    
    DEFAULT_UPDATE_INTERVAL = 10
    DEFAULT_API_URL = ""
    DEFAULT_TIMEOUT = 30

    def __init__(self):
        """初始化服务实例"""
        self._session: aiohttp.ClientSession | None = None
        self._token: str | None = None
        self._token_expiry: float | None = None

    # === 抽象属性 ===
    @property
    @abstractmethod
    def service_id(self) -> str:
        """返回服务的唯一标识符"""

    @property
    @abstractmethod
    def name(self) -> str:
        """返回服务的用户友好名称"""

    @property
    @abstractmethod
    def description(self) -> str:
        """返回服务的详细描述"""

    @property
    @abstractmethod
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        """返回服务的配置字段定义"""

    # === 可覆盖属性 ===
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
        interval_minutes = int(self.config_fields.get("interval", {}).get("default", self.DEFAULT_UPDATE_INTERVAL))
        return timedelta(minutes=interval_minutes)

    # === 传感器配置 ===
    @property
    def sensor_configs(self) -> List[SensorConfig]:
        return self._get_sensor_configs()

    def _get_sensor_configs(self) -> List[SensorConfig]:
        return []

    # === 会话管理 ===
    async def async_unload(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            _LOGGER.debug("[%s] HTTP会话已关闭", self.service_id)

    async def _ensure_session(self) -> None:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.default_timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
            _LOGGER.debug("[%s] 创建HTTP会话，超时: %s秒", self.service_id, self.default_timeout)

    # === 主入口方法 ===
    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            request_config = await self.prepare_request(params)
            response_data = await self.execute_request(request_config)
            parsed_data = self.parse_response_data(response_data)
            return self._create_success_response(parsed_data)
        except Exception as e:
            return self._handle_error(e)

    # === 请求准备阶段 ===
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
            timeout=self.default_timeout
        )

    def _build_base_request(self, params: Dict[str, Any]) -> RequestConfig:
        return RequestConfig(
            url=self.default_api_url,
            method="GET",
            params=self._build_request_params(params)
        )

    def _build_request_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    def _build_auth_headers(self, token: str) -> Dict[str, str]:
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

    # === Token管理 ===
    async def _ensure_token(self, params: Dict[str, Any]) -> str:
        if self._token and self._token_expiry and time.time() < self._token_expiry:
            return self._token
            
        token = params.get("token") or params.get("access_token")
        if token:
            self._token = token
            self._token_expiry = time.time() + 3600
            return token
            
        return ""

    # === 请求执行阶段 ===
    async def execute_request(self, config: RequestConfig) -> Any:
        await self._ensure_session()
        request_kwargs = self._prepare_request_kwargs(config)
        
        async with self._session.request(config.method, config.url, **request_kwargs) as resp:
            return await self._process_response(resp)

    def _prepare_request_kwargs(self, config: RequestConfig) -> Dict[str, Any]:
        kwargs = {"headers": config.headers}
        if config.params:
            kwargs["params"] = config.params
        if config.data:
            kwargs["data"] = config.data
        if config.json_data:
            kwargs["json"] = config.json_data
        return kwargs

    async def _process_response(self, resp) -> Any:
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "").lower()
        
        if "application/json" in content_type:
            return await resp.json()
        else:
            text_data = await resp.text()
            try:
                return json.loads(text_data)
            except json.JSONDecodeError:
                return text_data

    # === 数据解析阶段 ===
    def parse_response_data(self, response_data: Any) -> Dict[str, Any]:
        try:
            raw_data = self._parse_raw_response(response_data)
            return self._normalize_data(raw_data)
        except Exception as e:
            _LOGGER.error("[%s] 解析响应数据失败: %s", self.service_id, str(e))
            return self._create_error_data(f"数据解析失败: {str(e)}")

    @abstractmethod
    def _parse_raw_response(self, response_data: Any) -> Dict[str, Any]:
        """解析原始响应数据 - 子类必须实现"""

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

    # === 响应构建 ===
    def _create_success_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "data": data,
            "status": "success",
            "error": None,
            "update_time": datetime.now().isoformat()
        }

    def _create_error_data(self, error_msg: str) -> Dict[str, Any]:
        return {
            "status": "error",
            "error": error_msg
        }

    def _handle_error(self, error: Exception) -> Dict[str, Any]:
        error_msg = self._format_error(error)
        _LOGGER.error("[%s] %s", self.service_id, error_msg)
        
        return {
            "data": None,
            "status": "error",
            "error": error_msg,
            "update_time": datetime.now().isoformat()
        }

    def _format_error(self, error: Exception) -> str:
        if isinstance(error, asyncio.TimeoutError):
            return f"请求超时（{self.default_timeout}秒）"
        elif isinstance(error, aiohttp.ClientConnectorError):
            return "连接服务器失败"
        elif isinstance(error, aiohttp.ServerTimeoutError):
            return "服务器响应超时"
        elif isinstance(error, aiohttp.ClientResponseError):
            return f"HTTP错误 {error.status}"
        else:
            return f"请求失败: {str(error)}"

    # === 传感器数据访问（2026规范优化）===
    def get_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """获取传感器值"""
        if not data or data.get("status") != "success":
            return None
            
        value = data.get("data", {}).get(sensor_key)
        
        # 2026规范：优先返回None而非占位字符串
        if value is None:
            return None
            
        return value

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化传感器显示值 - 2026规范：返回合适的数据类型"""
        value = self.get_sensor_value(sensor_key, data)
        
        if value is None:
            return None
        
        # 查找传感器配置
        sensor_config = next((config for config in self.sensor_configs if config["key"] == sensor_key), None)
        
        # 如果有单位，尝试转换为数值类型
        if sensor_config and sensor_config.get("unit"):
            try:
                if isinstance(value, (int, float)):
                    return value
                elif isinstance(value, str):
                    numeric_match = re.search(r'[-+]?\d*\.?\d+', value)
                    if numeric_match:
                        num = float(numeric_match.group())
                        # 如果是整数且没有小数部分，返回整数
                        return int(num) if num.is_integer() else num
                    return None
                else:
                    return None
            except (ValueError, TypeError):
                return None
        
        # 文本型传感器返回字符串
        return str(value)

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        """获取传感器属性"""
        if not data or data.get("status") != "success":
            return {}
            
        return {
            "更新时间": data.get("update_time", "未知"),
            "数据状态": "成功",
            "错误信息": data.get("error", "")
        }

    def get_sensor_icon(self, sensor_key: str, data: Any) -> str:
        """获取传感器图标"""
        config = next((c for c in self.sensor_configs if c["key"] == sensor_key), None)
        return config.get("icon", "mdi:information") if config else "mdi:information"

    # === 辅助方法 ===
    def _create_sensor_config(
        self,
        key: str,
        name: str,
        icon: str,
        unit: str = None,
        device_class: str = None,
        is_attribute: bool = False,
        parent_sensor: str = None
    ) -> SensorConfig:
        """创建传感器配置 - 符合2026规范"""
        return {
            "key": key,
            "name": name,
            "icon": icon,
            "unit": unit,
            "device_class": device_class,
            "is_attribute": is_attribute,
            "parent_sensor": parent_sensor
        }

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        pass
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TypedDict, List
from datetime import timedelta, datetime
import logging
import aiohttp
import time
import json
import asyncio

_LOGGER = logging.getLogger(__name__)


class SensorConfig(TypedDict, total=False):
    """传感器配置类型定义"""
    
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
    
    # 类常量
    DEFAULT_UPDATE_INTERVAL = 10
    DEFAULT_API_URL = ""
    DEFAULT_TIMEOUT = 30

    def __init__(self):
        """初始化服务实例"""
        self._session: aiohttp.ClientSession | None = None
        self._token: str | None = None
        self._token_expiry: float | None = None

    # === 抽象属性（必须实现）===
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
        """返回服务的配置说明 - 子类可覆盖"""
        return f"配置 {self.name} 的相关参数"

    @property
    def device_name(self) -> str:
        """返回设备名称 - 子类可覆盖"""
        return self.name

    @property
    def icon(self) -> str:
        """返回服务的默认图标 - 子类可覆盖"""
        return "mdi:information"

    @property
    def default_api_url(self) -> str:
        """返回默认API地址 - 子类可覆盖"""
        return self.DEFAULT_API_URL

    @property
    def default_timeout(self) -> int:
        """返回默认超时时间（秒）- 子类可覆盖"""
        return self.DEFAULT_TIMEOUT

    @property
    def default_update_interval(self) -> timedelta:
        """从配置字段获取默认更新间隔"""
        interval_minutes = int(self.config_fields.get("interval", {}).get("default", self.DEFAULT_UPDATE_INTERVAL))
        return timedelta(minutes=interval_minutes)

    # === 传感器配置 ===
    @property
    def sensor_configs(self) -> List[SensorConfig]:
        """返回该服务提供的所有传感器配置"""
        return self._get_sensor_configs()

    def _get_sensor_configs(self) -> List[SensorConfig]:
        """子类实现的具体传感器配置"""
        return []

    # === 会话管理 ===
    async def async_unload(self) -> None:
        """清理资源"""
        if self._session and not self._session.closed:
            await self._session.close()
            _LOGGER.debug("[%s] HTTP会话已关闭", self.service_id)

    async def _ensure_session(self) -> None:
        """确保会话存在"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.default_timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
            _LOGGER.debug("[%s] 创建HTTP会话，超时: %s秒", self.service_id, self.default_timeout)

    # === 主入口方法 ===
    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取数据的主入口方法"""
        try:
            # 1. 准备请求
            request_config = await self.prepare_request(params)
            
            # 2. 执行请求
            response_data = await self.execute_request(request_config)
            
            # 3. 解析数据
            parsed_data = self.parse_response_data(response_data)
            
            return self._create_success_response(parsed_data)
            
        except Exception as e:
            return self._handle_error(e)

    # === 请求准备阶段 ===
    async def prepare_request(self, params: Dict[str, Any]) -> RequestConfig:
        """准备请求配置 - 子类可覆盖"""
        # 获取认证token
        token = await self._ensure_token(params)
        
        # 构建基础请求
        base_config = self._build_base_request(params)
        
        # 添加认证头
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
        """构建基础请求配置 - 子类可覆盖"""
        return RequestConfig(
            url=self.default_api_url,
            method="GET",
            params=self._build_request_params(params)
        )

    def _build_request_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """构建请求参数 - 子类可覆盖"""
        return {}

    def _build_auth_headers(self, token: str) -> Dict[str, str]:
        """构建认证头 - 子类可覆盖"""
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

    # === Token管理 ===
    async def _ensure_token(self, params: Dict[str, Any]) -> str:
        """确保有有效的token - 子类可覆盖"""
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
        """执行HTTP请求"""
        await self._ensure_session()
        
        # 准备请求参数
        request_kwargs = self._prepare_request_kwargs(config)
        
        async with self._session.request(config.method, config.url, **request_kwargs) as resp:
            return await self._process_response(resp)

    def _prepare_request_kwargs(self, config: RequestConfig) -> Dict[str, Any]:
        """准备请求参数"""
        kwargs = {"headers": config.headers}
        
        if config.params:
            kwargs["params"] = config.params
        if config.data:
            kwargs["data"] = config.data
        if config.json_data:
            kwargs["json"] = config.json_data
            
        return kwargs

    async def _process_response(self, resp) -> Any:
        """处理HTTP响应"""
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
        """解析响应数据"""
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
        """标准化数据格式"""
        if not isinstance(data, dict):
            return self._create_error_data("数据格式无效")
        
        # 确保状态字段
        data.setdefault("status", "success")
        
        # 处理成功数据
        if data["status"] == "success":
            return self._clean_data(data)
        
        return data

    def _clean_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """清理数据中的None值"""
        cleaned = data.copy()
        for key, value in data.items():
            if value is None:
                cleaned[key] = self._get_default_value(key)
        return cleaned

    def _get_default_value(self, key: str) -> Any:
        """根据字段名返回默认值"""
        numeric_fields = {"count", "humidity", "pressure", "temperature", "release_count"}
        return None if key in numeric_fields else "未知"

    # === 响应构建 ===
    def _create_success_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建成功响应"""
        return {
            "data": data,
            "status": "success",
            "error": None,
            "update_time": datetime.now().isoformat()
        }

    def _create_error_data(self, error_msg: str) -> Dict[str, Any]:
        """创建错误数据"""
        return {
            "status": "error",
            "error": error_msg
        }

    def _handle_error(self, error: Exception) -> Dict[str, Any]:
        """统一错误处理"""
        error_msg = self._format_error(error)
        _LOGGER.error("[%s] %s", self.service_id, error_msg)
        
        return {
            "data": None,
            "status": "error",
            "error": error_msg,
            "update_time": datetime.now().isoformat()
        }

    def _format_error(self, error: Exception) -> str:
        """格式化错误信息"""
        if isinstance(error, asyncio.TimeoutError):
            return f"请求超时（{self.default_timeout}秒）"
        elif isinstance(error, aiohttp.ClientConnectorError):
            return "连接服务器失败"
        elif isinstance(error, aiohttp.ServerTimeoutError):
            return f"服务器响应超时"
        elif isinstance(error, aiohttp.ClientResponseError):
            return f"HTTP错误 {error.status}"
        else:
            return f"请求失败: {str(error)}"

    # === 传感器数据访问 ===
    def get_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """获取传感器值"""
        if not data or data.get("status") != "success":
            return self._get_sensor_default(sensor_key)
            
        value = data.get("data", {}).get(sensor_key)
        return value if value is not None else self._get_sensor_default(sensor_key)

    def _get_sensor_default(self, sensor_key: str) -> Any:
        """获取传感器默认值"""
        numeric_sensors = {"humidity", "pressure", "temperature", "release_count", "count"}
        return None if sensor_key in numeric_sensors else "暂无数据"

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化传感器显示值 - 确保数值型传感器返回数值或None"""
        value = self.get_sensor_value(sensor_key, data)
        
        if value is None:
            return self._get_sensor_default(sensor_key)
        
        # 对于数值型传感器，确保返回数值或None
        sensor_config = next((config for config in self.sensor_configs if config["key"] == sensor_key), None)
        if sensor_config and sensor_config.get("unit"):
            # 有单位的传感器应该是数值型
            try:
                # 尝试转换为数值
                if isinstance(value, (int, float)):
                    return value
                elif isinstance(value, str):
                    # 如果是字符串，尝试提取数字
                    numeric_match = re.search(r'[-+]?\d*\.?\d+', value)
                    if numeric_match:
                        return float(numeric_match.group())
                    else:
                        return None
                else:
                    return None
            except (ValueError, TypeError):
                return None
        
        # 对于文本型传感器，返回字符串
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
        """创建传感器配置"""
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
        """验证服务配置 - 子类可覆盖"""
        pass
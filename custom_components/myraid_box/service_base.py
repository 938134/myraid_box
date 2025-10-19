from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TypedDict, List, Tuple
from datetime import timedelta, datetime
import logging
import aiohttp

_LOGGER = logging.getLogger(__name__)

class AttributeConfig(TypedDict, total=False):
    """传感器属性配置类型定义"""
    name: str
    icon: str
    unit: str | None
    device_class: str | None
    value_map: Dict[str, str] | None

class SensorConfig(TypedDict, total=False):
    """传感器配置类型定义"""
    key: str
    name: str
    icon: str
    unit: str | None
    device_class: str | None
    entity_category: str | None
    value_formatter: str | None

class BaseService(ABC):
    """重构的服务基类 - 支持多传感器生成"""
    
    def __init__(self):
        """初始化服务实例"""
        self._last_update: datetime | None = None
        self._last_successful: bool = True
        self._session: aiohttp.ClientSession | None = None

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
    def device_name(self) -> str:
        """返回设备名称"""
        return self.name

    @property
    def icon(self) -> str:
        """返回服务的默认图标"""
        return "mdi:information"

    @property
    def default_update_interval(self) -> timedelta:
        """从config_fields获取默认更新间隔"""
        interval_minutes = int(self.config_fields.get("interval", {}).get("default", 10))
        return timedelta(minutes=interval_minutes)

    @property
    @abstractmethod
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        """抽象方法：返回服务的配置字段定义"""

    @property
    def sensor_configs(self) -> List[SensorConfig]:
        """返回该服务提供的所有传感器配置"""
        return []

    def get_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """根据传感器key获取对应的值"""
        if not data or data.get("status") != "success":
            return None
            
        parsed_data = self.parse_response(data)
        return parsed_data.get(sensor_key)

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化特定传感器的显示值"""
        value = self.get_sensor_value(sensor_key, data)
        if value is None:
            return "暂无数据"
        return str(value)

    async def async_unload(self) -> None:
        """清理资源"""
        if self._session and not self._session.closed:
            await self._session.close()
            _LOGGER.debug("[%s] HTTP会话已关闭", self.service_id)

    async def _ensure_session(self) -> None:
        """确保会话存在"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))

    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取数据（网络请求和数据获取）"""
        await self._ensure_session()
        try:
            url, request_params, headers = self.build_request(params)
            
            async with self._session.get(url, params=request_params, headers=headers) as resp:
                content_type = resp.headers.get("Content-Type", "").lower()
                resp.raise_for_status()
                if "application/json" in content_type:
                    data = await resp.json()
                else:
                    data = await resp.text()
                
                return {
                    "data": data,
                    "status": "success",
                    "error": None,
                    "update_time": datetime.now().isoformat()
                }
        except Exception as e:
            _LOGGER.error("[%s] 请求失败: %s", self.service_id, str(e), exc_info=True)
            return {
                "data": None,
                "status": "error",
                "error": str(e),
                "update_time": datetime.now().isoformat()
            }

    @abstractmethod
    def build_request(self, params: Dict[str, Any]) -> Tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建请求的 URL、参数和请求头"""
        pass
    
    @abstractmethod
    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """解析响应数据为标准化字典"""
        pass
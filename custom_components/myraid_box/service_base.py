from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TypedDict, List, Callable, Tuple
from datetime import timedelta, datetime
import logging
from homeassistant.core import HomeAssistant, CALLBACK_TYPE
from homeassistant.helpers.event import async_track_time_interval
import aiohttp

_LOGGER = logging.getLogger(__name__)

class AttributeConfig(TypedDict, total=False):
    """传感器属性配置类型定义
    
    Attributes:
        name: 属性显示名称
        icon: 属性图标 (Material Design Icons)
        unit: 计量单位
        device_class: 设备类型 (Home Assistant标准)
        value_map: 值映射字典 {原始值: 显示值}
    """
    name: str
    icon: str
    unit: str | None
    device_class: str | None
    value_map: Dict[str, str] | None

class BaseService(ABC):
    """服务基类，所有具体服务必须继承此类"""
    
    def __init__(self):
        """初始化服务实例"""
        self._last_update: datetime | None = None
        self._last_successful: bool = True
        self._session: aiohttp.ClientSession | None = None

    @property
    @abstractmethod
    def service_id(self) -> str:
        """返回服务的唯一标识符 (必须全小写，无空格)"""

    @property
    @abstractmethod
    def name(self) -> str:
        """返回服务的用户友好名称"""

    @property
    @abstractmethod
    def description(self) -> str:
        """返回服务的详细描述"""

    @property
    def icon(self) -> str:
        """返回服务的默认图标 (Material Design Icons)"""
        return "mdi:information"

    @property
    def unit(self) -> str | None:
        """返回服务的默认单位"""
        return None

    @property
    def device_class(self) -> str | None:
        """返回服务的设备类型"""
        return None

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
    def attributes(self) -> Dict[str, AttributeConfig]:
        """返回传感器的额外属性配置"""
        return {}

    def get_sensor_configs(self, service_data: Any) -> List[Dict[str, Any]]:
        """返回该服务提供的传感器配置列表"""
        return [{
            "key": "main",
            "name": self.name,
            "icon": self.icon,
            "unit": self.unit,
            "device_class": self.device_class
        }]

    def format_sensor_value(self, data: Any, sensor_config: Dict[str, Any]) -> Any:
        """格式化传感器显示值"""
        return str(data) if data is not None else "暂无数据"

    def is_sensor_available(self, data: Any, sensor_config: Dict[str, Any]) -> bool:
        """检查传感器是否可用"""
        if data is None:
            return False
        required_fields = sensor_config.get("required_fields", [])
        for field in required_fields:
            if field not in data:
                return False
        return True

    def get_sensor_attributes(self, data: Any, sensor_config: Dict[str, Any]) -> Dict[str, Any]:
        """获取传感器的额外属性"""
        if not data:
            return {}
            
        attrs = {}
        for attr, config in self.attributes.items():
            if value := data.get(attr):
                if "value_map" in config:
                    value = config["value_map"].get(str(value), value)
                attrs[config.get("name", attr)] = value
        return attrs

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
        """解析响应数据"""
        pass
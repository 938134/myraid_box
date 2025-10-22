from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TypedDict, List, Tuple, Union
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
    sort_order: int  # 新增：实体创建顺序

class BaseService(ABC):
    """增强的服务基类 - 支持自动配置和实体排序"""

    # 类常量
    DEFAULT_UPDATE_INTERVAL = 10  # 默认更新间隔（分钟）
    DEFAULT_API_URL = ""  # 子类需要覆盖这个

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
        interval_minutes = int(self.config_fields.get("interval", {}).get("default", self.DEFAULT_UPDATE_INTERVAL))
        return timedelta(minutes=interval_minutes)

    @property
    def default_api_url(self) -> str:
        """返回默认API地址"""
        return self.DEFAULT_API_URL

    @property
    @abstractmethod
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        """抽象方法：返回服务的配置字段定义"""

    @property
    def sensor_configs(self) -> List[SensorConfig]:
        """返回该服务提供的所有传感器配置（已排序）"""
        configs = self._get_sensor_configs()
        # 按 sort_order 排序，如果没有设置则按添加顺序
        return sorted(configs, key=lambda x: x.get('sort_order', 999))

    def _get_sensor_configs(self) -> List[SensorConfig]:
        """子类实现的具体传感器配置"""
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

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        """获取传感器的额外属性"""
        return {}

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

    def build_request(self, params: Dict[str, Any]) -> Tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建请求的 URL、参数和请求头 - 子类可覆盖"""
        url = self.default_api_url
        request_params = self._build_request_params(params)
        headers = self._build_request_headers()
        return url, request_params, headers

    def _build_request_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """构建请求参数 - 子类可覆盖"""
        return {}

    def _build_request_headers(self) -> Dict[str, str]:
        """构建请求头 - 子类可覆盖"""
        return {
            "User-Agent": f"HomeAssistant/{self.service_id}",
            "Accept": "application/json"
        }

    @abstractmethod
    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """解析响应数据为标准化字典"""
        pass

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """验证服务配置 - 子类可覆盖为类方法"""
        pass

    def _create_sensor_config(self, key: str, name: str, icon: str, 
                            unit: str = None, device_class: str = None, 
                            sort_order: int = 999) -> SensorConfig:
        """快速创建传感器配置的辅助方法"""
        return {
            "key": key,
            "name": name,
            "icon": icon,
            "unit": unit,
            "device_class": device_class,
            "sort_order": sort_order
        }
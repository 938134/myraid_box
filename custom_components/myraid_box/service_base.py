from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TypedDict, List, Callable
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
    """服务基类，所有具体服务必须继承此类
    
    提供以下核心功能：
    - 定时任务管理
    - 配置字段定义
    - 传感器数据格式化
    - 错误处理基础框架
    - 网络请求功能
    """

    def __init__(self):
        """初始化服务实例"""
        self._update_cancel: CALLBACK_TYPE | None = None
        self._update_interval: timedelta = self.default_update_interval
        self._update_callback: Callable | None = None
        self.hass: HomeAssistant | None = None
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
        interval_minutes = self.config_fields.get("interval", {}).get("default", 10)
        return timedelta(minutes=interval_minutes)

    def setup_periodic_update(
        self,
        hass: HomeAssistant,
        update_callback: Callable,
        interval: timedelta | None = None
    ) -> None:
        """设置定时更新任务"""
        self.cancel_periodic_update()
        
        self.hass = hass
        self._update_callback = update_callback
        self._update_interval = interval or self.default_update_interval

        if self._update_interval.total_seconds() < 60:
            _LOGGER.warning(
                "[%s] 更新间隔 %.1f 分钟过短，已自动调整为1分钟",
                self.service_id,
                self._update_interval.total_seconds() / 60
            )
            self._update_interval = timedelta(minutes=1)

        _LOGGER.info(
            "[%s] 设置定时更新，间隔: %.1f 分钟",
            self.service_id,
            self._update_interval.total_seconds() / 60
        )

        self._update_cancel = async_track_time_interval(
            hass,
            self._safe_update_wrapper,
            self._update_interval
        )

        # 立即触发首次更新
        hass.async_create_task(self._safe_update_wrapper())

    async def _safe_update_wrapper(self, now=None):
        """带状态保持的更新包装器"""
        update_time = datetime.now().isoformat()
        try:
            result = await (self._update_callback(now) if self._update_callback else None)
            if result and result.get("status") == "success":
                self._last_successful_data = {
                    **result,
                    "update_time": update_time,
                    "is_cached": False
                }
                self._last_successful = True
                _LOGGER.debug("[%s] 更新成功", self.service_id)
            return result
        except Exception as e:
            self._last_successful = False
            _LOGGER.warning(
                "[%s] 更新失败: %s", 
                self.service_id, 
                str(e),
                exc_info=_LOGGER.isEnabledFor(logging.DEBUG)
            )
            if self._last_successful_data:
                return {
                    **self._last_successful_data,
                    "update_time": update_time,
                    "is_cached": True,
                    "error": str(e)
                }
            raise

    @abstractmethod
    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Any:
        """抽象方法：获取服务数据"""

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
        return data is not None

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

    @property
    def last_update_status(self) -> Dict[str, Any]:
        """返回最后一次更新的状态信息"""
        return {
            "last_update": self._last_update,
            "success": self._last_successful,
            "interval_minutes": self._update_interval.total_seconds() / 60
        }

    def cancel_periodic_update(self) -> None:
        """取消现有的定时更新任务"""
        if self._update_cancel:
            self._update_cancel()
            self._update_cancel = None
            _LOGGER.debug("[%s] 已取消定时更新", self.service_id)

    async def async_unload(self) -> None:
        """清理资源"""
        self.cancel_periodic_update()
        if self._session and not self._session.closed:
            await self._session.close()
            _LOGGER.debug("[%s] HTTP会话已关闭", self.service_id)

    async def _ensure_session(self) -> None:
        """确保会话存在"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
            _LOGGER.debug("[%s] 创建新的HTTP会话", self.service_id)

    async def _make_request(self, url: str, params: Dict[str, Any] = None, headers: Dict[str, str] = None) -> Dict[str, Any]:
        """发送网络请求"""
        await self._ensure_session()
        try:
            async with self._session.get(url, params=params, headers=headers) as resp:
                resp.raise_for_status()
                content_type = resp.headers.get("Content-Type", "").lower()
                if "application/json" in content_type:
                    data = await resp.json()
                else:
                    data = await resp.text()  # 返回原始文本内容
                return {
                    "data": data,
                    "status": "success",
                    "error": None
                }
        except Exception as e:
            _LOGGER.error("[%s] 请求失败: %s", self.service_id, str(e), exc_info=True)
            return {
                "data": None,
                "status": "error",
                "error": str(e)
            }
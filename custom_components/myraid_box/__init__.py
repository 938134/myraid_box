from __future__ import annotations
import logging
from datetime import datetime, timedelta
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, SERVICE_REGISTRY, discover_services
from .config_flow import MyriadBoxConfigFlow 

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

class ServiceCoordinator(DataUpdateCoordinator):
    """单个服务的独立协调器"""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, service_id: str):
        """初始化独立服务协调器"""
        service_class = SERVICE_REGISTRY[service_id]
        self.service = service_class()
        self.service_id = service_id
        self.entry = entry
        
        # 从配置中提取该服务的参数
        self.params = {
            k.split(f"{service_id}_")[1]: v 
            for k, v in entry.data.items() 
            if k.startswith(f"{service_id}_")
        }
        
        # 获取更新间隔（分钟转秒）
        interval_minutes = int(self.params.get(
            "interval",
            self.service.config_fields.get("interval", {}).get("default", 15)
        ))
        update_interval = timedelta(minutes=interval_minutes)
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{service_id}",
            update_interval=update_interval,
            update_method=self._async_update_data
        )
        
        # 存储最后一次成功数据
        self._last_successful_data = None

    async def _async_update_data(self) -> Dict[str, Any]:
        """执行独立数据更新"""
        try:
            # 强制使用当前时间作为更新时间
            update_time = datetime.now().isoformat()
            result = await self.service.fetch_data(self, self.params)
            result["update_time"] = update_time
            
            # 只有数据真正变化时才更新
            if result != self._last_successful_data:
                self._last_successful_data = result
                return result
            return self._last_successful_data
            
        except Exception as e:
            _LOGGER.error("[%s] 更新失败: %s", self.service_id, str(e), exc_info=True)
            raise

async def async_setup(hass: HomeAssistant, config: Dict) -> bool:
    """设置组件"""
    # 注册配置流
    if DOMAIN not in config_entries.HANDLERS:
        hass.data[DOMAIN] = {}
        config_entries.HANDLERS.register(DOMAIN)(MyriadBoxConfigFlow)
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """通过配置条目设置"""
    # 服务自动发现
    services_dir = str(Path(__file__).parent / "services")
    await discover_services(hass, services_dir)
    
    # 初始化协调器
    coordinators = {}
    enabled_services = [
        k.replace("enable_", "") 
        for k, v in entry.data.items() 
        if k.startswith("enable_") and v
    ]
    
    for service_id in enabled_services:
        try:
            coordinator = ServiceCoordinator(hass, entry, service_id)
            await coordinator.async_config_entry_first_refresh()
            coordinators[service_id] = coordinator
        except Exception as e:
            _LOGGER.error(f"初始化服务 {service_id} 失败: {str(e)}")
            raise ConfigEntryNotReady(f"服务 {service_id} 初始化失败") from e
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinators
    
    # 设置平台 - 使用新的方式
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """配置项更新时重新加载"""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载集成"""
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        return False

    coordinators = hass.data[DOMAIN][entry.entry_id]
    
    # 卸载所有平台
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok
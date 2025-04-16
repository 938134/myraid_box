from __future__ import annotations
import logging
from datetime import datetime, timedelta
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, SERVICE_REGISTRY, discover_services

_LOGGER = logging.getLogger(__name__)

class MyriadBoxCoordinator(DataUpdateCoordinator):
    """动态间隔的数据协调器"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """初始化协调器"""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self._async_update_data
        )
        self.entry = entry
        self.session = async_get_clientsession(hass)
        self._services: Dict[str, Any] = {}
        self._data: Dict[str, Any] = {}
        self._enabled_services: List[str] = []
        self._update_tasks: Dict[str, CALLBACK_TYPE] = {}
        self._update_intervals: Dict[str, int] = {}

    async def async_ensure_data_loaded(self):
        """确保所有服务数据已加载"""
        self._enabled_services = [
            k.replace("enable_", "") 
            for k, v in self.entry.data.items() 
            if k.startswith("enable_") and v
        ]
        
        _LOGGER.info("正在初始化 %d 个服务: %s", 
                    len(self._enabled_services),
                    ", ".join(self._enabled_services))
        
        try:
            await self._setup_all_services()
        except Exception as e:
            _LOGGER.error("服务初始化失败: %s", str(e), exc_info=True)
            raise

    async def _setup_all_services(self):
        """初始化所有启用的服务"""
        await asyncio.gather(*[
            self._setup_service(service_id)
            for service_id in self._enabled_services
        ])

    async def _setup_service(self, service_id: str):
        """初始化单个服务"""
        if service_id in self._services:
            return
            
        if service_class := SERVICE_REGISTRY.get(service_id):
            try:
                service = service_class()
                self._services[service_id] = service
                
                # 获取配置参数
                params = {
                    k.split(f"{service_id}_")[1]: v 
                    for k, v in self.entry.data.items() 
                    if k.startswith(f"{service_id}_")
                }
                
                # 设置更新间隔（分钟转秒）
                interval_minutes = params.get(
                    "interval",
                    service.config_fields.get("interval", {}).get("default", 10)
                )
                interval_seconds = interval_minutes * 60
                self._update_intervals[service_id] = interval_seconds
                
                # 定义更新回调
                async def service_updater(_=None):
                    """带间隔控制的服务更新"""
                    try:
                        last_update = self._data.get(service_id, {}).get("update_time")
                        if last_update:
                            elapsed = (datetime.now() - datetime.fromisoformat(last_update)).total_seconds()
                            if elapsed < interval_seconds:
                                return
                        
                        _LOGGER.debug("[%s] 执行定时更新", service_id)
                        self._data[service_id] = await service.fetch_data(self, params)
                        self.async_set_updated_data(self._data)
                    except Exception as e:
                        _LOGGER.error("[%s] 更新失败: %s", service_id, str(e))

                # 取消现有任务（如果存在）
                if service_id in self._update_tasks:
                    self._update_tasks[service_id]()
                
                # 立即执行首次更新
                await service_updater()
                
                # 设置定时任务
                self._update_tasks[service_id] = async_track_time_interval(
                    self.hass,
                    service_updater,
                    timedelta(seconds=interval_seconds)
                )
                _LOGGER.info(
                    "[%s] 服务初始化完成，更新间隔: %d 分钟", 
                    service_id, 
                    interval_minutes
                )
                
            except Exception as e:
                _LOGGER.error("[%s] 服务初始化失败: %s", service_id, str(e))
                raise

    async def _async_update_data(self):
        """被动数据聚合方法"""
        return self._data

    async def async_unload(self):
        """卸载协调器"""
        _LOGGER.info("正在停止所有服务...")
        for task in self._update_tasks.values():
            task()
        self._update_tasks.clear()
        
        for service in self._services.values():
            if hasattr(service, 'async_unload'):
                await service.async_unload()
        
        self._services.clear()
        _LOGGER.info("所有服务已停止")

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """设置集成入口"""
    # 服务自动发现
    services_dir = str(Path(__file__).parent / "services")
    await discover_services(hass, services_dir)
    
    # 初始化协调器
    coordinator = MyriadBoxCoordinator(hass, entry)
    
    try:
        await coordinator.async_ensure_data_loaded()
    except Exception as e:
        raise ConfigEntryNotReady(f"数据加载失败: {str(e)}") from e
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    return True

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """配置项更新时重新加载"""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载集成"""
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        return False

    coordinator: MyriadBoxCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_unload()
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok
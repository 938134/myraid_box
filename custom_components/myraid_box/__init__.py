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

from .const import DOMAIN, SERVICE_REGISTRY, discover_services

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    """集成初始化"""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """设置集成入口"""
    # 服务自动发现
    services_dir = str(Path(__file__).parent / "services")
    discover_services(services_dir)
    
    # 初始化协调器
    coordinator = MyraidBoxCoordinator(hass, entry)
    
    try:
        # 确保数据加载完成
        await coordinator.async_ensure_data_loaded()
    except Exception as e:
        _LOGGER.error("初始化数据失败: %s", str(e), exc_info=True)
        raise ConfigEntryNotReady(f"数据加载失败: {str(e)}") from e
    
    # 存储协调器实例
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # 设置平台
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    
    # 配置更新监听
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    # 创建设备注册
    #await _async_create_device(hass, entry)
    
    return True

# 删除或注释掉 _async_create_device 相关代码
# async def _async_create_device(hass: HomeAssistant, entry: ConfigEntry):
#     device_registry = dr.async_get(hass)
#     device_registry.async_get_or_create(
#         config_entry_id=entry.entry_id,
#         identifiers={(DOMAIN, entry.entry_id)},
#         manufacturer="万象盒子",
#         name=entry.title,
#         model="多服务聚合终端",
#         sw_version="2.0"
#     )

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """配置项更新时重新加载"""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载集成"""
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        return False

    coordinator: MyraidBoxCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    # 取消所有服务更新
    await coordinator.async_unload()
    
    # 卸载平台
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok

class MyraidBoxCoordinator(DataUpdateCoordinator):
    """数据协调器（完整实现）"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """初始化"""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self._async_update_data,
            update_interval=timedelta(minutes=5)  # 默认更新间隔
        )
        self.entry = entry
        self.session = async_get_clientsession(hass)
        self._services: Dict[str, Any] = {}
        self._data: Dict[str, Any] = {}
        self._enabled_services: List[str] = []

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
            await self.async_refresh()
        except Exception as e:
            _LOGGER.error("服务初始化失败: %s", str(e), exc_info=True)
            raise

    async def _setup_all_services(self):
        """初始化所有启用的服务"""
        for service_id in self._enabled_services:
            await self._setup_service(service_id)

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
                
                # 设置更新间隔
                interval = timedelta(
                    minutes=params.get(
                        "interval",
                        service.config_fields.get("interval", {}).get("default", 10)
                    )
                )
                service.setup_periodic_update(
                    self.hass,
                    lambda now=None, s=service, p=params: self._service_updater(s, p),
                    interval
                )
                
                _LOGGER.info("[%s] 服务初始化完成，更新间隔: %s 分钟", 
                            service_id, interval.total_seconds() / 60)
                
            except Exception as e:
                _LOGGER.error("[%s] 服务初始化失败: %s", service_id, str(e), exc_info=True)
                raise

    async def _service_updater(self, service: BaseService, params: Dict[str, Any]):
        """服务数据更新回调"""
        service_id = service.service_id
        try:
            self._data[service_id] = await service.fetch_data(self, params)
            self.async_set_updated_data(self._data)
            _LOGGER.debug("[%s] 数据更新成功", service_id)
        except Exception as e:
            _LOGGER.error("[%s] 更新失败: %s", service_id, str(e), exc_info=True)
            self._data[service_id] = {
                "error": str(e),
                "last_update": datetime.now().isoformat(),
                "status": "error"
            }
            self.async_set_updated_data(self._data)

    async def _async_update_data(self):
        """全局数据更新方法"""
        if not self._services:
            _LOGGER.warning("没有可用的服务")
            return self._data
            
        try:
            results = await asyncio.gather(*[
                service.fetch_data(self, {
                    k.split(f"{sid}_")[1]: v 
                    for k, v in self.entry.data.items() 
                    if k.startswith(f"{sid}_")
                })
                for sid, service in self._services.items()
            ], return_exceptions=True)
            
            # 合并结果
            for sid, result in zip(self._services.keys(), results):
                if isinstance(result, Exception):
                    self._data[sid] = {
                        "error": str(result),
                        "status": "error"
                    }
                else:
                    self._data[sid] = result
            
            return self._data
        except Exception as e:
            _LOGGER.error("全局更新失败: %s", str(e), exc_info=True)
            raise

    async def async_unload(self):
        """卸载协调器"""
        _LOGGER.info("正在停止所有服务...")
        for service in self._services.values():
            if hasattr(service, 'cancel_periodic_update'):
                service.cancel_periodic_update()
            if hasattr(service, 'async_unload'):
                await service.async_unload()
        
        self._services.clear()
        _LOGGER.info("所有服务已停止")

    def get_service_status(self, service_id: str) -> Optional[Dict[str, Any]]:
        """获取服务状态"""
        if service_id not in self._services:
            return None
            
        data = self._data.get(service_id, {})
        return {
            "last_update": data.get("last_update"),
            "status": data.get("status", "unknown"),
            "error": data.get("error")
        }
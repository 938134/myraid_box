from __future__ import annotations
import logging
from datetime import datetime, timedelta
import asyncio
import time
import hashlib
import os
from typing import Dict, Any, Optional
from pathlib import Path

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.http import HomeAssistantView

from .const import DOMAIN, SERVICE_REGISTRY, discover_services
from .config_flow import MyriadBoxConfigFlow 

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


class MyraidBoxAPIView(HomeAssistantView):
    """API端点，供卡片直接读取集成数据"""
    url = "/api/myraid_box/data"
    name = "api:myraid_box:data"
    requires_auth = False

    async def get(self, request):
        """返回所有服务的实时数据"""
        hass = request.app["hass"]
        
        if DOMAIN not in hass.data:
            return self.json({"error": "集成未加载"}, status=404)
        
        result = {}
        
        # 遍历所有配置条目
        for entry_id, coordinators in hass.data[DOMAIN].items():
            for service_id, coordinator in coordinators.items():
                if coordinator.data and coordinator.data.get("status") == "success":
                    service_data = coordinator.data.get("data", {})
                    result[service_id] = {
                        "status": "success",
                        "data": service_data,
                        "update_time": coordinator.data.get("update_time")
                    }
                elif coordinator.data:
                    result[service_id] = {
                        "status": "error",
                        "error": coordinator.data.get("error", "未知错误")
                    }
        
        return self.json(result)


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
        
        # 获取更新间隔
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
        
        self._last_successful_data = None

    async def _async_update_data(self) -> Dict[str, Any]:
        """执行独立数据更新"""
        try:
            update_time = datetime.now().isoformat()
            result = await self.service.fetch_data(self, self.params)
            result["update_time"] = update_time
            
            if result != self._last_successful_data:
                self._last_successful_data = result
                return result
            return self._last_successful_data
            
        except Exception as e:
            _LOGGER.error("[%s] 更新失败: %s", self.service_id, str(e), exc_info=True)
            raise


async def setup_myraid_card(hass: HomeAssistant) -> bool:
    """注册万象盒子卡片"""
    card_js_path = hass.config.path(f'custom_components/{DOMAIN}/frontend/myraid_box_card.js')
    card_path = '/myriad_card_local'
    frontend_dir = hass.config.path(f'custom_components/{DOMAIN}/frontend')
    
    def compute_file_hash():
        try:
            if os.path.exists(card_js_path):
                with open(card_js_path, 'rb') as f:
                    return hashlib.md5(f.read()).hexdigest()[:8]
            return None
        except Exception:
            return None
    
    def ensure_dir():
        if not os.path.exists(frontend_dir):
            os.makedirs(frontend_dir, exist_ok=True)
    
    try:
        await hass.async_add_executor_job(ensure_dir)
        file_hash = await hass.async_add_executor_job(compute_file_hash)
        version = file_hash if file_hash else str(int(time.time()))
        
        await hass.http.async_register_static_paths([
            StaticPathConfig(card_path, frontend_dir, False)
        ])
        add_extra_js_url(hass, f"{card_path}/myraid_box_card.js?ver={version}")
        
        _LOGGER.info("万象盒子卡片已注册，版本: %s", version)
        return True
    except Exception as e:
        _LOGGER.error("注册万象盒子卡片失败: %s", e)
        return False


async def async_setup(hass: HomeAssistant, config: Dict) -> bool:
    """设置组件"""
    if DOMAIN not in config_entries.HANDLERS:
        hass.data[DOMAIN] = {}
        config_entries.HANDLERS.register(DOMAIN)(MyriadBoxConfigFlow)
    
    # 注册API端点
    hass.http.register_view(MyraidBoxAPIView)
    
    # 注册卡片资源
    await setup_myraid_card(hass)
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """通过配置条目设置"""
    services_dir = str(Path(__file__).parent / "services")
    await discover_services(hass, services_dir)
    
    coordinators = {}
    enabled_services = [
        k.replace("enable_", "") 
        for k, v in entry.data.items() 
        if k.startswith("enable_") and v
    ]
    
    failed_services = []
    
    for service_id in enabled_services:
        try:
            coordinator = ServiceCoordinator(hass, entry, service_id)
            await coordinator.async_config_entry_first_refresh()
            coordinators[service_id] = coordinator
            _LOGGER.info("成功初始化服务: %s", service_id)
        except Exception as e:
            _LOGGER.error("初始化服务 %s 失败: %s", service_id, str(e))
            failed_services.append(service_id)
    
    if not coordinators and enabled_services:
        _LOGGER.error("所有服务初始化都失败了")
        raise ConfigEntryNotReady("所有服务初始化失败")
    
    if failed_services:
        _LOGGER.warning("以下服务初始化失败: %s", failed_services)
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinators
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """重新加载配置条目"""
    _LOGGER.debug("重新加载万象盒子配置条目")
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载集成"""
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        return False

    coordinators = hass.data[DOMAIN][entry.entry_id]
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    for coordinator in coordinators.values():
        if hasattr(coordinator.service, 'async_unload'):
            await coordinator.service.async_unload()
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.debug("成功卸载万象盒子集成")
    
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """移除配置条目时的清理工作"""
    _LOGGER.debug("移除万象盒子配置条目")
    ent_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    for entity in entities:
        ent_reg.async_remove(entity.entity_id)
    
    dev_reg = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    for device in devices:
        device_entities = er.async_entries_for_device(ent_reg, device.id)
        if not device_entities:
            dev_reg.async_remove_device(device.id)


@callback
def async_cleanup_disabled_services(hass: HomeAssistant, entry: ConfigEntry, previous_config: Dict[str, Any]) -> None:
    """清理被禁用的服务的设备和实体"""
    current_enabled_services = [
        k.replace("enable_", "") 
        for k, v in entry.data.items() 
        if k.startswith("enable_") and v
    ]
    
    previous_enabled_services = [
        k.replace("enable_", "") 
        for k, v in previous_config.items() 
        if k.startswith("enable_") and v
    ]
    
    # 找出被禁用的服务
    disabled_services = set(previous_enabled_services) - set(current_enabled_services)
    
    if disabled_services:
        _LOGGER.debug("清理被禁用的服务设备: %s", disabled_services)
        _cleanup_service_devices(hass, entry, disabled_services)


@callback
def _cleanup_service_devices(hass: HomeAssistant, entry: ConfigEntry, service_ids: set) -> None:
    """清理特定服务的设备和实体"""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    
    # 获取所有属于此配置条目的设备
    devices = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    
    for device in devices:
        # 检查设备标识符是否包含被禁用的服务ID
        for identifier in device.identifiers:
            if identifier[0] == DOMAIN:
                device_service_id = identifier[1].split('_')[0]  # 提取服务ID
                if device_service_id in service_ids:
                    # 删除该设备的所有实体
                    device_entities = er.async_entries_for_device(ent_reg, device.id)
                    for entity in device_entities:
                        ent_reg.async_remove(entity.entity_id)
                    
                    # 删除设备
                    dev_reg.async_remove_device(device.id)
                    _LOGGER.debug("已移除被禁用服务 %s 的设备", device_service_id)
                    break


@callback
def async_update_sensors(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """动态更新传感器"""
    _LOGGER.debug("动态更新传感器")
    hass.async_create_task(async_reload_entry(hass, entry))
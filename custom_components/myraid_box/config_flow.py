from __future__ import annotations
from typing import Any, Dict
import hashlib
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, DEVICE_MANUFACTURER, SERVICE_REGISTRY
from .flow_base import MyriadBoxFlowHandler

@config_entries.HANDLERS.register(DOMAIN)
class MyriadBoxConfigFlow(config_entries.ConfigFlow, MyriadBoxFlowHandler):
    """支持中文的配置流"""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """初始化流程实例"""
        config_entries.ConfigFlow.__init__(self)
        MyriadBoxFlowHandler.__init__(self, self.hass, {})

    async def async_step_user(self, user_input: Dict[str, Any] = None) -> FlowResult:
        """处理用户初始步骤"""
        self._async_abort_entries_match()
        
        if user_input is not None:
            return await self.async_handle_next_service()
        return await self.async_start_flow()

    async def async_step_service_config(self, user_input: Dict[str, Any] = None) -> FlowResult:
        """处理服务配置步骤"""
        if user_input is None:
            return await self.async_show_service_config_form(
                self._services_order[self._current_service_index]
            )
        return await self.async_handle_service_config(
            self._services_order[self._current_service_index],
            user_input
        )

    async def async_finalize_config(self) -> FlowResult:
        """最终配置验证"""
        enabled_services = [
            sid for sid in self._services_order
            if self._config_data.get(f"enable_{sid}", False)
        ]

        if not enabled_services:
            return self.async_show_form(
                step_id="service_config",
                data_schema=vol.Schema({}),
                errors={"base": "no_services_selected"},
                description_placeholders={
                    "available_services": "\n".join(
                        f"• {SERVICE_REGISTRY[sid]().name} ({sid})"
                        for sid in self._services_order
                    )
                }
            )

        unique_id = hashlib.md5(
            str(sorted(self._config_data.items())).encode()
        ).hexdigest()
        await self.async_set_unique_id(f"myraid_box_{unique_id}")
        self._abort_if_unique_id_configured()
        
        return self.async_create_entry(
            title=f"{DEVICE_MANUFACTURER}",
            data=self._config_data,
            description="已启用服务: " + ", ".join(
                SERVICE_REGISTRY[sid]().name for sid in enabled_services
            )
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """创建选项流"""
        return MyriadBoxOptionsFlow(config_entry)

class MyriadBoxOptionsFlow(config_entries.OptionsFlow, MyriadBoxFlowHandler):
    """支持中文和动态实体管理的选项流"""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """初始化选项流"""
        config_entries.OptionsFlow.__init__(self)
        MyriadBoxFlowHandler.__init__(
            self, 
            self.hass, 
            dict(config_entry.data)
        )
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Dict[str, Any] = None) -> FlowResult:
        """初始化选项配置"""
        return await self.async_start_flow()

    async def async_step_service_config(self, user_input: Dict[str, Any] = None) -> FlowResult:
        """处理服务配置步骤"""
        if user_input is None:
            return await self.async_show_service_config_form(
                self._services_order[self._current_service_index]
            )
        return await self.async_handle_service_config(
            self._services_order[self._current_service_index],
            user_input
        )

    async def async_finalize_config(self) -> FlowResult:
        """最终配置验证 - 更新配置并重新加载"""
        enabled_services = [
            sid for sid in self._services_order
            if self._config_data.get(f"enable_{sid}", False)
        ]

        if not enabled_services:
            return self.async_show_form(
                step_id="service_config",
                data_schema=vol.Schema({}),
                errors={"base": "no_services_selected"},
                description_placeholders={
                    "available_services": "\n".join(
                        f"• {SERVICE_REGISTRY[sid]().name} ({sid})"
                        for sid in self._services_order
                    )
                }
            )

        # 更新配置条目数据
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=self._config_data
        )
        
        # 触发重新加载以创建/移除实体
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)
        
        return self.async_create_entry(title="", data=None)
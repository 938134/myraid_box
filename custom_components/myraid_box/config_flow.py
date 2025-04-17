from __future__ import annotations
import logging
from typing import Any, Dict, Optional, List
from pathlib import Path
import hashlib
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback, HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode
)

from .const import DOMAIN, SERVICE_REGISTRY, discover_services

_LOGGER = logging.getLogger(__name__)

class MyraidBoxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """配置流实现"""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """初始化流程实例"""
        self._services_order: List[str] = []
        self._current_service_index: int = 0
        self._config_data: Dict[str, Any] = {}
        self._available_services: Dict[str, str] = {}
        
    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """处理用户初始步骤"""
        if user_input is not None:
            # 用户已提交第一步，直接进入服务配置
            return await self._async_handle_next_service()
        
        # 自动发现服务模块
        if not SERVICE_REGISTRY:
            services_dir = str(Path(__file__).parent / "services")
            await discover_services(self.hass, services_dir)
            if not SERVICE_REGISTRY:
                return self.async_abort(
                    reason="no_services",
                    description_placeholders={"error": "未发现任何可用的服务模块"}
                )
    
        # 初始化服务顺序
        self._services_order = sorted(
            SERVICE_REGISTRY.keys(),
            key=lambda x: SERVICE_REGISTRY[x]().name
        )
        self._current_service_index = 0
        self._config_data = {}
        return await self._async_handle_next_service()
        # 显示空表单（不需要用户输入，直接进入下一步）
        #return self.async_show_form(
            #step_id="user",
            #data_schema=vol.Schema({})  # 空表单
        #)

    async def _async_handle_next_service(self) -> FlowResult:
        """处理下一个服务配置"""
        if self._current_service_index >= len(self._services_order):
            return await self._async_finalize_config()
            
        service_id = self._services_order[self._current_service_index]
        return await self.async_step_service_config(service_id=service_id)

    def _build_service_schema(self, service_id: str) -> Dict:
        """构建动态表单schema"""
        service = SERVICE_REGISTRY[service_id]()
        schema = {
            vol.Required(
                f"enable_{service_id}",
                default=self._config_data.get(f"enable_{service_id}", False),
                description=f"启用 {service.name} 服务"
            ): BooleanSelector()
        }

        for field, config in service.config_fields.items():
            field_key = f"{service_id}_{field}"
            default_val = self._config_data.get(field_key, config.get("default"))
            
            # 组合 name 和 description
            field_description = f"{config.get('name', field)}"
            if 'description' in config:
                field_description += f"【{config['description']}】"
            
            # URL类型字段
            if field == "url":
                schema[vol.Required(
                    field_key,
                    default=default_val or config.get("default"),
                    description=field_description
                )] = TextSelector(TextSelectorConfig(type="url"))

            # 数字类型字段
            elif config.get("type") == "int":
                schema[vol.Optional(
                    field_key,
                    default=default_val,
                    description=field_description
                )] = NumberSelector(
                    NumberSelectorConfig(
                        mode=NumberSelectorMode.BOX
                    )
                )

            # 布尔类型字段
            elif config.get("type") == "bool":
                schema[vol.Optional(
                    field_key,
                    default=default_val,
                    description=field_description
                )] = BooleanSelector()

            # 选择类型字段
            elif "options" in config:
                selector_config = {
                    "options": config["options"],
                    "mode": SelectSelectorMode.DROPDOWN
                }
                if config.get("translation_key"):
                    selector_config["translation_key"] = config["translation_key"]
                
                schema[vol.Optional(
                    field_key,
                    default=default_val,
                    description=field_description
                )] = SelectSelector(SelectSelectorConfig(**selector_config))

            # 默认文本输入
            else:
                input_type = "password" if config.get("type") == "password" else "text"
                schema[vol.Optional(
                    field_key,
                    default=default_val,
                    description=field_description
                )] = TextSelector(TextSelectorConfig(type=input_type))

        return schema

    async def async_step_service_config(self, user_input=None, service_id=None):
        """带间隔验证的配置步骤"""
        if service_id is None:
            if self._current_service_index < len(self._services_order):
                service_id = self._services_order[self._current_service_index]
            else:
                return await self._async_finalize_config()
        
        if user_input is None:
            # 生成并显示表单
            schema = self._build_service_schema(service_id)
            service_description = SERVICE_REGISTRY[service_id]().description
            return self.async_show_form(
                step_id="service_config",
                data_schema=vol.Schema(schema),  # 确保使用 vol.Schema
                description_placeholders={
                    "service_name": SERVICE_REGISTRY[service_id]().name,
                    "service_description": service_description,
                    "current_step": f"{self._current_service_index + 1}/{len(self._services_order)}"
                }
            )
        
        try:
            service_class = SERVICE_REGISTRY[service_id]
            if hasattr(service_class, 'validate_config'):
                service_class.validate_config({
                    k.split('_')[-1]: v 
                    for k, v in user_input.items() 
                    if k.startswith(service_id)
                })
            
            self._config_data.update(user_input)
            self._current_service_index += 1
            return await self._async_handle_next_service()
            
        except ValueError as err:
            service_description = SERVICE_REGISTRY[service_id]().description
            return self.async_show_form(
                step_id="service_config",
                errors={"base": str(err)},
                data_schema=vol.Schema(self._build_service_schema(service_id)),  # 确保使用 vol.Schema
                description_placeholders={
                    "service_name": SERVICE_REGISTRY[service_id]().name,
                    "service_description": service_description,
                    "current_step": f"{self._current_service_index + 1}/{len(self._services_order)}"
                }
            )
    
    async def _async_finalize_config(self) -> FlowResult:
        """最终配置验证和创建"""
        enabled_services = [
            sid for sid in self._services_order 
            if self._config_data.get(f"enable_{sid}", False)
        ]
        
        if not enabled_services:
            return self.async_show_form(
                step_id="user",
                errors={"base": "必须启用至少1项服务"},
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
            title=f"万象盒子 ({len(enabled_services)}项服务)",
            data=self._config_data,
            description="已启用服务: " + ", ".join(
                SERVICE_REGISTRY[sid]().name for sid in enabled_services
            )
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """创建选项流"""
        return MyraidBoxOptionsFlow(config_entry)

class MyraidBoxOptionsFlow(config_entries.OptionsFlow):
    """选项配置流"""
    
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """初始化选项流"""
        self.config_entry = config_entry
        self._config_data = dict(config_entry.data)
        self._services_order = [
            k.replace("enable_", "") 
            for k in config_entry.data 
            if k.startswith("enable_")
        ]
        self._current_service_index = 0

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """初始化选项配置"""
        if not self._services_order:
            return self.async_abort(reason="no_configured_services")
            
        return await self._async_handle_next_service()

    async def _async_step_service_config(self, service_id: str) -> FlowResult:
        """生成服务选项表单"""
        service = SERVICE_REGISTRY[service_id]()
        schema = {
            vol.Required(
                f"enable_{service_id}",
                default=self._config_data.get(f"enable_{service_id}", False),
                description=f"启用 {service.name} 服务"
            ): bool
        }
        
        for field, config in service.config_fields.items():
            field_key = f"{service_id}_{field}"
            current_val = self._config_data.get(field_key, config.get("default"))
            
            # 组合 name 和 description
            field_description = f"{config.get('name', field)}"
            if 'description' in config:
                field_description += f"【{config['description']}】"
            
            if config.get("type") == "int":
                schema[vol.Optional(
                    field_key,
                    default=current_val,
                    description=field_description
                )] = vol.All(vol.Coerce(int), vol.Range(min=config.get("min", 0)))
            else:
                schema[vol.Optional(
                    field_key,
                    default=current_val,
                    description=field_description
                )] = str

        return self.async_show_form(
            step_id="service_config",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "service_name": service.name,
                #"current_step": f"{self._current_service_index + 1}/{len(self._services_order)}"
            }
        )

    async def async_step_service_config(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """处理选项提交"""
        if user_input is None:
            service_id = self._services_order[self._current_service_index]
            service_description = SERVICE_REGISTRY[service_id]().description  # 获取服务描述
            return await self._async_step_service_config(service_id)
    
        service_id = self._services_order[self._current_service_index]
        
        try:
            self._config_data.update(user_input)
            
            if not user_input.get(f"enable_{service_id}", False):
                for key in list(self._config_data.keys()):
                    if key.startswith(f"{service_id}_"):
                        self._config_data.pop(key)
            
            self._current_service_index += 1
            return await self._async_handle_next_service()
            
        except vol.Invalid as err:
            return self.async_show_form(
                step_id="service_config",
                errors={"base": str(err)},
                description_placeholders={
                    "service_name": SERVICE_REGISTRY[service_id]().name,
                    "service_description": SERVICE_REGISTRY[service_id]().description  # 使用服务描述
                }
            )

    async def _async_handle_next_service(self) -> FlowResult:
        """处理下一个服务选项"""
        if self._current_service_index >= len(self._services_order):
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=self._config_data
            )
            return self.async_create_entry(title="", data=None)
            
        service_id = self._services_order[self._current_service_index]
        return await self._async_step_service_config(service_id)
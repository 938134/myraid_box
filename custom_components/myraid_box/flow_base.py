from __future__ import annotations
import logging
from typing import Any, Dict, Optional, List
from pathlib import Path
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    TextSelector, TextSelectorConfig,
    BooleanSelector,
    NumberSelector, NumberSelectorConfig, NumberSelectorMode,
    SelectSelector, SelectSelectorConfig, SelectSelectorMode
)

from .const import DOMAIN, SERVICE_REGISTRY, discover_services

_LOGGER = logging.getLogger(__name__)

class MyriadBoxFlowHandler:
    """完全整合的流处理基类"""
    
    def __init__(self, hass: HomeAssistant, config_data: Dict[str, Any]):
        """初始化共享处理器"""
        self.hass = hass
        self._config_data = config_data
        self._services_order: List[str] = []
        self._current_service_index: int = 0

    async def async_initialize_services(self) -> bool:
        """初始化服务（包含自动发现）"""
        services_dir = str(Path(__file__).parent / "services")
        await discover_services(self.hass, services_dir)
        
        if not SERVICE_REGISTRY:
            _LOGGER.error("未发现任何可用的服务模块")
            return False
            
        self._services_order = sorted(
            SERVICE_REGISTRY.keys(),
            key=lambda x: SERVICE_REGISTRY[x]().name
        )
        self._current_service_index = 0
        return True

    async def async_start_flow(self) -> FlowResult:
        """启动流程（子类可覆盖）"""
        if not await self.async_initialize_services():
            return self.async_abort(
                reason="no_services",
                description_placeholders={"error": "未发现任何可用的服务模块"}
            )
        return await self.async_handle_next_service()

    async def async_handle_next_service(self) -> FlowResult:
        """处理下一个服务配置"""
        if self._current_service_index >= len(self._services_order):
            return await self.async_finalize_config()
            
        service_id = self._services_order[self._current_service_index]
        return await self.async_show_service_config_form(service_id)

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
                
            if config["type"] == "str":
                schema[vol.Optional(
                    field_key,
                    default=default_val,
                    description=field_description
                )] = TextSelector(TextSelectorConfig(type="text"))
            elif config["type"] == "int":
                schema[vol.Optional(
                    field_key,
                    default=int(default_val) if default_val else config.get("default"),
                    description=field_description
                )] = NumberSelector(NumberSelectorConfig(
                    mode=NumberSelectorMode.BOX
                ))
            elif config["type"] == "select":
                schema[vol.Optional(
                    field_key,
                    default=default_val,
                    description=field_description
                )] = SelectSelector(SelectSelectorConfig(
                    options=config.get("options", []),
                    mode=SelectSelectorMode.DROPDOWN
                ))
            elif config["type"] == "password":
                schema[vol.Optional(
                    field_key,
                    default=default_val,
                    description=field_description
                )] = TextSelector(TextSelectorConfig(type="password"))
    
        return schema

    async def async_show_service_config_form(
        self, 
        service_id: str,
        errors: Optional[Dict[str, str]] = None
    ) -> FlowResult:
        """显示服务配置表单"""
        schema = self._build_service_schema(service_id)
        service = SERVICE_REGISTRY[service_id]()
        return self.async_show_form(
            step_id="service_config",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "service_name": service.name,
                "service_description": service.description,
                "current_step": f"{self._current_service_index + 1}/{len(self._services_order)}"
            }
        )

    async def async_handle_service_config(
        self,
        service_id: str,
        user_input: Dict[str, Any]
    ) -> FlowResult:
        """处理服务配置提交"""
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
            return await self.async_handle_next_service()
            
        except ValueError as err:
            return await self.async_show_service_config_form(
                service_id,
                errors={"base": str(err)}
            )

    async def async_finalize_config(self) -> FlowResult:
        """最终配置验证（子类必须实现）"""
        raise NotImplementedError

    def async_show_form(self, *args, **kwargs):
        """显示表单的抽象方法"""
        raise NotImplementedError

    def async_abort(self, *args, **kwargs):
        """中止流程的抽象方法"""
        raise NotImplementedError

    def async_create_entry(self, *args, **kwargs):
        """创建配置条目的抽象方法"""
        raise NotImplementedError
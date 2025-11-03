from __future__ import annotations
from typing import Any, Dict, List
import hashlib
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from pathlib import Path

from .const import DOMAIN, DEVICE_MANUFACTURER, SERVICE_REGISTRY, discover_services

class BaseMyriadBoxFlow:
    """万象盒子配置流的基类，包含通用方法"""
    
    def __init__(self):
        """初始化基础流"""
        self._services_loaded = False
        self._selected_services: List[str] = []
        self._current_service_index = 0

    async def _ensure_services_loaded(self, hass) -> None:
        """确保服务已加载"""
        if not self._services_loaded:
            services_dir = str(Path(__file__).parent / "services")
            await discover_services(hass, services_dir)
            self._services_loaded = True

    def _get_service_options(self) -> Dict[str, str]:
        """获取服务选项"""
        options = {}
        for service_id, service_class in SERVICE_REGISTRY.items():
            service = service_class()
            options[service_id] = service.name
        return options

    def _get_default_enabled_services(self) -> List[str]:
        """获取默认启用的服务"""
        return list(SERVICE_REGISTRY.keys())

    def _build_service_schema(self, service_id: str, current_data: Dict[str, Any] = None) -> vol.Schema:
        """构建单个服务的配置表单"""
        service_class = SERVICE_REGISTRY[service_id]
        service = service_class()
        schema_dict = {}

        for field, config in service.config_fields.items():
            # 确定实际使用的字段键名
            if config["type"] == "password":
                # 密码字段使用 _password 后缀来确保显示为密码输入框
                field_key = f"{service_id}_{field}_password"
            else:
                field_key = f"{service_id}_{field}"
            
            if self._should_skip_field(field, config):
                continue
                
            # 获取字段描述
            field_description = config.get('name', field)
            if 'description' in config:
                field_description += f" - {config['description']}"
            
            # 获取默认值
            if current_data:
                # 查找原始字段名或密码字段名的值
                original_field_key = f"{service_id}_{field}"
                if original_field_key in current_data:
                    default_value = current_data[original_field_key]
                elif field_key in current_data:
                    default_value = current_data[field_key]
                else:
                    default_value = config.get("default")
            else:
                default_value = config.get("default")
            
            # 根据字段类型构建schema
            if config["type"] == "str":
                schema_dict[vol.Optional(
                    field_key,
                    default=default_value or "",
                    description=field_description
                )] = cv.string
            elif config["type"] == "int":
                schema_dict[vol.Optional(
                    field_key,
                    default=int(default_value) if default_value else config.get("default", 10),
                    description=field_description
                )] = vol.Coerce(int)
            elif config["type"] == "select":
                schema_dict[vol.Optional(
                    field_key,
                    default=default_value or config.get("default", ""),
                    description=field_description
                )] = vol.In(config.get("options", []))
            elif config["type"] == "password":
                # 密码字段类型 - 使用密码输入框
                schema_dict[vol.Optional(
                    field_key,
                    default=default_value or "",
                    description=field_description
                )] = cv.string

        return vol.Schema(schema_dict)

    def _should_skip_field(self, field: str, config: Dict) -> bool:
        """判断是否跳过该字段"""
        skip_fields = ["url"]
        skip_descriptions = ["API地址", "官网地址"]
        
        if field in skip_fields:
            return True
            
        description = config.get('description', '')
        if any(skip_desc in description for skip_desc in skip_descriptions):
            return True
            
        return False

    def _get_service_description_placeholders(self, service_id: str) -> Dict[str, str]:
        """获取服务的描述占位符"""
        service_class = SERVICE_REGISTRY[service_id]
        service = service_class()
        
        # 进度信息单独一行，配置说明在下面
        progress_info = f"进度: {self._current_service_index + 1}/{len(self._selected_services)}"
        combined_help = f"{progress_info}\n{service.config_help}"
        
        return {
            "service_name": service.name,
            "current_step": f"{self._current_service_index + 1}",
            "total_steps": f"{len(self._selected_services)}",
            "config_help": combined_help
        }

    async def _validate_service_config(self, service_id: str, user_input: Dict[str, Any]) -> Dict[str, str]:
        """验证单个服务的配置"""
        errors = {}
        service_class = SERVICE_REGISTRY[service_id]
        
        try:
            # 构建服务配置，处理密码字段名映射
            service_config = {}
            for field, config in service_class().config_fields.items():
                original_field_key = f"{service_id}_{field}"
                password_field_key = f"{service_id}_{field}_password"
                
                # 检查是否有密码字段的替代键名
                if config["type"] == "password" and password_field_key in user_input:
                    service_config[field] = user_input[password_field_key]
                elif original_field_key in user_input:
                    service_config[field] = user_input[original_field_key]
            
            service_class.validate_config(service_config)
        except ValueError as e:
            errors["base"] = str(e)
            
        return errors

    def _process_password_fields(self, user_input: Dict[str, Any]) -> Dict[str, Any]:
        """处理密码字段名映射，将 _password 后缀的字段映射回原始字段名"""
        processed_input = {}
        for key, value in user_input.items():
            # 如果键以 _password 结尾，映射回原始字段名
            if key.endswith('_password'):
                original_key = key.replace('_password', '')
                processed_input[original_key] = value
            else:
                processed_input[key] = value
        return processed_input


@config_entries.HANDLERS.register(DOMAIN)
class MyriadBoxConfigFlow(config_entries.ConfigFlow, BaseMyriadBoxFlow):
    """优雅的分步配置流"""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """初始化配置流"""
        BaseMyriadBoxFlow.__init__(self)
        self._config_data = {}

    async def async_step_user(self, user_input: Dict[str, Any] = None) -> FlowResult:
        """第一步：选择要配置的服务"""
        self._async_abort_entries_match()
        
        await self._ensure_services_loaded(self.hass)

        if user_input is not None:
            self._selected_services = user_input["selected_services"]
            if not self._selected_services:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema({
                        vol.Required("selected_services"): cv.multi_select(
                            self._get_service_options()
                        )
                    }),
                    errors={"base": "no_services_selected"}
                )
            self._current_service_index = 0
            return await self.async_step_service_config()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(
                    "selected_services",
                    default=self._get_default_enabled_services(),
                    description="选择要配置的服务"
                ): cv.multi_select(self._get_service_options())
            }),
            description_placeholders={
                "services_count": str(len(SERVICE_REGISTRY))
            }
        )

    async def async_step_service_config(self, user_input: Dict[str, Any] = None) -> FlowResult:
        """第二步：逐个配置选中的服务"""
        if self._current_service_index >= len(self._selected_services):
            return await self.async_step_final()

        service_id = self._selected_services[self._current_service_index]
        service_class = SERVICE_REGISTRY[service_id]
        service = service_class()

        if user_input is not None:
            # 处理密码字段名映射
            processed_input = self._process_password_fields(user_input)
            
            # 验证并保存配置
            errors = await self._validate_service_config(service_id, processed_input)
            if errors:
                return self.async_show_form(
                    step_id="service_config",
                    data_schema=self._build_service_schema(service_id),
                    errors=errors,
                    description_placeholders=self._get_service_description_placeholders(service_id)
                )
            
            # 保存配置并前进到下一个服务
            self._config_data.update(processed_input)
            self._config_data[f"enable_{service_id}"] = True
            self._current_service_index += 1
            return await self.async_step_service_config()

        return self.async_show_form(
            step_id="service_config",
            data_schema=self._build_service_schema(service_id),
            description_placeholders=self._get_service_description_placeholders(service_id)
        )

    async def async_step_final(self, user_input: Dict[str, Any] = None) -> FlowResult:
        """最后一步：确认配置"""
        if user_input is not None:
            return await self._async_create_entry()

        # 显示配置摘要
        service_names = []
        for service_id in self._selected_services:
            service_class = SERVICE_REGISTRY[service_id]
            service_names.append(service_class().name)

        return self.async_show_form(
            step_id="final",
            data_schema=vol.Schema({}),
            description_placeholders={
                "services_list": "\n".join([f"• {name}" for name in service_names]),
                "services_count": str(len(self._selected_services))
            }
        )

    async def _async_create_entry(self) -> FlowResult:
        """创建配置条目"""
        # 确保未选择的服务被禁用
        for service_id in SERVICE_REGISTRY.keys():
            if service_id not in self._selected_services:
                self._config_data[f"enable_{service_id}"] = False
        
        # 生成唯一ID
        unique_id = hashlib.md5(
            str(sorted(self._config_data.items())).encode()
        ).hexdigest()
        
        await self.async_set_unique_id(f"myraid_box_{unique_id}")
        self._abort_if_unique_id_configured()
        
        return self.async_create_entry(
            title=f"{DEVICE_MANUFACTURER}",
            data=self._config_data,
            description=f"已启用 {len(self._selected_services)} 个服务"
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """创建选项流"""
        return MyriadBoxOptionsFlow(config_entry)

class MyriadBoxOptionsFlow(config_entries.OptionsFlow, BaseMyriadBoxFlow):
    """简洁的选项配置流 - 通过勾选状态直接管理服务"""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """初始化选项流"""
        BaseMyriadBoxFlow.__init__(self)
        self.config_entry = config_entry
        self._updated_config = dict(config_entry.data)
        self._previous_config = dict(config_entry.data)  # 保存之前的配置用于比较

    async def async_step_init(self, user_input: Dict[str, Any] = None) -> FlowResult:
        """第一步：选择要启用的服务和配置"""
        await self._ensure_services_loaded(self.hass)

        if user_input is not None:
            # 更新服务启用状态
            selected_services = []
            for service_id in SERVICE_REGISTRY.keys():
                enable_key = f"enable_{service_id}"
                is_enabled = user_input.get(enable_key, False)
                self._updated_config[enable_key] = is_enabled
                
                if is_enabled:
                    selected_services.append(service_id)
            
            # 如果有选中的服务，进入配置步骤
            if selected_services:
                self._selected_services = selected_services
                self._current_service_index = 0
                return await self.async_step_service_config()
            else:
                # 没有选中任何服务，直接保存
                return await self._async_save_config()

        # 构建服务选择表单
        schema_dict = {}
        for service_id, service_class in SERVICE_REGISTRY.items():
            service = service_class()
            is_enabled = self._updated_config.get(f"enable_{service_id}", False)
            
            schema_dict[vol.Optional(
                f"enable_{service_id}",
                default=is_enabled,
                description=f"{service.description}"
            )] = bool

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "total_count": str(len(SERVICE_REGISTRY))
            }
        )

    async def async_step_service_config(self, user_input: Dict[str, Any] = None) -> FlowResult:
        """第二步：逐个配置选中的服务"""
        if self._current_service_index >= len(self._selected_services):
            return await self._async_save_config()

        service_id = self._selected_services[self._current_service_index]
        service_class = SERVICE_REGISTRY[service_id]
        service = service_class()

        if user_input is not None:
            # 处理密码字段名映射
            processed_input = self._process_password_fields(user_input)
            
            # 验证配置
            errors = await self._validate_service_config(service_id, processed_input)
            if errors:
                return self.async_show_form(
                    step_id="service_config",
                    data_schema=self._build_service_schema(service_id, self._updated_config),
                    errors=errors,
                    description_placeholders=self._get_service_description_placeholders(service_id)
                )
            
            # 更新配置并前进
            self._updated_config.update(processed_input)
            self._current_service_index += 1
            return await self.async_step_service_config()

        return self.async_show_form(
            step_id="service_config",
            data_schema=self._build_service_schema(service_id, self._updated_config),
            description_placeholders=self._get_service_description_placeholders(service_id)
        )

    async def _async_save_config(self) -> FlowResult:
        """保存配置并重新加载"""
        # 更新配置条目
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=self._updated_config
        )
        
        # 清理被禁用的服务的设备
        from . import async_cleanup_disabled_services
        async_cleanup_disabled_services(self.hass, self.config_entry, self._previous_config)
        
        # 重新加载集成 - 这是关键修复
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)
        
        # 返回空数据表示成功
        return self.async_create_entry(title="", data={})
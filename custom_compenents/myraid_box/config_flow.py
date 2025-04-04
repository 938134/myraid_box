from __future__ import annotations
import logging
from typing import Any, Dict

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

from .const import DOMAIN, ServiceRegistry

_LOGGER = logging.getLogger(__name__)

class MyraidBoxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """配置流程处理器"""

    VERSION = 1
    _config_data: Dict[str, Any] = {}

    async def async_step_user(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        """处理初始步骤"""
        if user_input is not None:
            self._config_data.update(user_input)
            return await self._async_step_service_config(ServiceRegistry.order()[0])

        # 动态生成服务启用表单
        schema = {
            vol.Optional(
                f"enable_{service_type}",
                default=True,
                description=self._build_service_description(service_type)
            ): bool
            for service_type in ServiceRegistry.order()
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema),
            description_placeholders={"services_intro": "请选择需要启用的服务"}
        )

    def _build_service_description(self, service_type: str) -> str:
        """构建服务描述"""
        config = ServiceRegistry.get(service_type)
        return f"{config['description']}\n官网：{config['url']}"

    # ...其余配置流程方法保持不变...
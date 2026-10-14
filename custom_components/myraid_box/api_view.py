"""MyraidBoxAPIView：卡片数据端点。

从 ``__init__.py`` 抽出到独立模块，理由：
- 这是**HTTP 端点**（自定义 HomeAssistantView），职责和入口 setup 完全独立；
  放在 ``__init__.py`` 会让入口文件既管 setup 又管 HTTP，读者要跳来跳去。
- 拆分后如需给端点加认证 / 限流 / 缓存逻辑，只需改这一文件。

安全：
- ``requires_auth = True``：请求必须携带 HA 有效 token。
- 2.x 修复前是 ``False``，会向任意 HTTP 客户端吐出 token / 私钥；这是 v2.1.0 的安全修复。

响应契约（v3.0）：
- ``{"<service_id>": {"status": "success", "data": ..., "update_time": ...}}``
- ``{"<service_id>": {"status": "error", "error": "..."}}``
- 无 entry 时返回 404 ``{"error": "集成未加载"}``
"""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN


class MyraidBoxAPIView(HomeAssistantView):
    """卡片数据端点。

    URL: ``/api/myraid_box/data``
    权限：仅 HA 已认证用户（``requires_auth = True``）
    """

    url = "/api/myraid_box/data"
    name = "api:myraid_box:data"
    requires_auth = True
    requires_admin = False

    async def get(self, request):  # type: ignore[override]
        hass: HomeAssistant = request.app["hass"]

        entries = config_entries.async_entries(hass, DOMAIN)
        if not entries:
            return self.json({"error": "集成未加载"}, status=404)

        result: dict[str, Any] = {}

        for entry in entries:
            runtime = getattr(entry, "runtime_data", None)
            if not runtime:
                continue
            for service_id, coordinator in runtime["coordinators"].items():
                data = coordinator.data
                if not data:
                    continue
                if data.get("status") == "success":
                    result[service_id] = {
                        "status": "success",
                        "data": data.get("data", {}),
                        "update_time": data.get("update_time"),
                    }
                else:
                    result[service_id] = {
                        "status": "error",
                        "error": data.get("error", "未知错误"),
                    }

        return self.json(result)

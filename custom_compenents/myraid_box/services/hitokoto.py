import logging
from datetime import timedelta
from .base import BaseService
from ..const import register_service, HITOKOTO_TYPE_MAP

_LOGGER = logging.getLogger(__name__)

@register_service(
    name="每日一言",
    description="获取每日励志名言",
    url="https://v1.hitokoto.cn/?c=d&c=i&c=k",
    interval=timedelta(minutes=30),
    icon="mdi:format-quote-close",
    attributes={
        "from": {"name": "来源", "icon": "mdi:source-branch"},
        "from_who": {"name": "作者", "icon": "mdi:account"},
        "type": {"name": "分类", "icon": "mdi:tag"}
    }
)
class HitokotoService(BaseService):
    async def async_update_data(self) -> Dict[str, Any]:
        try:
            async with self.session.get(
                ServiceRegistry.get("hitokoto")["url"]
            ) as resp:
                data = await resp.json()
                data["type_display"] = HITOKOTO_TYPE_MAP.get(data.get("type", "a"), "未知")
                return data
        except Exception as e:
            _LOGGER.error(f"获取一言数据失败: {e}")
            return {"error": str(e)}
    
    @classmethod
    def config_fields(cls) -> Dict[str, Dict[str, Any]]:
        return {}
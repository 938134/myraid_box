from datetime import timedelta
from .base import BaseService
from ..const import register_service

@register_service(
    name="每日诗词",
    description="每日经典诗词推送",
    url="https://v1.jinrishici.com/all",
    interval=timedelta(hours=1),
    icon="mdi:book-open-variant",
    attributes={
        "author": {"name": "作者", "icon": "mdi:account"},
        "dynasty": {"name": "朝代", "icon": "mdi:calendar-clock"},
        "origin": {"name": "出处", "icon": "mdi:book-open"}
    }
)
class PoetryService(BaseService):
    async def async_update_data(self) -> dict:
        async with self.session.get(
            ServiceRegistry.get("poetry")["url"]
        ) as resp:
            return await resp.json()
    
    @classmethod
    def config_fields(cls) -> dict:
        return {}
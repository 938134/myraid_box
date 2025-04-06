from datetime import timedelta
from typing import Dict, Any
from ..service_base import BaseService, AttributeConfig
from ..const import DOMAIN, DEVICE_MANUFACTURER, DEVICE_MODEL

class PoetryService(BaseService):
    """每日诗词服务"""
    
    @property
    def service_id(self) -> str:
        return "poetry"
    
    @property
    def name(self) -> str:
        return "每日诗词"
    
    @property
    def description(self) -> str:
        return "每日接收经典诗词"
    
    @property
    def url(self) -> str:
        return "https://v1.jinrishici.com/all"
    
    @property
    def interval(self) -> timedelta:
        return timedelta(minutes=30)
    
    @property
    def icon(self) -> str:
        return "mdi:book-open-variant"
    
    @property
    def attributes(self) -> Dict[str, AttributeConfig]:
        return {
            "author": {
                "name": "作者",
                "icon": "mdi:account"
            },
            "origin": {
                "name": "出处",
                "icon": "mdi:book-open"
            },
            "dynasty": {
                "name": "朝代",
                "icon": "mdi:calendar-clock"
            }
        }
    
    async def fetch_data(self, coordinator, params):
        async with coordinator.session.get(self.url) as resp:
            return await resp.json()
    
    def format_main_value(self, data):
        if not data:
            return "暂无诗词数据"
        return data.get("content", "暂无诗词数据")
    
    def get_attribute_value(self, data, attribute):
        if attribute == "dynasty" and data:
            # 特殊处理朝代显示
            dynasty = data.get("dynasty", "")
            author = data.get("author", "")
            if dynasty and author and not author.startswith(dynasty):
                return f"{dynasty}·{author}"
        return super().get_attribute_value(data, attribute)
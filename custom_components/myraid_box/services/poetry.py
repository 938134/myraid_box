from datetime import timedelta
from typing import Dict, Any
from ..service_base import BaseService, AttributeConfig

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
    def icon(self) -> str:
        return "mdi:book-open-variant"
    
    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "url": {
                "name": "API地址",
                "type": "str",
                "required": True,
                "default": "https://v1.jinrishici.com/all",
                "description": "诗词API地址"
            },
            "interval": {
                "name": "更新间隔(分钟)",
                "type": "int",
                "required": True,
                "default": 30,
                "description": "数据更新间隔时间"
            }
        }
    
    @property
    def attributes(self) -> Dict[str, AttributeConfig]:
        return {
            "author": {"name": "作者", "icon": "mdi:account"},
            "origin": {"name": "出处", "icon": "mdi:book-open"},
            "dynasty": {"name": "朝代", "icon": "mdi:calendar-clock"}
        }
    
    async def fetch_data(self, coordinator, params):
        url = params["url"]
        async with coordinator.session.get(url) as resp:
            return await resp.json()
    
    def format_main_value(self, data):
        """格式化诗词主传感器显示"""
        if not data:
            return "暂无诗词数据"
        
        content = data.get("content", "")
        author = data.get("author", "")
        dynasty = data.get("dynasty", "")
        origin = data.get("origin", "")
        
        # 构建作者和朝代信息
        author_info = []
        if dynasty:
            author_info.append(dynasty)
        if author:
            author_info.append(author)
        author_str = "·".join(author_info) if author_info else ""
        
        # 构建出处信息
        origin_str = f"《{origin}》" if origin else ""
        
        # 组合最终输出
        result = [content]
        if author_str or origin_str:
            attribution = []
            if author_str:
                attribution.append(author_str)
            if origin_str:
                attribution.append(origin_str)
            result.append(" — " + " ".join(attribution))
        
        return "".join(result)
    
    def get_attribute_value(self, data, attribute):
        if attribute == "dynasty" and data:
            # 特殊处理朝代显示
            dynasty = data.get("dynasty", "")
            author = data.get("author", "")
            if dynasty and author and not author.startswith(dynasty):
                return f"{dynasty}·{author}"
        return super().get_attribute_value(data, attribute)
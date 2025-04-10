from datetime import timedelta
from typing import Dict, Any
from ..service_base import BaseService, AttributeConfig

class HitokotoService(BaseService):
    """每日一言服务"""
    
    TYPE_MAP = {
        "a": "动画", "b": "漫画", "c": "游戏", "d": "文学",
        "e": "原创", "f": "来自网络", "g": "其他", "h": "影视",
        "i": "诗词", "j": "网易云", "k": "哲学", "l": "抖机灵"
    }
    
    @property
    def service_id(self) -> str:
        return "hitokoto"
    
    @property
    def name(self) -> str:
        return "每日一言"
    
    @property
    def description(self) -> str:
        return "获取每日励志名言"
    
    @property
    def icon(self) -> str:
        return "mdi:format-quote-close"
    
    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "url": {
                "name": "API地址",
                "type": "str",
                "required": True,
                "default": "https://v1.hitokoto.cn/?c=d&c=i&c=k",
                "description": "一言API地址"
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
            "from": {"name": "来源", "icon": "mdi:source-branch"},
            "from_who": {"name": "作者", "icon": "mdi:account"},
            "type": {"name": "分类", "icon": "mdi:tag", "value_map": self.TYPE_MAP}
        }
    
    async def fetch_data(self, coordinator, params):
        url = params["url"]
        async with coordinator.session.get(url) as resp:
            return await resp.json()
    
    def format_sensor_value(self, data: Any, sensor_config: Dict[str, Any]) -> Any:
        """格式化一言主传感器显示"""
        if not data:
            return "暂无数据"
            
        parts = [data.get("hitokoto", "暂无数据")]
        if from_who := data.get("from_who"):
            parts.append(f"—— {from_who}")
        if from_source := data.get("from"):
            parts.append(f"「{from_source}」")
        if type_ := data.get("type"):
            parts.append(f"分类: {self.TYPE_MAP.get(type_, '未知')}")
        return "\n".join(parts)
    
    def get_sensor_attributes(self, data: Any, sensor_config: Dict[str, Any]) -> Dict[str, Any]:
        """获取一言传感器额外属性"""
        if not data:
            return {}
            
        attributes = {}
        for attr, attr_config in self.attributes.items():
            value = data.get(attr)
            if value is not None:
                if "value_map" in attr_config:
                    value = attr_config["value_map"].get(str(value), value)
                attributes[attr_config.get("name", attr)] = value
        
        return attributes
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlparse, parse_qs, urlencode
import logging
from ..service_base import BaseService, AttributeConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_HITOKOTO_API = "https://v1.hitokoto.cn/"

class HitokotoService(BaseService):
    """精简版一言服务"""

    CATEGORY_MAP = {
        "动画": "a", "漫画": "b", "游戏": "c", "文学": "d",
        "原创": "e", "来自网络": "f", "其他": "g", "影视": "h",
        "诗词": "i", "网易云": "j", "哲学": "k", "抖机灵": "l"
    }

    def __init__(self):
        super().__init__()

    @property
    def service_id(self) -> str:
        return "hitokoto"

    @property
    def name(self) -> str:
        return "每日一言"

    @property
    def description(self) -> str:
        return "获取励志名言（数据来源：一言API）"

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
                "default": DEFAULT_HITOKOTO_API,
                "description": "官方API地址",
                "placeholder": DEFAULT_HITOKOTO_API
            },
            "interval": {
                "name": "更新间隔（分钟）",
                "type": "int",
                "default": 10
            },
            "category": {
                "name": "分类",
                "type": "str",
                "required": False,
                "default": "哲学",
                "options": list(self.CATEGORY_MAP.keys())
            }
        }

    @property
    def attributes(self) -> Dict[str, AttributeConfig]:
        return {
            "from": {"name": "来源", "icon": "mdi:source-branch"},
            "from_who": {"name": "作者", "icon": "mdi:account"},
            "type": {"name": "分类", "icon": "mdi:tag", "value_map": {v: k for k, v in self.CATEGORY_MAP.items()}},
            "api_source": {"name": "数据源", "icon": "mdi:server"}
        }

    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取一言数据"""
        base_url = params["url"].strip()
        category = params.get("category", "哲学")
        category_code = self.CATEGORY_MAP.get(category, "k")
        
        # 构建最终的请求URL
        final_url = f"{base_url}?c={category_code}"

        # 发送请求
        response = await self._make_request(
            final_url,
            headers={
                "Accept": "application/json",
                "User-Agent": "HomeAssistant/MyriadBox"
            }
        )

        if response["status"] == "success":
            data = response["data"]
            return {
                **data,
                "update_time": datetime.now().isoformat(),
                "status": "success"
            }
        else:
            return {
                "error": response["error"],
                "update_time": datetime.now().isoformat(),
                "status": "error"
            }

    def format_sensor_value(self, data: Any, sensor_config: Dict[str, Any]) -> str:
        """格式化显示内容"""
        if not data or data.get("status") != "success":
            return "⚠️ 数据获取失败" if data and "error" in data else "⏳ 加载中..."
            
        parts = [data.get("hitokoto", "暂无内容")]
        
        if author := data.get("from_who"):
            parts.append(f"—— {author}")
            
        if source := data.get("from"):
            parts.append(f"「{source}」")
            
        return "\n".join(parts)

    def get_sensor_attributes(self, data: Any, sensor_config: Dict[str, Any]) -> Dict[str, Any]:
        """构建属性字典"""
        if not data:
            return {}
            
        attrs = {
            "update_time": data.get("update_time"),
            "api_source": data.get("api_source"),
            "status": data.get("status", "unknown")
        }
        
        for attr, config in self.attributes.items():
            if value := data.get(attr):
                if "value_map" in config:
                    value = config["value_map"].get(str(value), value)
                attrs[config["name"]] = value
                
        if "error" in data:
            attrs["error"] = data["error"]
            
        return attrs
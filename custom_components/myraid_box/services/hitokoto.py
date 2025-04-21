from typing import Dict, Any, List
from datetime import datetime, timedelta
import aiohttp
import logging
from ..service_base import BaseService, AttributeConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_HITOKOTO_API = "https://v1.hitokoto.cn"

class HitokotoService(BaseService):
    """完整修复版每日一言服务"""

    CATEGORY_MAP = {
        "动画": "a", "漫画": "b", "游戏": "c", "文学": "d",
        "原创": "e", "网络": "f", "其他": "g", "影视": "h",
        "诗词": "i", "网易云": "j", "哲学": "k", "抖机灵": "l", "随机": "z"
    }
    REVERSE_CATEGORY_MAP = {v: k for k, v in CATEGORY_MAP.items()}
    
    @property
    def service_id(self) -> str:
        return "hitokoto"

    @property
    def name(self) -> str:
        return "每日一言"

    @property
    def description(self) -> str:
        return "从一言官网获取有趣的话"

    @property
    def icon(self) -> str:
        return "mdi:format-quote-close"

    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "url": {
                "name": "API地址",
                "type": "str",
                "default": DEFAULT_HITOKOTO_API,
                "description": "官方API地址"
            },
            "interval": {
                "name": "更新间隔（分钟）",
                "type": "int",
                "default": 10,
                "description": "更新间隔时间"
            },
            "category": {
                "name": "分类",
                "type": "select",
                "default": "随机",
                "description": "一言分类",
                "options": sorted(self.CATEGORY_MAP.keys(), key=lambda x: self.CATEGORY_MAP[x])
            }
        }

    @property
    def attributes(self) -> Dict[str, AttributeConfig]:
        return {
            "category": {
                "name": "分类",
                "icon": "mdi:tag",
                "value_map": {v: k for k, v in self.CATEGORY_MAP.items()}
            },
            "source": {
                "name": "来源",
                "icon": "mdi:book"
            },
            "author": {
                "name": "作者",
                "icon": "mdi:account"
            },
            "update_time": {
                "name": "更新时间",
                "icon": "mdi:clock"
            }
        }

    def build_request(self, params: Dict[str, Any]) -> tuple[str, Dict[str, Any], Dict[str, str]]:
        base_url = params["url"].strip('/')
        category = params.get("category", "随机")
        
        if category == "随机":
            url = base_url
        else:
            category_code = self.CATEGORY_MAP.get(category, "z")
            url = f"{base_url}/?c={category_code}&encode=json"
        
        headers = {
            "Accept": "application/json",
            "User-Agent": f"HomeAssistant/{self.service_id}"
        }
        return url, {}, headers

    def parse_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """增强版响应解析"""
        data = response_data.get("data", response_data)
        update_time = response_data.get("update_time", datetime.now().isoformat()) 
        
        if not isinstance(data, dict):
            _LOGGER.error(f"无效的API响应格式: {type(data)}")
            return {
                "hitokoto": "数据解析错误",
                "category": "错误",
                "source": "",
                "author": "佚名",
                "update_time": update_time
            }
        
        # 转换分类代码为可读名称
        category_code = data.get("type", "")
        category_name = self.REVERSE_CATEGORY_MAP.get(category_code, f"({category_code})")
        
        return {
            "hitokoto": data.get("hitokoto", "无有效内容"),  # 确保有默认值
            "category": category_name,
            "source": data.get("from", ""),  # 确保有默认值
            "author": data.get("from_who", "佚名"),  # 确保有默认值
            "update_time": update_time
        }
        
    def format_sensor_value(self, data: Any, sensor_config: Dict[str, Any]) -> str:
        """带错误处理的显示格式化"""
        if not data or data.get("status") != "success":
            return "⏳ 加载中..." if data is None else f"⚠️ {data.get('error', '获取失败')}"
        
        try:
            parsed = self.parse_response(data)
            
            # 确保 hitokoto 不为 None
            hitokoto = parsed.get("hitokoto", "无有效内容")
            if hitokoto is None:
                hitokoto = "无有效内容"
            
            lines = [f"「{hitokoto}」"]
            
            attribution = []
            # 确保 author 和 source 不为 None
            author = parsed.get("author", "佚名")
            source = parsed.get("source", "未知")
            
            if author != "佚名":
                attribution.append(str(author))  # 确保转换为字符串
            if source:
                attribution.append(str(source))  # 确保转换为字符串
            
            if attribution:
                lines.append(f"—— {' '.join(attribution)}")
            
            return "\n".join(lines)
        except Exception as e:
            _LOGGER.error(f"格式化显示值时出错: {str(e)}")
            return "⚠️ 显示错误"

    def get_sensor_attributes(self, data: Any, sensor_config: Dict[str, Any]) -> Dict[str, Any]:
        """完整的属性获取方法"""
        if not data or data.get("status") != "success":
            return {}
        
        try:
            parsed = self.parse_response(data)
            return super().get_sensor_attributes({
                "category": parsed["category"],
                "source": parsed["source"],
                "author": parsed["author"],
                "update_time": parsed["update_time"] 
            }, sensor_config)
        except Exception as e:
            _LOGGER.error(f"获取属性时出错: {str(e)}")
            return {}

    def get_sensor_configs(self, service_data: Any) -> List[Dict[str, Any]]:
        return [{
            "key": "main",
            "name": self.name,
            "icon": self.icon,
            "unit": None,
            "device_class": "enum"
        }]
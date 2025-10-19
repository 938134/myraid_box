from typing import Dict, Any, List
from datetime import datetime
import aiohttp
import logging
from ..service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_HITOKOTO_API = "https://v1.hitokoto.cn"

class HitokotoService(BaseService):
    """多传感器版每日一言服务"""

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
    def sensor_configs(self) -> List[SensorConfig]:
        """返回每日一言的所有传感器配置"""
        return [
            {
                "key": "content",
                "name": "内容",
                "icon": "mdi:format-quote-close",
                "device_class": None
            },
            {
                "key": "category",
                "name": "分类", 
                "icon": "mdi:tag",
                "device_class": None,
                "entity_category": "diagnostic"
            },
            {
                "key": "author",
                "name": "作者",
                "icon": "mdi:account",
                "device_class": None,
                "entity_category": "diagnostic"
            },
            {
                "key": "source",
                "name": "来源",
                "icon": "mdi:book",
                "device_class": None,
                "entity_category": "diagnostic"
            }
        ]

    def build_request(self, params: Dict[str, Any]) -> tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建请求参数"""
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

    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """解析响应数据为标准化字典"""
        # 提取原始数据
        if isinstance(response_data, dict) and "data" in response_data:
            data = response_data["data"]
        else:
            data = response_data
            
        update_time = response_data.get("update_time", datetime.now().isoformat())
        
        if not isinstance(data, dict):
            _LOGGER.error(f"无效的API响应格式: {type(data)}")
            return {
                "content": "数据解析错误",
                "category": "错误",
                "author": "未知",
                "source": "未知",
                "update_time": update_time
            }
        
        # 转换分类代码为可读名称
        category_code = data.get("type", "")
        category_name = self.REVERSE_CATEGORY_MAP.get(category_code, f"未知({category_code})")
        
        # 返回标准化数据字典
        return {
            "content": data.get("hitokoto", "无有效内容"),
            "category": category_name,
            "author": data.get("from_who", "佚名"),
            "source": data.get("from", ""),
            "update_time": update_time
        }

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化特定传感器的显示值"""
        value = self.get_sensor_value(sensor_key, data)
        
        if value is None:
            return "暂无数据"
            
        # 为不同传感器提供特定的格式化
        if sensor_key == "content":
            return f"「{value}」" if value and value != "无有效内容" else value
        elif sensor_key == "category":
            return value if value else "未知分类"
        elif sensor_key == "author":
            return value if value and value != "佚名" else "未知作者"
        elif sensor_key == "source":
            return value if value else "未知来源"
        else:
            return str(value)
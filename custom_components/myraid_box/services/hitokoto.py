from typing import Dict, Any, List
from datetime import datetime
import logging
import re
from ..service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)

class HitokotoService(BaseService):
    """多传感器版每日一言服务"""

    DEFAULT_API_URL = "https://v1.hitokoto.cn"
    DEFAULT_UPDATE_INTERVAL = 10

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
        return "从一言官网获取励志名言"

    @property
    def icon(self) -> str:
        return "mdi:format-quote-close"

    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "interval": {
                "name": "更新间隔",
                "type": "int", 
                "default": self.DEFAULT_UPDATE_INTERVAL,
                "description": "更新间隔时间（分钟）"
            },
            "category": {
                "name": "分类",
                "type": "select",
                "default": "随机", 
                "description": "一言分类",
                "options": sorted(self.CATEGORY_MAP.keys(), key=lambda x: self.CATEGORY_MAP[x])
            }
        }

    def _get_sensor_configs(self) -> List[SensorConfig]:
        """返回每日一言的所有传感器配置（按显示顺序）"""
        return [
            self._create_sensor_config("content", "内容", "mdi:format-quote-close"),
            self._create_sensor_config("category", "分类", "mdi:tag"),
            self._create_sensor_config("author", "作者", "mdi:account"),
            self._create_sensor_config("source", "来源", "mdi:book")
        ]

    def _build_request_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """构建请求参数"""
        category = params.get("category", "随机")
        if category != "随机":
            category_code = self.CATEGORY_MAP.get(category, "z")
            return {"c": category_code, "encode": "json"}
        return {}

    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """解析响应数据为标准化字典"""
        # 处理基类返回的数据结构
        if isinstance(response_data, dict) and "data" in response_data:
            # 基类返回的结构：包含data、status、update_time等
            api_data = response_data["data"]
            update_time = response_data.get("update_time", datetime.now().isoformat())
        else:
            # 直接使用响应数据
            api_data = response_data
            update_time = datetime.now().isoformat()
        
        # 检查API响应状态
        if isinstance(api_data, dict) and api_data.get("status") == "error":
            _LOGGER.error(f"API返回错误: {api_data.get('error')}")
            return self._create_error_response(update_time)
        
        if not isinstance(api_data, dict):
            _LOGGER.error(f"无效的API响应格式: {type(api_data)}")
            return self._create_error_response(update_time)
    
        # 转换分类代码为可读名称
        category_code = api_data.get("type", "")
        category_name = self.REVERSE_CATEGORY_MAP.get(category_code, f"未知({category_code})")
        
        # 返回标准化数据字典
        return {
            "content": api_data.get("hitokoto", "无有效内容"),
            "category": category_name,
            "author": api_data.get("from_who", "佚名"),
            "source": api_data.get("from", ""),
            "update_time": update_time
        }

    def _create_error_response(self, update_time: str) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            "content": "数据解析错误",
            "category": "错误",
            "author": "未知",
            "source": "未知",
            "update_time": update_time
        }

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化特定传感器的显示值"""
        value = self.get_sensor_value(sensor_key, data)
        
        if value is None:
            return "暂无数据"
            
        # 为不同传感器提供特定的格式化
        formatters = {
            "content": self._format_content,
            "category": self._format_category,
            "author": self._format_author,
            "source": self._format_source
        }
        
        formatter = formatters.get(sensor_key, str)
        return formatter(value)

    def _format_content(self, value: str) -> str:
        """格式化内容"""
        if value and value != "无有效内容":
            cleaned_value = re.sub(r'^[「」『』"\'""《》【】（）、，。！？]', '', value)
            cleaned_value = re.sub(r'[「」『』"\'""《》【】（）、，。！？]$', '', cleaned_value)
            return cleaned_value.strip()
        return value

    def _format_category(self, value: str) -> str:
        return value if value else "未知"

    def _format_author(self, value: str) -> str:
        return value if value and value != "佚名" else "佚名"

    def _format_source(self, value: str) -> str:
        return value if value else "未知"

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """验证服务配置"""
        # 一言服务没有特殊验证要求
        pass
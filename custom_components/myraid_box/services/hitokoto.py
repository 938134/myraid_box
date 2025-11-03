from typing import Dict, Any, List
from datetime import datetime
import logging
import re
from ..service_base import BaseService, SensorConfig, RequestConfig

_LOGGER = logging.getLogger(__name__)


class HitokotoService(BaseService):
    """每日一言服务 - 使用新版基类"""

    # 服务常量
    DEFAULT_API_URL = "https://v1.hitokoto.cn"
    DEFAULT_UPDATE_INTERVAL = 10
    DEFAULT_TIMEOUT = 15  # 一言API响应很快，设置较短超时

    # 分类映射
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
    def config_help(self) -> str:
        return "📝 一言服务配置说明：\n1. 选择喜欢的句子分类\n2. 设置合适的更新间隔"

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
        """返回每日一言的所有传感器配置"""
        return [
            self._create_sensor_config("content", "内容", "mdi:format-quote-close"),
            self._create_sensor_config("category", "分类", "mdi:tag"),
            self._create_sensor_config("author", "作者", "mdi:account"),
            self._create_sensor_config("source", "来源", "mdi:book")
        ]

    def _build_base_request(self, params: Dict[str, Any]) -> RequestConfig:
        """构建一言API请求"""
        category = params.get("category", "随机")
        
        # 构建请求参数
        request_params = {"encode": "json"}
        if category != "随机":
            category_code = self.CATEGORY_MAP.get(category, "z")
            request_params["c"] = category_code

        return RequestConfig(
            url=self.default_api_url,
            method="GET",
            params=request_params
        )

    def _parse_raw_response(self, response_data: Any) -> Dict[str, Any]:
        """解析一言API响应数据"""
        # 检查响应格式
        if not isinstance(response_data, dict):
            return {
                "status": "error",
                "error": "无效的响应格式"
            }

        # 提取数据字段
        content = response_data.get("hitokoto", "").strip()
        category_code = response_data.get("type", "")
        author = response_data.get("from_who")
        source = response_data.get("from")
        
        # 转换分类代码为可读名称
        category_name = self.REVERSE_CATEGORY_MAP.get(category_code, f"未知({category_code})")

        # 清理内容中的引号符号
        if content:
            content = re.sub(r'^[「」『』"\'""《》【】]', '', content)
            content = re.sub(r'[「」『』"\'""《》【】]$', '', content)

        return {
            "content": content or "暂无内容",
            "category": category_name,
            "author": author or "佚名",
            "source": source or "未知来源"
        }

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化传感器显示值"""
        value = self.get_sensor_value(sensor_key, data)
        
        # 对于内容传感器，确保长度合适
        if sensor_key == "content" and value and len(value) > 100:
            value = value[:97] + "..."
            
        return super().format_sensor_value(sensor_key, data)

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        """获取传感器的额外属性"""
        attributes = super().get_sensor_attributes(sensor_key, data)
        
        if not data or data.get("status") != "success":
            return attributes
            
        # 为内容传感器添加完整信息
        if sensor_key == "content":
            parsed_data = data.get("data", {})
            attributes.update({
                "完整内容": parsed_data.get("content"),
                "句子ID": data.get("id"),
                "分类代码": parsed_data.get("category_code"),
                "数据来源": "hitokoto.cn"
            })
            
        return attributes

    def _get_default_value(self, key: str) -> Any:
        """根据字段名返回默认值"""
        defaults = {
            "content": "暂无内容",
            "category": "未知分类", 
            "author": "佚名",
            "source": "未知来源"
        }
        return defaults.get(key, super()._get_default_value(key))

    def _get_sensor_default(self, sensor_key: str) -> Any:
        """获取传感器默认值"""
        defaults = {
            "content": "加载中...",
            "category": "未知",
            "author": "佚名",
            "source": "未知"
        }
        return defaults.get(sensor_key, super()._get_sensor_default(sensor_key))

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """验证服务配置"""
        # 检查分类是否有效
        category = config.get("category")
        if category and category not in cls.CATEGORY_MAP:
            raise ValueError(f"无效的分类: {category}")
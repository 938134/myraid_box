from typing import Dict, Any, List
from datetime import datetime
import logging
import re
import asyncio
import time
from ..service_base import BaseService, SensorConfig, RequestConfig

_LOGGER = logging.getLogger(__name__)


class PoetryService(BaseService):
    """每日诗词服务 - 使用新版基类"""

    DEFAULT_API_URL = "https://v2.jinrishici.com/one.json"
    DEFAULT_UPDATE_INTERVAL = 10
    DEFAULT_TIMEOUT = 20  # 诗词API可能较慢

    def __init__(self):
        super().__init__()
        self._token_initialized = False
        self._token_lock = asyncio.Lock()

    @property
    def service_id(self) -> str:
        return "poetry"

    @property
    def name(self) -> str:
        return "每日诗词"

    @property
    def description(self) -> str:
        return "从古诗词API获取经典诗词"

    @property
    def config_help(self) -> str:
        return "📚 诗词服务配置说明：\n1. 自动获取随机经典诗词\n2. 包含原文、译文和赏析"

    @property
    def icon(self) -> str:
        return "mdi:book-open-variant"

    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "interval": {
                "name": "更新间隔",
                "type": "int",
                "default": self.DEFAULT_UPDATE_INTERVAL,
                "description": "更新间隔时间（分钟）"
            }
        }

    def _get_sensor_configs(self) -> List[SensorConfig]:
        """返回每日诗词的所有传感器配置"""
        return [
            self._create_sensor_config("content", "名句", "mdi:format-quote-open"),
            self._create_sensor_config("title", "标题", "mdi:book"),
            self._create_sensor_config("author", "诗人", "mdi:account"),
            self._create_sensor_config("dynasty", "朝代", "mdi:castle"),
        ]

    async def _ensure_token(self, params: Dict[str, Any]) -> str:
        """确保有有效的诗词API token"""
        async with self._token_lock:
            if self._token and self._token_expiry and time.time() < self._token_expiry:
                return self._token

            try:
                await self._ensure_session()
                token_url = "https://v2.jinrishici.com/token"
                
                async with self._session.get(token_url, timeout=10) as response:
                    token_data = await response.json()
                    if token_data.get("status") == "success":
                        self._token = token_data.get("data")
                        # 设置token有效期为23小时
                        self._token_expiry = time.time() + 82800
                        self._token_initialized = True
                        _LOGGER.info("成功获取诗词API Token")
                        return self._token
            except Exception as e:
                _LOGGER.warning("获取诗词API Token异常: %s，使用默认token", e)

            # 如果获取token失败，使用默认token
            self._token = "homeassistant-poetry-service"
            self._token_expiry = time.time() + 3600
            self._token_initialized = True
            return self._token

    def _build_auth_headers(self, token: str) -> Dict[str, str]:
        """构建诗词API认证头"""
        headers = {
            "Accept": "application/json",
            "User-Agent": f"HomeAssistant/{self.service_id}"
        }
        if token:
            headers["X-User-Token"] = token
        return headers

    def _parse_raw_response(self, response_data: Any) -> Dict[str, Any]:
        """解析诗词API响应数据"""
        # 检查API响应状态
        if isinstance(response_data, dict) and response_data.get("status") == "error":
            error_msg = response_data.get("errMessage", "API返回错误")
            _LOGGER.warning("诗词API返回错误: %s", error_msg)
            return self._create_error_data("API返回错误")

        # 解析数据结构
        data = response_data.get('data', response_data)
        origin_data = data.get('origin', {})
        
        # 提取字段
        content = data.get('content', '').strip()
        title = origin_data.get('title', '未知').strip()
        author = origin_data.get('author', '佚名').strip()
        dynasty = origin_data.get('dynasty', '未知').strip()
        full_content_list = origin_data.get('content', [])
        translate = origin_data.get('translate')
        
        # 格式化完整诗词内容
        full_content = self._format_poetry_content(full_content_list)
        
        # 格式化译文
        formatted_translate = self._format_translate(translate)

        return {
            "content": content or "暂无名句",
            "title": title or "未知标题",
            "author": author or "佚名",
            "dynasty": dynasty or "未知",
            "full_content": full_content,
            "translate": formatted_translate
        }

    def _format_poetry_content(self, content_list: List[str]) -> str:
        """格式化完整诗词内容"""
        if not content_list:
            return "无完整内容"
            
        # 将诗句列表连接成一个字符串
        combined_content = "".join(content_list)
        
        # 在标点符号后添加换行，使诗句更易读
        formatted_content = re.sub(r'([。！？])', r'\1\n', combined_content)
        formatted_content = re.sub(r'([，])', r'\1 ', formatted_content)
        
        # 清理多余的换行符和空格
        formatted_content = re.sub(r'\n+', '\n', formatted_content).strip()
        formatted_content = re.sub(r' +', ' ', formatted_content)
        
        return formatted_content

    def _format_translate(self, translate: Any) -> str:
        """格式化译文内容"""
        if not translate:
            return "无译文"
            
        if isinstance(translate, list):
            # 如果是列表，合并所有译文
            translated_text = " ".join([str(t).strip() for t in translate if t])
        else:
            # 如果是字符串，直接使用
            translated_text = str(translate).strip()
            
        return translated_text

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化传感器显示值"""
        value = self.get_sensor_value(sensor_key, data)
        
        if value is None:
            return self._get_sensor_default(sensor_key)
        
        # 对名句内容进行清理
        if sensor_key == "content":
            # 移除可能存在的引号等符号
            value = re.sub(r'[「」『』"\'""]', '', value).strip()
            # 限制名句长度
            if len(value) > 100:
                value = value[:97] + "..."
        
        return value

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        """获取传感器的额外属性"""
        attributes = super().get_sensor_attributes(sensor_key, data)
        
        if not data or data.get("status") != "success":
            return attributes
            
        parsed_data = data.get("data", {})
        
        # 在标题传感器中显示完整信息
        if sensor_key == "title":
            attributes.update({
                "诗人": parsed_data.get("author", "未知"),
                "朝代": parsed_data.get("dynasty", "未知"),
                "完整诗词": parsed_data.get("full_content", "无完整内容"),
                "诗词译文": parsed_data.get("translate", "无译文"),
                "精选名句": parsed_data.get("content", "暂无名句"),
                "数据来源": "jinrishici.com"
            })
        
        return attributes

    def _get_default_value(self, key: str) -> Any:
        """根据字段名返回默认值"""
        defaults = {
            "content": "暂无名句",
            "title": "未知标题",
            "author": "佚名",
            "dynasty": "未知",
            "full_content": "无完整内容",
            "translate": "无译文"
        }
        return defaults.get(key, super()._get_default_value(key))

    def _get_sensor_default(self, sensor_key: str) -> Any:
        """获取传感器默认值"""
        defaults = {
            "content": "加载中...",
            "title": "加载中...",
            "author": "加载中...",
            "dynasty": "加载中..."
        }
        return defaults.get(sensor_key, super()._get_sensor_default(sensor_key))

    def _create_error_data(self, error_msg: str) -> Dict[str, Any]:
        """创建错误数据"""
        return {
            "status": "error",
            "error": error_msg
        }

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """验证服务配置"""
        # 诗词服务没有特殊验证要求
        pass
from typing import Dict, Any, List
from datetime import datetime
import logging
import re
import random
from bs4 import BeautifulSoup
from ..service_base import BaseService, SensorConfig, RequestConfig

_LOGGER = logging.getLogger(__name__)


class HistoryService(BaseService):
    """每日历史服务 - 使用 abtool.cn 数据源"""

    DEFAULT_API_URL = "https://www.abtool.cn/historytoday"
    DEFAULT_UPDATE_INTERVAL = 1440
    DEFAULT_TIMEOUT = 30

    def __init__(self):
        super().__init__()

    @property
    def service_id(self) -> str:
        return "history"

    @property
    def name(self) -> str:
        return "每日历史"

    @property
    def description(self) -> str:
        return "从 abtool.cn 获取当天历史事件列表"

    @property
    def config_help(self) -> str:
        return "📜 历史服务配置说明：\n1. 自动获取当天历史事件"

    @property
    def icon(self) -> str:
        return "mdi:calendar-clock"

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
        """返回每日历史的所有传感器配置"""
        return [
            self._create_sensor_config("today", "今日", "mdi:calendar-today"),
            self._create_sensor_config("count", "数量", "mdi:counter", "个"),
            self._create_sensor_config("event", "事件", "mdi:book-open-page-variant"),
        ]

    def _build_base_request(self, params: Dict[str, Any]) -> RequestConfig:
        """构建请求配置"""
        return RequestConfig(
            url=self.default_api_url,
            method="GET",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            },
            timeout=self.DEFAULT_TIMEOUT
        )

    def _parse_raw_response(self, response_data: Any) -> Dict[str, Any]:
        """解析响应数据 - 返回包含 events 列表的数据"""
        if not isinstance(response_data, str):
            return {
                "today": self._get_today_date(),
                "count": 0,
                "event": "数据获取失败",
                "events": []
            }

        try:
            soup = BeautifulSoup(response_data, "html.parser")
            
            # 移除script和style标签
            for script in soup(["script", "style"]):
                script.decompose()
            
            # 获取纯文本
            text = soup.get_text()
            
            # 提取所有事件
            events = []
            events_list = []
            seen = set()
            
            # 匹配 [1865年]4月9日美国南北战争结束
            for match in re.finditer(r'\[(\d{4})年\]\d+月\d+日\s*(.+?)(?=\n\n|\[|\n\d+\.)', text):
                year = match.group(1)
                desc = match.group(2).strip()
                desc = re.sub(r'^\d+\.', '', desc)
                desc = desc.strip()
                
                if desc and len(desc) > 2 and desc not in seen:
                    seen.add(desc)
                    events.append(desc)
                    events_list.append({"year": year, "event": desc})
            
            # 备用模式
            if not events:
                for match in re.finditer(r'\[(\d{4})年\]([^\[\n]+)', text):
                    year = match.group(1)
                    desc = match.group(2).strip()
                    desc = re.sub(r'^\d+\.', '', desc)
                    desc = desc.strip()
                    
                    if desc and len(desc) > 2 and desc not in seen:
                        seen.add(desc)
                        events.append(desc)
                        events_list.append({"year": year, "event": desc})
            
            if not events:
                _LOGGER.warning("未解析到任何历史事件")
                return {
                    "today": self._get_today_date(),
                    "count": 0,
                    "event": "暂无事件",
                    "events": []
                }
            
            # 随机选择一个事件
            random_event = random.choice(events)
            
            # 返回格式，包含 events 列表供卡片使用
            return {
                "today": self._get_today_date(),
                "count": len(events),
                "event": random_event,
                "events": events_list
            }
            
        except Exception as e:
            _LOGGER.error("解析历史数据失败: %s", str(e), exc_info=True)
            return {
                "today": self._get_today_date(),
                "count": 0,
                "event": "解析失败",
                "events": []
            }

    def _get_today_date(self) -> str:
        """获取今日日期字符串"""
        today = datetime.now()
        return today.strftime("%Y年%m月%d日")

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化传感器显示值"""
        value = self.get_sensor_value(sensor_key, data)
        
        if value is None:
            return self._get_sensor_default(sensor_key)
        
        # 对事件内容进行长度限制
        if sensor_key == "event" and value and len(value) > 80:
            value = value[:77] + "..."
        
        return value

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        """获取传感器的额外属性"""
        attributes = super().get_sensor_attributes(sensor_key, data)
        
        if not data or data.get("status") != "success":
            return attributes
        
        # 为今日传感器添加更多属性
        if sensor_key == "today":
            attributes.update({
                "数据来源": "abtool.cn",
                "更新说明": "每日历史事件"
            })
        
        return attributes

    def get_sensor_icon(self, sensor_key: str, data: Any) -> str:
        """获取传感器图标"""
        icons = {
            "today": "mdi:calendar-today",
            "count": "mdi:counter",
            "event": "mdi:book-open-page-variant"
        }
        return icons.get(sensor_key, "mdi:information")

    def _get_sensor_default(self, sensor_key: str) -> Any:
        """获取传感器默认值"""
        defaults = {
            "today": self._get_today_date(),
            "count": 0,
            "event": "加载中..."
        }
        return defaults.get(sensor_key, super()._get_sensor_default(sensor_key))

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """验证服务配置"""
        pass
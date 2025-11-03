from typing import Dict, Any, List
from datetime import datetime
import logging
import re
from bs4 import BeautifulSoup
from ..service_base import BaseService, SensorConfig, RequestConfig

_LOGGER = logging.getLogger(__name__)


class HistoryService(BaseService):
    """每日历史服务 - 使用新版基类"""

    DEFAULT_API_URL = "http://www.todayonhistory.com"
    DEFAULT_UPDATE_INTERVAL = 10
    DEFAULT_TIMEOUT = 30  # 历史网站可能较慢

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
        return "从历史网站获取当天历史事件列表"

    @property
    def config_help(self) -> str:
        return "📜 历史服务配置说明：\n1. 自动获取当天历史事件\n2. 支持最多10个历史事件"

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
            self._create_sensor_config("count", "数量", "mdi:counter", "个"),
            self._create_sensor_config("era", "时期", "mdi:clock-outline"),
            self._create_sensor_config("event", "事件", "mdi:book"),
            self._create_sensor_config("details", "详情", "mdi:format-list-bulleted"),
        ]

    def _build_base_request(self, params: Dict[str, Any]) -> RequestConfig:
        """构建历史网站请求"""
        today = datetime.now()
        today_path = f"today-{today.month}-{today.day}.html"
        url = f"{self.default_api_url}/{today_path}"
        
        return RequestConfig(
            url=url,
            method="GET",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            }
        )

    def _parse_raw_response(self, response_data: Any) -> Dict[str, Any]:
        """解析历史网站响应数据"""
        if not isinstance(response_data, str):
            return {
                "status": "error",
                "error": "无效的响应格式"
            }

        try:
            soup = BeautifulSoup(response_data, "html.parser")
            events = self._parse_all_events(soup)
            
            if not events:
                return {
                    "count": 0,
                    "era": "未知",
                    "event": "未找到历史事件",
                    "details": "暂无历史事件"
                }

            # 选择第一个事件作为主要显示
            main_event = events[0]
            return {
                "count": len(events),
                "era": main_event.get("era", "未知"),
                "event": main_event.get("event", "未知"),
                "details": self._format_events_details(events),
                "events": events  # 保存完整事件列表供属性使用
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"解析历史数据失败: {str(e)}"
            }

    def _parse_all_events(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """解析所有历史事件"""
        events = []
        items = soup.select("p")
        
        for item in items:
            if item.find("span") and item.find("a"):
                event_data = self._parse_history_item(item)
                if event_data:
                    events.append(event_data)
                    # 限制最大事件数量
                    if len(events) >= 10:
                        break
        
        return events

    def _parse_history_item(self, item: Any) -> Dict[str, Any]:
        """解析单个历史事件项"""
        try:
            # 提取年份（方括号[]中的内容）
            year_text = item.find("span").get_text().strip()
            year_match = re.search(r'\[(.*?)\]', year_text)
            
            if year_match:
                year = year_match.group(1)
                era = self._infer_era(year)
            else:
                year = "未知年份"
                era = "未知时期"

            event = item.find("a").get_text().strip()
            url = item.find("a").get("href", "")
            
            return {
                "year": year,
                "event": event,
                "url": url,
                "era": era
            }
        except Exception:
            return None

    def _format_events_details(self, events: List[Dict[str, Any]]) -> str:
        """格式化事件详情为字符串"""
        if not events:
            return "暂无历史事件"
        
        formatted_details = []
        for event in events:
            year = event.get("year", "未知")
            event_text = event.get("event", "")
            formatted_details.append(f"{year} {event_text}")
        
        return "\n".join(formatted_details)

    def _infer_era(self, year_str: str) -> str:
        """根据年份推断历史时期"""
        try:
            clean_year = re.sub(r'[^\d]', '', year_str)
            if not clean_year:
                return "未知时期"
                
            year = int(clean_year)
            
            era_periods = [
                (221, "远古时期"),
                (581, "秦汉魏晋南北朝"),
                (907, "隋唐时期"),
                (1279, "宋辽金时期"),
                (1368, "元朝"),
                (1644, "明朝"),
                (1912, "清朝"),
                (1949, "民国时期"),
                (float('inf'), "现代")
            ]
            
            for threshold, era_name in era_periods:
                if year < threshold:
                    return era_name
                    
        except (ValueError, TypeError):
            return "未知时期"
        
        return "未知时期"

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        """获取传感器的额外属性"""
        attributes = super().get_sensor_attributes(sensor_key, data)
        
        if not data or data.get("status") != "success":
            return attributes
            
        parsed_data = data.get("data", {})
        
        # 为事件传感器添加完整事件列表
        if sensor_key == "event":
            events = parsed_data.get("events", [])
            if events:
                attributes["事件总数"] = len(events)
                for i, event in enumerate(events[:5]):  # 只显示前5个事件
                    attributes[f"事件{i+1}"] = f"{event.get('year')} {event.get('event')}"
        
        return attributes

    def _get_default_value(self, key: str) -> Any:
        """根据字段名返回默认值"""
        defaults = {
            "count": 0,
            "era": "未知时期",
            "event": "暂无历史事件",
            "details": "暂无事件详情"
        }
        return defaults.get(key, super()._get_default_value(key))

    def _get_sensor_default(self, sensor_key: str) -> Any:
        """获取传感器默认值"""
        defaults = {
            "count": 0,
            "era": "未知",
            "event": "加载中...",
            "details": "加载中..."
        }
        return defaults.get(sensor_key, super()._get_sensor_default(sensor_key))

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """验证服务配置"""
        # 历史服务没有特殊验证要求
        pass
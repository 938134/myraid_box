from __future__ import annotations
from datetime import datetime
from typing import Dict, Any, List
import logging
import re
from bs4 import BeautifulSoup
from ..service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)

class HistoryService(BaseService):
    """多传感器版历史上的今天数据服务 - 四传感器版"""

    DEFAULT_API_URL = "http://www.todayonhistory.com/"
    DEFAULT_UPDATE_INTERVAL = 10
    MAX_EVENTS = 10  # 最大事件数量

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
            self._create_sensor_config("count", "数量", "mdi:counter", "个", None, 1),
            self._create_sensor_config("era", "时期", "mdi:clock-outline", None, None, 2),
            self._create_sensor_config("event", "事件", "mdi:book", None, None, 3),
            self._create_sensor_config("details", "详情", "mdi:format-list-bulleted", None, None, 4),
        ]

    def build_request(self, params: Dict[str, Any], token: str = "") -> tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建请求参数"""
        base_url = self.default_api_url
        today = datetime.now()
        today_path = f"today-{today.month}-{today.day}.html"
        url = f"{base_url}/{today_path}"
        headers = self._build_request_headers(token)
        return url, {}, headers

    def _build_request_headers(self, token: str = "") -> Dict[str, str]:
        """构建请求头 - 历史服务需要HTML内容"""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }

    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """解析响应数据为标准化字典 - 返回事件列表"""
        if isinstance(response_data, dict) and "data" in response_data:
            # 处理基类返回的数据结构
            html_data = response_data["data"]
            update_time = response_data.get("update_time", datetime.now().isoformat())
        else:
            # 直接处理HTML字符串
            html_data = response_data
            update_time = datetime.now().isoformat()

        if isinstance(html_data, str):
            soup = BeautifulSoup(html_data, "html.parser")
            
            # 获取所有历史事件
            events = self._parse_all_events(soup, update_time)
            
            if events:
                # 选择第一个事件作为主要显示
                main_event = events[0]
                return {
                    "status": "success",
                    "count": len(events),
                    "era": main_event.get("era", "未知"),
                    "event": main_event.get("event", "未知"),
                    "details": self._format_events_details(events),
                    "update_time": update_time
                }
            else:
                return self._create_error_response("未找到历史事件", update_time)
        else:
            return self._create_error_response("无效响应数据", update_time)

    def _parse_all_events(self, soup: BeautifulSoup, update_time: str) -> List[Dict[str, Any]]:
        """解析所有历史事件"""
        events = []
        items = soup.select("p")
        
        for item in items:
            if item.find("span") and item.find("a"):
                event_data = self._parse_history_item(item, update_time)
                if event_data.get("status") == "success":
                    events.append(event_data)
                    # 限制最大事件数量
                    if len(events) >= self.MAX_EVENTS:
                        break
        
        return events

    def _parse_history_item(self, item: Any, update_time: str) -> Dict[str, Any]:
        """解析单个历史事件项"""
        try:
            # 提取年份（方括号[]中的内容）
            year_text = item.find("span").get_text().strip()
            year_match = re.search(r'\[(.*?)\]', year_text)
            
            if year_match:
                year = year_match.group(1)  # 获取方括号中的内容
                era = self._infer_era(year)
            else:
                year = "未知年份"
                era = "未知时期"

            event = item.find("a").get_text().strip()
            url = item.find("a")["href"]
            
            return {
                "status": "success",
                "year": year,
                "event": event,
                "url": url,
                "era": era
            }
        except Exception as e:
            _LOGGER.error("解析历史事件失败: %s", str(e))
            return {
                "status": "error",
                "year": "未知",
                "event": "解析失败",
                "url": "",
                "era": "未知"
            }

    def _format_events_details(self, events: List[Dict[str, Any]]) -> str:
        """格式化事件详情为字符串 - 每行时间+事件"""
        if not events:
            return "暂无历史事件"
        
        formatted_details = []
        for event in events:
            year = event.get("year", "未知")
            event_text = event.get("event", "")
            formatted_details.append(f"{year} {event_text}")
        
        return "\n".join(formatted_details)

    def _create_error_response(self, error_msg: str, update_time: str) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            "status": "error",
            "count": 0,
            "era": "未知",
            "event": error_msg,
            "details": error_msg,
            "update_time": update_time
        }
    
    def _infer_era(self, year_str: str) -> str:
        """根据年份推断历史时期"""
        try:
            # 清理年份字符串
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

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化特定传感器的显示值"""
        value = self.get_sensor_value(sensor_key, data)
        
        if value is None:
            return "暂无数据"
            
        formatters = {
            "count": self._format_count,
            "era": self._format_era,
            "event": self._format_event,
            "details": self._format_details,
        }
        
        formatter = formatters.get(sensor_key, str)
        return formatter(value)

    def _format_count(self, value: int) -> str:
        return f"{value}" if value > 0 else "0"

    def _format_era(self, value: str) -> str:
        return value if value and value != "未知" else "未知时期"

    def _format_event(self, value: str) -> str:
        return value if value and value != "未找到历史事件" else "暂无历史事件"

    def _format_details(self, value: str) -> str:
        return value if value else "暂无事件详情"

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        """获取传感器的额外属性"""
        if not data or data.get("status") != "success":
            return {}
            
        return {
            "更新时间": data.get("update_time", "未知"),
            "数据状态": "成功"
        }

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """验证服务配置"""
        # 历史服务没有特殊验证要求
        pass
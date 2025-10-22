from __future__ import annotations
from datetime import datetime
from typing import Dict, Any, List
import logging
import random
import re
from bs4 import BeautifulSoup
from ..service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)

class HistoryService(BaseService):
    """多传感器版历史上的今天数据服务"""

    DEFAULT_API_URL = "http://www.todayonhistory.com/"
    DEFAULT_UPDATE_INTERVAL = 10

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
        return "从历史网站获取当天历史事件"

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
        """返回每日历史的所有传感器配置（按显示顺序）"""
        return [
            self._create_sensor_config("event", "历史事件", "mdi:book", sort_order=1),
            self._create_sensor_config("year", "历史年份", "mdi:calendar", sort_order=2),
            self._create_sensor_config("url", "详情链接", "mdi:link", sort_order=3),
            self._create_sensor_config("era", "历史时期", "mdi:clock-outline", sort_order=4)
        ]

    def build_request(self, params: Dict[str, Any]) -> tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建请求参数"""
        base_url = self.default_api_url
        today = datetime.now()
        today_path = f"today-{today.month}-{today.day}.html"
        url = f"{base_url}/{today_path}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
            "Accept": "text/html"
        }
        return url, {}, headers

    def _build_request_headers(self) -> Dict[str, str]:
        """构建请求头"""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
            "Accept": "text/html"
        }

    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """解析响应数据为标准化字典"""
        if isinstance(response_data.get("data"), str):
            soup = BeautifulSoup(response_data["data"], "html.parser")
    
            # 随机选择一个符合条件的<p>标签
            items = soup.select("p")
            random.shuffle(items)  # 打乱顺序
            
            for item in items:
                if item.find("span") and item.find("a"):
                    return self._parse_history_item(item, response_data.get("update_time", datetime.now().isoformat()))
    
            # 如果没有找到符合条件的事件
            return self._create_error_response("未找到有效事件", response_data.get("update_time", datetime.now().isoformat()))
        else:
            return self._create_error_response("无效响应数据", response_data.get("update_time", datetime.now().isoformat()))

    def _parse_history_item(self, item: Any, update_time: str) -> Dict[str, Any]:
        """解析历史事件项"""
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
            "era": era,
            "update_time": update_time
        }

    def _create_error_response(self, error_msg: str, update_time: str) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            "status": "error",
            "year": "未知",
            "event": error_msg,
            "url": "",
            "era": "未知",
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
            "event": self._format_event,
            "year": self._format_year,
            "url": self._format_url,
            "era": self._format_era
        }
        
        formatter = formatters.get(sensor_key, str)
        return formatter(value)

    def _format_event(self, value: str) -> str:
        return f"📜 {value}" if value and value != "未找到有效事件" else "暂无历史事件"

    def _format_year(self, value: str) -> str:
        return value if value and value != "未知" else "未知年份"

    def _format_url(self, value: str) -> str:
        return value if value else "无详情链接"

    def _format_era(self, value: str) -> str:
        return value if value and value != "未知" else "未知时期"
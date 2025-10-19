from __future__ import annotations
from datetime import datetime
from typing import Dict, Any, List
import logging
import random
import requests
import re
from bs4 import BeautifulSoup
from ..service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_HISTORY_URL = "http://www.todayonhistory.com/"

class HistoryService(BaseService):
    """多传感器版历史上的今天数据服务"""

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
            "url": {
                "name": "API地址",
                "type": "str",
                "default": DEFAULT_HISTORY_URL,
                "description": "历史事件网站地址"
            },
            "interval": {
                "name": "更新间隔（分钟）",
                "type": "int",
                "default": 360,
                "description": "更新间隔时间"
            }
        }

    @property
    def sensor_configs(self) -> List[SensorConfig]:
        """返回每日历史的所有传感器配置"""
        return [
            {
                "key": "event",
                "name": "历史事件",
                "icon": "mdi:book",
                "device_class": None
            },
            {
                "key": "year",
                "name": "历史年份",
                "icon": "mdi:calendar",
                "device_class": None
            },
            {
                "key": "url",
                "name": "详情链接",
                "icon": "mdi:link",
                "device_class": None
            },
            {
                "key": "era",
                "name": "历史时期",
                "icon": "mdi:clock-outline",
                "device_class": None
            }
        ]

    def build_request(self, params: Dict[str, Any]) -> tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建请求参数"""
        base_url = params["url"].strip('/')
        today = datetime.now()
        today_path = f"today-{today.month}-{today.day}.html"
        url = f"{base_url}/{today_path}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
            "Accept": "text/html"
        }
        return url, {}, headers

    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """解析响应数据为标准化字典"""
        if isinstance(response_data.get("data"), str):
            soup = BeautifulSoup(response_data["data"], "html.parser")
    
            # 随机选择一个符合条件的<p>标签
            items = soup.select("p")
            random.shuffle(items)  # 打乱顺序
            for item in items:
                if item.find("span") and item.find("a"):
                    # 提取年份（方括号[]中的内容）
                    year_text = item.find("span").get_text().strip()
                    year_match = re.search(r'\[(.*?)\]', year_text)
                    if year_match:
                        year = year_match.group(1)  # 获取方括号中的内容
                        # 推断历史时期
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
                        "update_time": response_data.get("update_time", datetime.now().isoformat())
                    }
    
            # 如果没有找到符合条件的事件
            return {
                "status": "error",
                "year": "未知",
                "event": "未找到有效事件",
                "url": "",
                "era": "未知",
                "update_time": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "year": "未知",
                "event": "无效响应数据",
                "url": "",
                "era": "未知",
                "update_time": datetime.now().isoformat()
            }
    
    def _infer_era(self, year_str: str) -> str:
        """根据年份推断历史时期"""
        try:
            # 清理年份字符串
            clean_year = re.sub(r'[^\d]', '', year_str)
            if not clean_year:
                return "未知时期"
                
            year = int(clean_year)
            
            if year < 221:
                return "远古时期"
            elif year < 581:
                return "秦汉魏晋南北朝"
            elif year < 907:
                return "隋唐时期"
            elif year < 1279:
                return "宋辽金时期"
            elif year < 1368:
                return "元朝"
            elif year < 1644:
                return "明朝"
            elif year < 1912:
                return "清朝"
            elif year < 1949:
                return "民国时期"
            else:
                return "现代"
                
        except (ValueError, TypeError):
            return "未知时期"

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化特定传感器的显示值"""
        value = self.get_sensor_value(sensor_key, data)
        
        if value is None:
            return "暂无数据"
            
        # 为不同传感器提供特定的格式化
        if sensor_key == "event":
            return f"📜 {value}" if value and value != "未找到有效事件" else "暂无历史事件"
        elif sensor_key == "year":
            return value if value and value != "未知" else "未知年份"
        elif sensor_key == "url":
            return value if value else "无详情链接"
        elif sensor_key == "era":
            return value if value and value != "未知" else "未知时期"
        else:
            return str(value)
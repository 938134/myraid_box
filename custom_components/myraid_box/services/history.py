from __future__ import annotations
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging
import random
import requests
import re
from bs4 import BeautifulSoup
from ..service_base import BaseService, AttributeConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_HISTORY_URL = "http://www.todayonhistory.com/"

class HistoryService(BaseService):
    """历史上的今天数据服务"""

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
    def attributes(self) -> Dict[str, AttributeConfig]:
        return {
            "year": {"name": "年份", "icon": "mdi:calendar"},
            "event": {"name": "事件", "icon": "mdi:book"},
            "update_time": {"name": "更新时间", "icon": "mdi:clock"}
        }

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
        """解析HTML响应数据并随机返回一条事件"""
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
                    else:
                        year = "未知年份"
    
                    event = item.find("a").get_text().strip()
                    url = item.find("a")["href"]
                    return {
                        "status": "success",
                        "year": year,
                        "event": event,
                        "url": url,
                        "update_time": response_data.get("update_time", datetime.now().isoformat())
                    }
    
            # 如果没有找到符合条件的事件
            return {
                "status": "error",
                "error": "未找到有效事件",
                "update_time": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "error": "无效响应数据",
                "update_time": datetime.now().isoformat()
            }
        
    def format_sensor_value(self, data: Any, sensor_config: Dict[str, Any]) -> str:
        """生成主传感器显示值"""
        if not data or data.get("status") != "success":
            return "⏳ 加载中..." if data is None else f"⚠️ {data.get('error', '获取失败')}"
        
        try:
            parsed = self.parse_response(data)
            year = parsed.get("year", "未知年份").strip("[]")  # 去掉年份两边的方括号
            event = parsed.get("event", "未知事件")
            
            # 格式化输出
            return f"📜 {year} {event}"
        except Exception as e:
            _LOGGER.error(f"格式化显示值时出错: {str(e)}")
            return "⚠️ 显示错误"

    def get_sensor_attributes(self, data: Any, sensor_config: Dict[str, Any]) -> Dict[str, Any]:
        """生成传感器属性字典"""
        if not data or data.get("status") != "success":
            return {}
            
        try:
            parsed = self.parse_response(data)
            return super().get_sensor_attributes({
                "year": parsed["year"],
                "event": parsed["event"],
                "update_time": parsed["update_time"] 
            }, sensor_config)
        except Exception as e:
            _LOGGER.error(f"获取属性时出错: {str(e)}")
            return {}

    def get_sensor_configs(self, service_data: Any) -> List[Dict[str, Any]]:
        """返回传感器配置列表"""
        return [{
            "key": "main",
            "name": self.name,
            "icon": self.icon,
            "unit": None,
            "device_class": None
        }]
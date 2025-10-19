from __future__ import annotations
from datetime import datetime
from typing import Dict, Any, List
import re
import logging
from bs4 import BeautifulSoup
from ..service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_OIL_URL = "http://www.qiyoujiage.com/"

class OilService(BaseService):
    """多传感器版每日油价服务"""

    CATEGORY_MAP = {
        "北京": "beijing", "上海": "shanghai", "广东": "guangdong",
        "天津": "tianjin", "重庆": "chongqing", "河北": "hebei",
        "山西": "shanxi", "辽宁": "liaoning", "吉林": "jilin",
        "黑龙江": "heilongjiang", "江苏": "jiangsu", "浙江": "zhejiang",
        "安徽": "anhui", "福建": "fujian", "江西": "jiangxi",
        "山东": "shandong", "河南": "henan", "湖北": "hubei",
        "湖南": "hunan", "海南": "hainan", "四川": "sichuan",
        "贵州": "guizhou", "云南": "yunnan", "陕西": "shaanxi",
        "甘肃": "gansu", "青海": "qinghai", "台湾": "taiwan",
        "内蒙古": "neimenggu", "广西": "guangxi", "西藏": "xizang",
        "宁夏": "ningxia", "新疆": "xinjiang", "香港": "xianggang",
        "澳门": "aomen"
    }

    def __init__(self):
        super().__init__()

    @property
    def service_id(self) -> str:
        return "oilprice"

    @property
    def name(self) -> str:
        return "每日油价"

    @property
    def description(self) -> str:
        return "从汽油价格网获取各省市最新油价"

    @property
    def icon(self) -> str:
        return "mdi:gas-station"

    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "url": {
                "name": "API地址",
                "type": "str",
                "default": DEFAULT_OIL_URL,
                "description": "汽油价格网地址"
            },
            "interval": {
                "name": "更新间隔（分钟）",
                "type": "int",
                "default": 360,
                "description": "更新间隔时间"
            },
            "province": {
                "name": "省份",
                "type": "select",
                "default": "浙江",
                "description": "查询省份",
                "options": sorted(self.CATEGORY_MAP.keys(), key=lambda x: self.CATEGORY_MAP[x])
            }
        }

    @property
    def sensor_configs(self) -> List[SensorConfig]:
        """返回每日油价的所有传感器配置"""
        return [
            {
                "key": "92#",
                "name": "92号汽油",
                "icon": "mdi:gas-station",
                "unit": "元/升",
                "device_class": None
            },
            {
                "key": "95#",
                "name": "95号汽油",
                "icon": "mdi:gas-station",
                "unit": "元/升",
                "device_class": None
            },
            {
                "key": "98#",
                "name": "98号汽油",
                "icon": "mdi:gas-station",
                "unit": "元/升",
                "device_class": None
            },
            {
                "key": "0#",
                "name": "0号柴油",
                "icon": "mdi:gas-station",
                "unit": "元/升",
                "device_class": None
            },
            {
                "key": "province",
                "name": "省份",
                "icon": "mdi:map-marker",
                "device_class": None
            },
            {
                "key": "info",
                "name": "调价窗口期",
                "icon": "mdi:calendar-clock",
                "device_class": None
            },
            {
                "key": "tips",
                "name": "油价走势",
                "icon": "mdi:chart-line",
                "device_class": None
            }
        ]

    def build_request(self, params: Dict[str, Any]) -> tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建请求参数"""
        base_url = params["url"].strip('/')
        province_pinyin = self.CATEGORY_MAP.get(params["province"], "zhejiang")
        
        url = f"{base_url}/{province_pinyin}.shtml"
        headers = {
            "User-Agent": f"HomeAssistant/{self.service_id}",
            "Accept": "text/html"
        }
        return url, {}, headers
        
    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """解析响应数据为标准化字典"""
        if isinstance(response_data.get("data"), str):
            # 解析 HTML 内容
            soup = BeautifulSoup(response_data["data"], "html.parser")
            result = {
                "status": "success",
                "province": "未知",
                "update_time": response_data.get("update_time", datetime.now().isoformat()), 
                "0#": "未知",
                "92#": "未知",
                "95#": "未知",
                "98#": "未知",
                "info": "未知",
                "tips": "未知"
            }

            # 解析省份信息
            title = soup.find("title")
            if title:
                title_text = title.text
                for province in self.CATEGORY_MAP.keys():
                    if province in title_text:
                        result["province"] = province
                        break

            # 解析油品价格
            for dl in soup.select("#youjia > dl"):
                dt_text = dl.select('dt')[0].text.strip() if dl.select('dt') else ""
                dd_text = dl.select('dd')[0].text.strip() if dl.select('dd') else ""
                
                if match := re.search(r"(\d+)#", dt_text):
                    oil_type = f"{match.group(1)}#"
                    result[oil_type] = dd_text

            # 解析调价信息
            info_divs = soup.select("#youjiaCont > div")
            if len(info_divs) > 1:
                result["info"] = info_divs[1].contents[0].strip() if info_divs[1].contents else "未知"
            
            # 解析涨跌信息
            tips_span = soup.select("#youjiaCont > div:nth-of-type(2) > span")
            if tips_span:
                result["tips"] = tips_span[0].text.strip()

            return result
        else:
            # 如果响应数据不是 HTML 字符串，直接返回数据
            return response_data.get("data", {
                "update_time": response_data.get("update_time", datetime.now().isoformat())
            })

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化特定传感器的显示值"""
        value = self.get_sensor_value(sensor_key, data)
        
        if value is None:
            return "暂无数据"
            
        # 为不同传感器提供特定的格式化
        if sensor_key in ["92#", "95#", "98#", "0#"]:
            # 油价传感器 - 清理格式
            cleaned_value = value.replace("元/升", "").strip()
            return f"{cleaned_value}" if cleaned_value and cleaned_value != "未知" else "暂无数据"
        elif sensor_key == "province":
            return value if value and value != "未知" else "未知省份"
        elif sensor_key == "info":
            # 优化调价窗口期显示
            if value and value != "未知":
                # 提取时间信息
                if "下次油价" in value and "调整" in value:
                    # 格式：下次油价10月27日24时调整 → 10月27日24时
                    time_part = value.replace("下次油价", "").replace("调整", "").strip()
                    return time_part
                return value
            return "暂无窗口期信息"
        elif sensor_key == "tips":
            # 优化油价走势显示
            if value and value != "未知":
                # 提取关键调整信息
                if "预计下调" in value:
                    # 格式：目前预计下调油价290元/吨(0.22元/升-0.26元/升) → 预计下调290元/吨
                    if "元/吨" in value:
                        start = value.find("预计下调")
                        end = value.find("元/吨") + 4
                        if start != -1 and end != -1:
                            return value[start:end]
                elif "预计上调" in value:
                    # 格式：目前预计上调油价150元/吨(0.12元/升-0.14元/升) → 预计上调150元/吨
                    if "元/吨" in value:
                        start = value.find("预计上调")
                        end = value.find("元/吨") + 4
                        if start != -1 and end != -1:
                            return value[start:end]
                elif "搁浅" in value or "不作调整" in value:
                    return "本轮搁浅"
                return value
            return "暂无走势信息"
        else:
            return str(value)
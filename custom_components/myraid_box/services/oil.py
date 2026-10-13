from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from ..service_base import BaseService, RequestConfig, SensorConfig

_LOGGER = logging.getLogger(__name__)


class OilService(BaseService):
    """每日油价服务 - 使用新版基类"""

    DEFAULT_API_URL = "http://www.qiyoujiage.com"
    DEFAULT_UPDATE_INTERVAL = 360
    DEFAULT_TIMEOUT = 30

    PROVINCE_MAP = {
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
        self._current_province = "浙江"

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
    def config_help(self) -> str:
        return "⛽ 油价服务配置说明：\n1. 选择要查询的省份\n2. 油价数据每天更新，建议设置较长更新间隔"

    @property
    def icon(self) -> str:
        return "mdi:gas-station"

    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "interval": {
                "name": "更新间隔",
                "type": "int",
                "default": self.DEFAULT_UPDATE_INTERVAL,
                "description": "更新间隔时间（分钟）"
            },
            "province": {
                "name": "省份",
                "type": "select",
                "default": "浙江",
                "description": "查询省份",
                "options": sorted(self.PROVINCE_MAP.keys())
            }
        }

    def _get_sensor_configs(self) -> List[SensorConfig]:
        return [
            self._create_sensor_config("92#", "92号汽油", "mdi:gas-station", "元/升"),
            self._create_sensor_config("95#", "95号汽油", "mdi:gas-station", "元/升"),
            self._create_sensor_config("98#", "98号汽油", "mdi:gas-station", "元/升"),
            self._create_sensor_config("0#", "0号柴油", "mdi:gas-station", "元/升"),
            self._create_sensor_config("province", "省份", "mdi:map-marker"),
            self._create_sensor_config("tip", "油价贴士", "mdi:information-outline"),
            self._create_sensor_config("countdown", "调价倒计时", "mdi:calendar-clock", "天"),
        ]

    def _build_base_request(self, params: Dict[str, Any]) -> RequestConfig:
        province = params.get("province", "浙江")
        self._current_province = province
        province_pinyin = self.PROVINCE_MAP.get(province, "zhejiang")
        
        url = f"{self.default_api_url}/{province_pinyin}.shtml"
        
        return RequestConfig(
            url=url,
            method="GET",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            }
        )

    def _parse_raw_response(self, response_data: Any) -> Dict[str, Any]:
        if not isinstance(response_data, str):
            return {
                "status": "error",
                "error": "无效的响应格式"
            }

        try:
            soup = BeautifulSoup(response_data, "html.parser")
            
            result = {
                "92#": None,
                "95#": None, 
                "98#": None,
                "0#": None,
                "province": self._current_province,
                "tip": "暂无调价信息",
                "countdown": None,
            }

            # 解析油价数据
            youjia_div = soup.select_one("#youjia")
            if youjia_div:
                oil_items = youjia_div.select("dl")
            else:
                oil_items = soup.select("dl")
            
            for item in oil_items:
                dt_elem = item.find('dt')
                dd_elem = item.find('dd')
                
                if not dt_elem or not dd_elem:
                    continue
                    
                oil_type_text = dt_elem.get_text().strip()
                price_text = dd_elem.get_text().strip()
                
                price_match = re.search(r'(\d+\.\d+)', price_text)
                if not price_match:
                    continue
                    
                price = float(price_match.group(1))
                
                if "92#" in oil_type_text:
                    result["92#"] = price
                elif "95#" in oil_type_text:
                    result["95#"] = price
                elif "98#" in oil_type_text:
                    result["98#"] = price
                elif "0#" in oil_type_text:
                    result["0#"] = price

            # 解析调价信息
            info_text = self._extract_adjust_info_text(soup)
            if info_text:
                fields = self._parse_oil_tip_fields(info_text)
                result["tip"] = self._build_tip_text(fields)
                result["countdown"] = self._calculate_countdown(fields)
                # 结构化字段（供 extra_state_attributes 使用）
                result["adjust_date"] = self._format_adjust_date(fields)
                result["direction"] = fields.get("direction")
                result["range_low"] = fields.get("range_low")
                result["range_high"] = fields.get("range_high")
                result["ton_price"] = fields.get("ton_price")

            return result
            
        except Exception as e:
            _LOGGER.error("解析油价数据失败: %s", str(e), exc_info=True)
            return {
                "status": "error", 
                "error": f"解析油价数据失败: {str(e)}"
            }

    @staticmethod
    def _extract_adjust_info_text(soup: BeautifulSoup) -> str:
        """定位含调价信息的最小祖先节点，取其文本。

        旧逻辑用 ``soup.select_one("#youjiaCont")`` 会拿到整个大容器，
        把油价数字和密度说明都混进 tip 匹配文本；改成按内容定位。
        """
        pattern = re.compile(r"下次油价|下次调整|下次调价")
        for node in soup.find_all(string=pattern):
            parent = node.parent
            if parent and parent.name in ("div", "span", "p"):
                text = parent.get_text()
                if pattern.search(text):
                    return text
        # 兜底：整个容器
        container = soup.select_one("#youjiaCont")
        return container.get_text() if container else ""

    @staticmethod
    def _parse_oil_tip_fields(text: str) -> Dict[str, Any]:
        """从调价文本中提取结构化字段。"""
        fields: Dict[str, Any] = {}

        # 调价时间：下次[油价|调整|调价]M月D日[HH时]
        m = re.search(
            r"下次(?:油价|调整|调价)(\d{1,2})月(\d{1,2})日(?:\s*(\d{1,2})\s*时)?",
            text,
        )
        if m:
            fields["month"] = int(m.group(1))
            fields["day"] = int(m.group(2))
            fields["hour"] = int(m.group(3)) if m.group(3) else 24

        # 方向词
        m = re.search(r"(上调|下调|上涨|下跌)", text)
        if m:
            fields["direction"] = m.group(1)

        # 元/升范围（用 ~ 或 - 连接）
        m = re.search(
            r"(\d+\.?\d*)\s*元/升\s*[-~]\s*(\d+\.?\d*)\s*元/升",
            text,
        )
        if m:
            fields["range_low"] = float(m.group(1))
            fields["range_high"] = float(m.group(2))

        # 吨价
        m = re.search(r"(\d+)\s*元/吨", text)
        if m:
            fields["ton_price"] = int(m.group(1))

        return fields

    @staticmethod
    def _build_tip_text(fields: Dict[str, Any]) -> str:
        """把结构化字段拼成人类可读的 tip 文本。"""
        parts: list[str] = []

        if "month" in fields:
            parts.append(
                f"下次{fields['month']}月{fields['day']}日"
                f"{fields.get('hour', 24)}时调整"
            )

        if "direction" in fields and "range_low" in fields:
            parts.append(
                f"预计{fields['direction']} "
                f"{fields['range_low']}~{fields['range_high']}元/升"
            )
        elif "range_low" in fields:
            parts.append(
                f"调整幅度 {fields['range_low']}~{fields['range_high']}元/升"
            )

        if "ton_price" in fields:
            parts.append(f"({fields['ton_price']}元/吨)")

        return "，".join(parts) if parts else ""

    @staticmethod
    def _calculate_countdown(fields: Dict[str, Any]) -> Optional[int]:
        """从结构化字段计算调价倒计时天数。"""
        if "month" not in fields or "day" not in fields:
            return None
        try:
            now = datetime.now()
            year = now.year
            try:
                adjust_date = datetime(year, fields["month"], fields["day"],
                                       23, 59, 59)
            except ValueError:
                return None
            if adjust_date.date() < now.date():
                try:
                    adjust_date = datetime(year + 1, fields["month"],
                                           fields["day"], 23, 59, 59)
                except ValueError:
                    return None
            return max(0, (adjust_date - now).days)
        except Exception as e:
            _LOGGER.debug("[油价服务] 计算倒计时失败: %s", e)
            return None

    @staticmethod
    def _format_adjust_date(fields: Dict[str, Any]) -> str:
        """格式化调价日期为 'YYYY年M月D日'。"""
        if "month" not in fields or "day" not in fields:
            return ""
        now = datetime.now()
        year = now.year
        try:
            target = datetime(year, fields["month"], fields["day"])
            if target.date() < now.date():
                year += 1
        except (ValueError, TypeError):
            return ""
        return f"{year}年{fields['month']}月{fields['day']}日"

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        value = self.get_sensor_value(sensor_key, data)
        
        if value is None:
            return self._get_sensor_default(sensor_key)
            
        if sensor_key in ["92#", "95#", "98#", "0#"]:
            return value
        
        if sensor_key == "countdown":
            if value is None or value < 0:
                return None
            return int(value)
        
        if sensor_key == "tip" and value and len(value) > 100:
            return value[:97] + "..."
            
        return super().format_sensor_value(sensor_key, data)

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        attributes = super().get_sensor_attributes(sensor_key, data)
        
        if not data or data.get("status") != "success":
            return attributes
            
        parsed_data = data.get("data", {})
        
        if sensor_key == "province":
            attributes.update({
                "92号汽油": f"{parsed_data['92#']}元/升" if parsed_data.get("92#") is not None else "未知",
                "95号汽油": f"{parsed_data['95#']}元/升" if parsed_data.get("95#") is not None else "未知",
                "98号汽油": f"{parsed_data['98#']}元/升" if parsed_data.get("98#") is not None else "未知",
                "0号柴油": f"{parsed_data['0#']}元/升" if parsed_data.get("0#") is not None else "未知",
                "油价贴士": parsed_data.get("tip", ""),
                "调价日期": parsed_data.get("adjust_date") or "未知",
                "数据来源": "qiyoujiage.com",
                "更新时间": data.get("update_time", "未知"),
            })

        elif sensor_key == "countdown":
            days_left = parsed_data.get("countdown")
            if days_left is not None:
                if days_left == 0:
                    attributes["今日状态"] = "今日调价"
                elif days_left == 1:
                    attributes["今日状态"] = "明天调价"
                elif days_left <= 3:
                    attributes["今日状态"] = f"还有{days_left}天，临近调价"
                else:
                    attributes["今日状态"] = f"还有{days_left}天"

            if parsed_data.get("adjust_date"):
                attributes["调价日期"] = parsed_data["adjust_date"]
            if parsed_data.get("direction"):
                attributes["调整方向"] = parsed_data["direction"]
            if parsed_data.get("range_low") is not None:
                attributes["调整幅度"] = (
                    f"{parsed_data['range_low']}~{parsed_data['range_high']}元/升"
                )
            if parsed_data.get("ton_price") is not None:
                attributes["吨价"] = f"{parsed_data['ton_price']}元/吨"

        return attributes

    def get_sensor_icon(self, sensor_key: str, data: Any) -> str:
        if sensor_key == "countdown":
            value = self.get_sensor_value(sensor_key, data)
            if value is not None:
                if value == 0:
                    return "mdi:alert-circle"
                elif value == 1:
                    return "mdi:clock-alert-outline"
                elif value <= 3:
                    return "mdi:clock-alert"
                else:
                    return "mdi:calendar-arrow-right"
            return "mdi:calendar-arrow-right"
        
        return super().get_sensor_icon(sensor_key, data)

    def _get_default_value(self, key: str) -> Any:
        if key in ["92#", "95#", "98#", "0#"]:
            return None
            
        if key == "countdown":
            return None
            
        defaults = {
            "province": "未知省份",
            "tip": "暂无调价信息",
        }
        return defaults.get(key, super()._get_default_value(key))

    def _get_sensor_default(self, sensor_key: str) -> Any:
        if sensor_key in ["92#", "95#", "98#", "0#"]:
            return None
            
        if sensor_key == "countdown":
            return None
            
        defaults = {
            "province": "加载中...", 
            "tip": "加载中...",
        }
        return defaults.get(sensor_key, super()._get_sensor_default(sensor_key))

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        province = config.get("province")
        if province and province not in cls.PROVINCE_MAP:
            raise ValueError(f"无效的省份: {province}")
from typing import Dict, Any, List
from datetime import datetime
import logging
import re
from bs4 import BeautifulSoup
from ..service_base import BaseService, SensorConfig, RequestConfig

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
            info_container = soup.select_one("#youjiaCont")
            if not info_container:
                info_container = soup.find("div", string=re.compile(r"下次油价"))
                if not info_container:
                    info_container = soup.find(string=re.compile(r"下次油价"))
                    if info_container:
                        info_container = info_container.parent
            
            if info_container:
                text = info_container.get_text()
                
                # 提取调整时间
                window_match = re.search(r'下次油价(\d+月\d+日\d*时?)调整', text)
                
                # 提取涨幅信息
                price_match = re.search(r'油价(上涨|下跌|上调|下调)(\d+\.?\d*元/升-\d+\.?\d*元/升)', text)
                if not price_match:
                    price_match = re.search(r'(上涨|下跌|上调|下调)(\d+\.?\d*元/升-\d+\.?\d*元/升)', text)
                if not price_match:
                    price_match = re.search(r'(\d+\.?\d*元/升-\d+\.?\d*元/升)', text)
                
                # 提取吨价信息
                ton_match = re.search(r'\((.+?)\)', text)
                
                # 构建完整贴士
                tip_parts = []
                
                if window_match:
                    tip_parts.append(f"下次油价{window_match.group(1)}调整")
                
                if price_match:
                    if len(price_match.groups()) == 2:
                        direction = price_match.group(1)
                        price_range = price_match.group(2)
                        tip_parts.append(f"油价{direction}{price_range}")
                    elif len(price_match.groups()) == 1:
                        tip_parts.append(f"油价{price_match.group(1)}")
                    else:
                        tip_parts.append(f"油价{price_match.group(0)}")
                
                if ton_match:
                    tip_parts.append(ton_match.group(1))
                
                if tip_parts:
                    if len(tip_parts) >= 3:
                        result["tip"] = f"{tip_parts[0]}，{tip_parts[1]}{tip_parts[2]}"
                    elif len(tip_parts) == 2:
                        result["tip"] = f"{tip_parts[0]}，{tip_parts[1]}"
                    else:
                        result["tip"] = tip_parts[0]
                elif window_match:
                    result["tip"] = f"下次油价{window_match.group(1)}调整"
                elif price_match:
                    result["tip"] = f"油价{price_match.group(0)}"

                result["countdown"] = self._calculate_countdown(text)
            
            return result
            
        except Exception as e:
            _LOGGER.error("解析油价数据失败: %s", str(e), exc_info=True)
            return {
                "status": "error", 
                "error": f"解析油价数据失败: {str(e)}"
            }

    def _calculate_countdown(self, text: str) -> int | None:
        try:
            patterns = [
                r'下次调整[：:]\s*(\d{1,2})月(\d{1,2})日',
                r'下次油价(\d{1,2})月(\d{1,2})日(?:\d*时?)',
                r'调整时间[：:]\s*(\d{1,2})月(\d{1,2})日',
                r'(\d{1,2})月(\d{1,2})日.*?调整',
                r'下次油价(\d{1,2})月(\d{1,2})日',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    month = int(match.group(1))
                    day = int(match.group(2))
                    
                    now = datetime.now()
                    current_year = now.year
                    
                    try:
                        adjust_date = datetime(current_year, month, day, 23, 59, 59)
                    except ValueError:
                        continue
                    
                    if adjust_date.date() < now.date():
                        adjust_date = datetime(current_year + 1, month, day, 23, 59, 59)
                    
                    days_left = (adjust_date - now).days
                    return max(0, days_left)
            
            return None
            
        except Exception as e:
            _LOGGER.debug("[油价服务] 计算倒计时失败: %s", str(e))
            return None

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
            oil_92 = parsed_data.get("92#")
            oil_95 = parsed_data.get("95#")
            oil_98 = parsed_data.get("98#")
            oil_0 = parsed_data.get("0#")
            tip = parsed_data.get("tip", "")
            adjust_date = self._extract_date_from_tip(tip)
            
            attributes.update({
                "92号汽油": f"{oil_92}元/升" if oil_92 is not None else "未知",
                "95号汽油": f"{oil_95}元/升" if oil_95 is not None else "未知",
                "98号汽油": f"{oil_98}元/升" if oil_98 is not None else "未知",
                "0号柴油": f"{oil_0}元/升" if oil_0 is not None else "未知",
                "油价贴士": tip,
                "调价日期": adjust_date if adjust_date else "未知",
                "数据来源": "qiyoujiage.com",
                "更新时间": data.get("update_time", "未知")
            })
        
        elif sensor_key == "countdown":
            tip = parsed_data.get("tip", "")
            adjust_date = self._extract_date_from_tip(tip)
            days_left = parsed_data.get("countdown")
            
            if adjust_date:
                attributes["调价日期"] = adjust_date
                attributes["调价时间"] = "当日24时"
            
            if days_left is not None:
                if days_left == 0:
                    attributes["今日状态"] = "今日调价"
                elif days_left == 1:
                    attributes["今日状态"] = "明天调价"
                elif days_left <= 3:
                    attributes["今日状态"] = f"还有{days_left}天，临近调价"
                else:
                    attributes["今日状态"] = f"还有{days_left}天"
        
        return attributes

    def _extract_date_from_tip(self, tip: str) -> str | None:
        try:
            match = re.search(r'(\d{1,2})月(\d{1,2})日', tip)
            if match:
                month = int(match.group(1))
                day = int(match.group(2))
                
                now = datetime.now()
                year = now.year
                
                if month < now.month or (month == now.month and day < now.day):
                    year += 1
                
                return f"{year}年{month}月{day}日"
            
            return None
        except Exception:
            return None

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
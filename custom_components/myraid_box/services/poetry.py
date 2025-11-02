from typing import Dict, Any, List, Tuple
from datetime import datetime
import logging
import re
import aiohttp
import asyncio
import time
from ..service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)

class PoetryService(BaseService):
    """多传感器版每日诗词服务 - v2 API版本"""

    DEFAULT_API_URL = "https://v2.jinrishici.com/one.json"
    DEFAULT_TOKEN_URL = "https://v2.jinrishici.com/token"
    DEFAULT_UPDATE_INTERVAL = 10

    def __init__(self):
        super().__init__()
        self._token_initialized = False
        self._token_lock = asyncio.Lock()
        self._fallback_data = None

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
        """返回传感器配置"""
        return [
            # 核心信息 - 高优先级
            self._create_sensor_config("content", "名句", "mdi:format-quote-open", None, None, 1),
            self._create_sensor_config("title", "标题", "mdi:book", None, None, 2),
            self._create_sensor_config("author", "诗人", "mdi:account", None, None, 3),
            self._create_sensor_config("dynasty", "朝代", "mdi:castle", None, None, 4),
            
            # 扩展信息 - 中优先级
            self._create_sensor_config("full_content", "全文", "mdi:book-open-variant", None, None, 5),
            self._create_sensor_config("translate", "译文", "mdi:comment-text", None, None, 6),
        ]

    async def _ensure_token(self, params: Dict[str, Any]) -> str:
        """确保有有效的token"""
        async with self._token_lock:
            if self._token and self._token_expiry and time.time() < self._token_expiry:
                return self._token

            try:
                await self._ensure_session()
                async with self._session.get(self.DEFAULT_TOKEN_URL, timeout=10) as response:
                    data = await response.json()
                    if data.get("status") == "success":
                        self._token = data.get("data")
                        # 设置token有效期为23小时（API token通常有效期较长）
                        self._token_expiry = time.time() + 82800  # 23小时
                        self._token_initialized = True
                        _LOGGER.info("成功获取今日诗词API Token")
                        return self._token
            except Exception as e:
                _LOGGER.warning("获取诗词API Token异常: %s，使用默认token", e)

            # 如果获取token失败，使用默认token
            self._token = "homeassistant-poetry-service"
            self._token_expiry = time.time() + 3600  # 1小时
            self._token_initialized = True
            return self._token

    def _build_request_headers(self, token: str = "") -> Dict[str, str]:
        """构建请求头 - 包含诗词API认证"""
        headers = {
            "Accept": "application/json",
            "User-Agent": f"HomeAssistant/{self.service_id}"
        }
        
        # 添加诗词API认证头
        if token:
            headers["X-User-Token"] = token
            
        return headers

    def build_request(self, params: Dict[str, Any], token: str = "") -> Tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建请求参数 - 支持Token认证"""
        url = self.default_api_url
        request_params = {}
        headers = self._build_request_headers(token)
        
        return url, request_params, headers

    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Dict[str, Any]:
        """重写数据获取方法以处理API错误"""
        await self._ensure_session()
        try:
            # 确保有有效的token
            token = await self._ensure_token(params)
            url, request_params, headers = self.build_request(params, token)
            
            async with self._session.get(url, params=request_params, headers=headers, timeout=10) as resp:
                # 检查HTTP状态码
                if resp.status >= 500:
                    _LOGGER.warning("[诗词服务] API服务器错误 (%s)，使用备用数据", resp.status)
                    return self._get_fallback_response()
                elif resp.status >= 400:
                    _LOGGER.warning("[诗词服务] API客户端错误 (%s)，使用备用数据", resp.status)
                    return self._get_fallback_response()
                
                content_type = resp.headers.get("Content-Type", "").lower()
                if "application/json" in content_type:
                    data = await resp.json()
                else:
                    data = await resp.text()
                
                return {
                    "data": data,
                    "status": "success",
                    "error": None,
                    "update_time": datetime.now().isoformat()
                }
                    
        except aiohttp.ClientError as e:
            _LOGGER.warning("[诗词服务] 网络请求失败: %s，使用备用数据", str(e))
            return self._get_fallback_response()
        except asyncio.TimeoutError:
            _LOGGER.warning("[诗词服务] 请求超时，使用备用数据")
            return self._get_fallback_response()
        except Exception as e:
            _LOGGER.warning("[诗词服务] 请求失败: %s，使用备用数据", str(e))
            return self._get_fallback_response()

    def _get_fallback_response(self) -> Dict[str, Any]:
        """获取备用数据响应"""
        # 如果有之前的有效数据，继续使用
        if self._fallback_data:
            _LOGGER.debug("[诗词服务] 使用之前的有效数据作为备用")
            return self._fallback_data
        
        # 生成默认的备用数据
        fallback_data = {
            "data": {
                "data": {
                    "content": "床前明月光，疑是地上霜。",
                    "origin": {
                        "title": "静夜思",
                        "author": "李白",
                        "dynasty": "唐",
                        "content": ["床前明月光，", "疑是地上霜。", "举头望明月，", "低头思故乡。"],
                        "translate": ["明亮的月光洒在窗户纸上，好像地上泛起了一层霜。", "我禁不住抬起头来，看那天窗外空中的一轮明月，不由得低头沉思，想起远方的家乡。"]
                    }
                },
                "status": "success"
            },
            "status": "success",
            "error": None,
            "update_time": datetime.now().isoformat()
        }
        
        # 保存备用数据供下次使用
        self._fallback_data = fallback_data
        return fallback_data

    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """解析API响应数据"""
        try:
            # 处理基类返回的数据结构
            if isinstance(response_data, dict) and "data" in response_data:
                api_data = response_data["data"]
                update_time = response_data.get("update_time", datetime.now().isoformat())
                
                # 如果是备用数据，直接解析
                if api_data and isinstance(api_data, dict) and api_data.get("status") == "success":
                    actual_data = api_data.get("data", {})
                    if actual_data:
                        api_data = actual_data
            else:
                api_data = response_data
                update_time = datetime.now().isoformat()

            # 检查API响应状态
            if isinstance(api_data, dict) and api_data.get("status") == "error":
                _LOGGER.warning("[诗词服务] API返回错误: %s", api_data.get("errMessage"))
                return self._create_error_response()

            # 解析数据结构
            data = api_data.get('data', api_data)  # 兼容不同结构
            origin_data = data.get('origin', {})
            
            # 提取字段
            content = data.get('content', '')  # 精选诗句
            title = origin_data.get('title', '未知')  # 诗词标题
            author = origin_data.get('author', '佚名')  # 诗人
            dynasty = origin_data.get('dynasty', '未知')  # 朝代
            full_content_list = origin_data.get('content', [])  # 完整诗词内容列表
            translate = origin_data.get('translate')  # 译文
            
            # 格式化完整诗词内容
            full_content = self._format_poetry_content(full_content_list) if full_content_list else "无完整内容"
            
            # 格式化译文
            formatted_translate = self._format_translate(translate) if translate else "无译文"

            result = {
                "content": content,
                "title": title,
                "author": author,
                "dynasty": dynasty,
                "full_content": full_content,
                "translate": formatted_translate,
                "update_time": update_time
            }
            
            # 保存成功的数据作为备用
            if content and content != "床前明月光，疑是地上霜。":  # 不是默认备用数据
                self._fallback_data = {
                    "data": response_data.get("data") if isinstance(response_data, dict) else response_data,
                    "status": "success",
                    "error": None,
                    "update_time": update_time
                }
            
            return result
            
        except Exception as e:
            _LOGGER.warning("[诗词服务] 解析诗词数据时发生异常: %s，返回错误响应", e)
            return self._create_error_response()

    def _format_poetry_content(self, content_list: List[str]) -> str:
        """格式化完整诗词内容"""
        if not content_list:
            return "无完整内容"
            
        # 将诗句列表连接成一个字符串，并在适当位置添加换行
        combined_content = "".join(content_list)
        
        # 在标点符号后添加换行，使诗句更易读
        formatted_content = re.sub(r'([。！？])', r'\1\n', combined_content)
        formatted_content = re.sub(r'([，])', r'\1 ', formatted_content)
        
        # 清理多余的换行符和空格
        formatted_content = re.sub(r'\n+', '\n', formatted_content).strip()
        formatted_content = re.sub(r' +', ' ', formatted_content)
        
        # 限制最大长度，保留安全边界
        max_length = 500  # 完整诗词可能较长
        if len(formatted_content) > max_length:
            formatted_content = formatted_content[:max_length-3] + "..."
        
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
            
        # 限制译文长度
        max_length = 300
        if len(translated_text) > max_length:
            translated_text = translated_text[:max_length-3] + "..."
            
        return translated_text

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化传感器显示值"""
        value = self.get_sensor_value(sensor_key, data)
        if not value:
            return self._get_default_value(sensor_key)
        
        # 对内容字段进行额外处理
        if sensor_key in ["content", "full_content"]:
            # 移除可能存在的引号等符号
            value = re.sub(r'[「」『』"\'""]', '', value).strip()
            # 确保长度不超过限制
            max_length = 255 if sensor_key == "content" else 500
            if len(value) > max_length:
                value = value[:max_length-3] + "..."
        
        return value

    def _get_default_value(self, sensor_key: str) -> str:
        """获取默认值"""
        return {
            "content": "无有效内容",
            "title": "未知标题",
            "author": "佚名", 
            "dynasty": "未知",
            "full_content": "无完整内容",
            "translate": "无译文"
        }.get(sensor_key, "暂无数据")

    def _create_error_response(self) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            "content": "无有效内容",
            "title": "未知标题",
            "author": "佚名",
            "dynasty": "未知", 
            "full_content": "无完整内容",
            "translate": "无译文",
            "update_time": datetime.now().isoformat()
        }

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        """获取传感器的额外属性"""
        if not data or data.get("status") != "success":
            return {}
            
        attributes = {
            "更新时间": data.get("update_time", "未知"),
            "数据状态": "成功"
        }
        
        return attributes

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """验证服务配置"""
        # 诗词服务没有特殊验证要求
        pass
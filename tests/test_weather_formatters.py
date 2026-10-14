"""WeatherService 格式化函数测试（纯逻辑，不发请求）。

所有纯格式化函数已从 ``services.weather`` 单文件直接导入，
不再通过 ``WeatherService`` 实例访问。这样测试直接验证纯函数，
无需构造 service 实例（也不用担心 session / token / hass 依赖）。
"""
from __future__ import annotations

from custom_components.myraid_box.services.weather import (
    build_sensor_attributes,
    format_future_weather,
    format_sensor_value,
    format_temperature,
    format_today_detail,
    format_weather_text,
    format_wind_text,
    get_day_forecast,
    get_sensor_default,
)


# ============================================================
# format_temperature
# ============================================================

def test_temperature_both_none():
    assert format_temperature(None, None) == "未知"


def test_temperature_only_max():
    assert format_temperature(None, "28") == "28°C"


def test_temperature_only_min():
    assert format_temperature("20", None) == "20°C"


def test_temperature_equal_values():
    assert format_temperature("22", "22") == "22°C"


def test_temperature_range():
    assert format_temperature("18", "26") == "18~26°C"


def test_temperature_handles_numeric_input():
    assert format_temperature(15, 25) == "15~25°C"


# ============================================================
# format_weather_text
# ============================================================

def test_weather_text_both_empty():
    assert format_weather_text("", "") == "未知"


def test_weather_text_only_day():
    assert format_weather_text("晴", "") == "晴"


def test_weather_text_only_night():
    assert format_weather_text("", "多云") == "多云"


def test_weather_text_same_day_night():
    assert format_weather_text("晴", "晴") == "晴"


def test_weather_text_different():
    assert format_weather_text("晴", "多云") == "白天晴，夜间多云"


# ============================================================
# format_wind_text
# ============================================================

def test_wind_text_all_empty():
    assert format_wind_text("", "", "", "") == "未知"


def test_wind_text_only_day():
    assert format_wind_text("东风", "3", "", "") == "东风3级"


def test_wind_text_only_night():
    assert format_wind_text("", "", "西风", "4") == "西风4级"


def test_wind_text_same():
    assert format_wind_text("南风", "2", "南风", "2") == "南风2级"


def test_wind_text_different():
    assert format_wind_text("北风", "3", "东风", "2") == "白天北风3级，夜间东风2级"


# ============================================================
# get_day_forecast
# ============================================================

def test_get_day_forecast_valid():
    data = [{"tempMin": "10"}, {"tempMin": "15"}]
    assert get_day_forecast(data, 0) == {"tempMin": "10"}
    assert get_day_forecast(data, 1) == {"tempMin": "15"}


def test_get_day_forecast_out_of_range():
    assert get_day_forecast([{"tempMin": "10"}], 5) is None
    assert get_day_forecast([], 0) is None
    assert get_day_forecast(None, 0) is None


# ============================================================
# format_future_weather
# ============================================================

def test_future_weather_no_data():
    assert format_future_weather(None) == "暂无数据"


def test_future_weather_full():
    data = {
        "textDay": "晴",
        "textNight": "多云",
        "tempMin": "18",
        "tempMax": "26",
        "windDirDay": "东风",
        "windScaleDay": "3",
        "windDirNight": "东风",
        "windScaleNight": "3",
    }
    result = format_future_weather(data)
    assert "白天晴，夜间多云" in result
    assert "18~26°C" in result
    assert "东风3级" in result


# ============================================================
# format_today_detail
# ============================================================

def test_today_detail_no_data():
    assert format_today_detail({}) == "暂无数据"


def test_today_detail_rain_reminder():
    data = {
        "textDay": "小雨",
        "textNight": "多云",
        "tempMin": "15",
        "tempMax": "22",
        "windDirDay": "东风",
        "windScaleDay": "2",
        "windDirNight": "东风",
        "windScaleNight": "2",
        "humidity": 80,
    }
    assert "雨具" in format_today_detail(data)


def test_today_detail_uv_strong_reminder():
    data = {"textDay": "晴", "textNight": "晴", "tempMin": "20", "tempMax": "28", "uvIndex": 8}
    result = format_today_detail(data)
    assert "紫外线强烈" in result
    assert "防晒" in result


def test_today_detail_hot_reminder():
    data = {"textDay": "晴", "textNight": "晴", "tempMin": "25", "tempMax": "35"}
    assert "炎热" in format_today_detail(data)


def test_today_detail_cold_reminder():
    data = {"textDay": "晴", "textNight": "晴", "tempMin": "-5", "tempMax": "3"}
    assert "寒冷" in format_today_detail(data) or "添衣" in format_today_detail(data)


def test_today_detail_all_parts_present():
    data = {
        "textDay": "晴",
        "textNight": "晴",
        "tempMin": "20",
        "tempMax": "28",
        "windDirDay": "东风",
        "windScaleDay": "2",
        "windDirNight": "东风",
        "windScaleNight": "2",
        "humidity": 60,
    }
    result = format_today_detail(data)
    assert "温度20~28°C" in result
    assert "湿度60%" in result
    assert "风力东风2级" in result


# ============================================================
# get_sensor_default
# ============================================================

def test_sensor_default_numeric_keys_return_none():
    """数值型传感器默认 None（HA 会显示 "Unknown"）。"""
    for key in ("today_humidity", "today_precip", "today_pressure", "today_vis", "today_cloud"):
        assert get_sensor_default(key) is None, f"{key} 应返回 None"


def test_sensor_default_text_keys_return_loading():
    """文本型传感器默认"加载中..."。"""
    for key in ("city_name", "today_weather", "today_temp", "today_wind", "today_uv"):
        assert get_sensor_default(key) == "加载中...", f"{key} 应为加载中"


def test_sensor_default_unknown_key_returns_loading():
    assert get_sensor_default("not_a_real_key") == "加载中..."


# ============================================================
# format_sensor_value（分派器）
# ============================================================

def _success_data(**daily):
    """构造一个 success 状态的 data（含 3 天预报）。"""
    return {
        "status": "success",
        "data": {
            "city_info": {"name": "北京", "id": "101010100"},
            "api_source": {"city_api": "测试", "weather_api": "测试"},
            "daily_forecast": [daily] * 3 if daily else [],
            "jwt_status": "valid",
            "update_time": "2026-01-01T00:00:00",
        },
    }


def test_format_sensor_value_city_name():
    data = _success_data()
    data["data"]["city_info"] = {"name": "上海"}
    assert format_sensor_value("city_name", data) == "上海"


def test_format_sensor_value_today_weather():
    data = _success_data(textDay="晴", textNight="多云")
    assert format_sensor_value("today_weather", data) == "白天晴，夜间多云"


def test_format_sensor_value_today_temp():
    data = _success_data(tempMin="10", tempMax="25")
    assert format_sensor_value("today_temp", data) == "10~25°C"


def test_format_sensor_value_today_humidity_returns_number():
    data = _success_data(humidity=75)
    assert format_sensor_value("today_humidity", data) == 75


def test_format_sensor_value_tomorrow_weather_uses_index1():
    data = _success_data(textDay="雪", textNight="晴")
    # day1 也是同样数据，验证 tomorrow 也走 format_future_weather
    assert "雪" in format_sensor_value("tomorrow_weather", data)


def test_format_sensor_value_returns_default_when_status_not_success():
    assert format_sensor_value("city_name", {"status": "error", "data": {}}) == "加载中..."


def test_format_sensor_value_returns_default_when_data_empty():
    assert format_sensor_value("city_name", {}) == "加载中..."


def test_format_sensor_value_unknown_key_returns_default():
    data = _success_data()
    assert format_sensor_value("not_a_real_key", data) == "加载中..."


# ============================================================
# build_sensor_attributes
# ============================================================

def test_build_sensor_attributes_basic_fields():
    data = _success_data()
    attrs = build_sensor_attributes("today_weather", data)
    assert attrs["数据来源"] == "测试"
    assert attrs["天气数据来源"] == "测试"
    assert attrs["JWT状态"] == "valid"
    assert attrs["更新时间"] == "2026-01-01T00:00:00"


def test_build_sensor_attributes_city_name_includes_geo():
    data = _success_data()
    data["data"]["city_info"] = {"id": "101010100", "country": "中国", "adm1": "北京", "adm2": "市"}
    attrs = build_sensor_attributes("city_name", data)
    assert attrs["城市ID"] == "101010100"
    assert attrs["国家"] == "中国"
    assert "省份" in attrs


def test_build_sensor_attributes_today_weather_includes_detail():
    """today_weather 专属：包含"详情"字段。"""
    data = _success_data(textDay="晴", textNight="晴", tempMin="20", tempMax="28")
    attrs = build_sensor_attributes("today_weather", data)
    assert "详情" in attrs
    assert "日出" in attrs
    assert "日落" in attrs


def test_build_sensor_attributes_tomorrow_does_not_include_detail():
    """tomorrow_weather 也有 3 天共享属性，但没有"详情"。"""
    data = _success_data(textDay="晴", textNight="晴", tempMin="20", tempMax="28")
    attrs = build_sensor_attributes("tomorrow_weather", data)
    assert "日出" in attrs
    assert "详情" not in attrs


def test_build_sensor_attributes_empty_when_status_not_success():
    assert build_sensor_attributes("city_name", {"status": "error", "data": {}}) == {}


def test_build_sensor_attributes_empty_when_data_none():
    assert build_sensor_attributes("city_name", None) == {}

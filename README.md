万象盒子 (Myraid Box)
https://img.shields.io/badge/HACS-Custom-41BDF5.svg
https://img.shields.io/badge/version-2.0.0-blue.svg
https://img.shields.io/badge/Home%2520Assistant-2023.8%252B-orange.svg

包罗万象，从一个集成开始

万象盒子是一个多服务数据聚合平台，为 Home Assistant 提供丰富多样的每日数据服务，包括每日一言、经典诗词、天气预报、油价查询、历史事件等。

🚀 特色功能
📝 每日一言
从一言官网获取励志名言，支持多种分类筛选

内容传感器: 显示名言内容

分类传感器: 显示名言分类（文学、影视、哲学等）

作者传感器: 显示名言作者

来源传感器: 显示名言出处

📚 每日诗词
从古诗词API获取经典诗词，支持主题分类

诗句传感器: 显示诗词内容

诗人传感器: 显示诗词作者

出处传感器: 显示诗词出处

朝代传感器: 显示诗词朝代

⛽ 每日油价
从汽油价格网获取全国各省市最新油价信息

92号汽油传感器: 显示92号汽油价格

95号汽油传感器: 显示95号汽油价格

98号汽油传感器: 显示98号汽油价格

0号柴油传感器: 显示0号柴油价格

省份传感器: 显示查询省份

调价窗口期传感器: 显示下次调价时间

油价走势传感器: 显示价格调整趋势

📜 每日历史
从历史网站获取当天历史事件

历史事件传感器: 显示历史事件内容

历史年份传感器: 显示事件发生年份

详情链接传感器: 显示事件详情链接

历史时期传感器: 显示事件所属历史时期

🌤️ 每日天气
从和风天气获取3天天气预报

今日天气传感器: 显示今天天气状况

明日天气传感器: 显示明天天气状况

后天天气传感器: 显示后天天气状况

天气趋势传感器: 显示3天天气趋势

📥 安装
通过 HACS 安装（推荐）
打开 HACS

点击「集成」

点击右下角「+ 浏览并下载仓库」

搜索「万象盒子」或「Myraid Box」

点击「下载」

重启 Home Assistant

手动安装
下载最新版本

将 custom_components/myraid_box 文件夹复制到你的 Home Assistant 配置目录中

重启 Home Assistant

⚙️ 配置
通过界面配置
打开 Home Assistant

进入「配置」->「设备与服务」

点击「+ 添加集成」

搜索「万象盒子」

按照向导步骤配置所需服务

配置选项
每个服务都支持以下配置：

启用/禁用: 选择要使用的服务

API地址: 服务的数据源地址

更新间隔: 数据更新频率（分钟）

分类/省份: 特定服务的筛选条件

🔧 服务详情
每日一言
默认API: https://v1.hitokoto.cn

更新间隔: 10分钟

支持分类: 动画、漫画、游戏、文学、原创、网络、影视、诗词、哲学等

每日诗词
默认API: https://v1.jinrishici.com

更新间隔: 10分钟

支持分类: 抒情、四季、山水、天气、人物、人生、生活、节日等

每日油价
默认API: http://www.qiyoujiage.com/

更新间隔: 360分钟

支持省份: 全国31个省市自治区

每日历史
默认API: http://www.todayonhistory.com/

更新间隔: 360分钟

每日天气
默认API: https://devapi.qweather.com/v7/weather/3d

更新间隔: 30分钟

需要配置: 城市LocationID 和 API Key

📊 传感器列表
每个服务都会创建多个专用传感器：

每日一言传感器
sensor.myraid_box_hitokoto_content - 名言内容

sensor.myraid_box_hitokoto_category - 名言分类

sensor.myraid_box_hitokoto_author - 名言作者

sensor.myraid_box_hitokoto_source - 名言来源

每日诗词传感器
sensor.myraid_box_poetry_content - 诗句内容

sensor.myraid_box_poetry_author - 诗词作者

sensor.myraid_box_poetry_origin - 诗词出处

sensor.myraid_box_poetry_dynasty - 诗词朝代

每日油价传感器
sensor.myraid_box_oilprice_92 - 92号汽油价格

sensor.myraid_box_oilprice_95 - 95号汽油价格

sensor.myraid_box_oilprice_98 - 98号汽油价格

sensor.myraid_box_oilprice_0 - 0号柴油价格

sensor.myraid_box_oilprice_province - 查询省份

sensor.myraid_box_oilprice_info - 调价窗口期

sensor.myraid_box_oilprice_tips - 油价走势

每日历史传感器
sensor.myraid_box_history_event - 历史事件

sensor.myraid_box_history_year - 历史年份

sensor.myraid_box_history_url - 详情链接

sensor.myraid_box_history_era - 历史时期

每日天气传感器
sensor.myraid_box_weather_day_0 - 今日天气

sensor.myraid_box_weather_day_1 - 明日天气

sensor.myraid_box_weather_day_2 - 后天天气

sensor.myraid_box_weather_trend - 天气趋势

🎨 自动化示例
每日早安播报
yaml
alias: 每日早安播报
trigger:
  - platform: time
    at: "07:00:00"
action:
  - service: tts.speak
    data:
      message: >
        早上好！今天是{{ now().strftime('%m月%d日') }}，
        今日名言：{{ states('sensor.myraid_box_hitokoto_content') }}，
        今天历史上的今天：{{ states('sensor.myraid_box_history_event') }}，
        当前气温{{ states('sensor.myraid_box_weather_today_temp') }}度。
油价上涨提醒
yaml
alias: 油价上涨提醒
trigger:
  - platform: state
    entity_id: sensor.myraid_box_oilprice_tips
    to: "*上调*"
action:
  - service: notify.mobile_app
    data:
      message: >
        油价即将上涨！{{ states('sensor.myraid_box_oilprice_tips') }}，
        调价窗口期：{{ states('sensor.myraid_box_oilprice_info') }}
诗词分享
yaml
alias: 每日诗词分享
trigger:
  - platform: time
    at: "12:00:00"
action:
  - service: notify.wechat
    data:
      message: >
        📚 今日诗词
        {{ states('sensor.myraid_box_poetry_content') }}
        ——{{ states('sensor.myraid_box_poetry_author') }}《{{ states('sensor.myraid_box_poetry_origin') }}》
🔍 故障排除
常见问题
传感器显示"暂无数据"

检查网络连接

确认API地址是否正确

查看日志获取详细错误信息

服务无法加载

重启 Home Assistant

检查集成配置是否正确

确认依赖包已安装

数据更新不及时

调整更新间隔设置

检查API服务是否稳定

查看日志
在 configuration.yaml 中启用调试日志：

yaml
logger:
  default: info
  logs:
    custom_components.myraid_box: debug
🤝 贡献
欢迎提交 Issue 和 Pull Request！

GitHub 仓库

问题反馈

📄 许可证
本项目采用 MIT 许可证。

🙏 致谢
感谢以下数据服务提供商：

一言 - 每日一言数据

今日诗词 - 诗词数据

和风天气 - 天气数据

汽油价格网 - 油价数据

今天历史 - 历史事件数据

让智能家居更有文化，让日常生活更有趣味！ 🎉

万象盒子 - 包罗万象，从一个集成开始


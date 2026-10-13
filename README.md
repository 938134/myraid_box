[file name]: README.md
[file content begin]
# 万象盒子 (Myraid Box) - 智能生活数据聚合平台

![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)
![Version](https://img.shields.io/badge/version-2.1.0-blue.svg)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.6%2B-orange.svg)

**包罗万象，从一个集成开始**

万象盒子是一个专为 Home Assistant 设计的智能数据聚合平台，集成了多种实用的日常数据服务，让您的智能家居更加丰富多彩。

## 🚀 核心特色

### 📝 每日一言
- **数据源**: 一言官网 (Hitokoto)
- **功能**: 每日励志名言，支持多种分类
- **传感器**:
  - 名言内容
  - 名言分类（文学、影视、哲学等）
  - 名言作者
  - 名言来源

### 📚 每日诗词  
- **数据源**: 今日诗词 API
- **功能**: 经典古诗词欣赏，陶冶情操
- **传感器**:
  - 精选诗句
  - 诗词标题
  - 诗人信息
  - 诗词朝代
  - 完整诗词
  - 诗词译文

### 🌤️ 每日天气
- **数据源**: 和风天气 (官方 JWT 认证)
- **功能**: 3天精准天气预报
- **特色**: 使用 EdDSA 算法安全认证
- **传感器**:
  - 今日天气详情
  - 温度、湿度、风力
  - 降水量、气压
  - 紫外线指数
  - 未来两天预报

### ⛽ 每日油价
- **数据源**: 汽油价格网
- **功能**: 全国各省市实时油价
- **传感器**:
  - 92号/95号/98号汽油价格
  - 0号柴油价格
  - 省份信息
  - 调价窗口期
  - 油价走势预测

### 📜 每日历史
- **数据源**: 今天历史网
- **功能**: 了解历史上的今天
- **传感器**:
  - 历史事件内容
  - 事件发生年份
  - 历史时期分类
  - 事件详情列表

## 🔧 安装指南

### 通过 HACS 安装（推荐）
1. 打开 HACS
2. 点击「集成」
3. 点击右下角「+ 浏览并下载仓库」
4. 搜索「万象盒子」或「Myraid Box」
5. 点击「下载」
6. 重启 Home Assistant

### 手动安装
1. 下载最新版本
2. 将 `custom_components/myraid_box` 文件夹复制到您的 Home Assistant 配置目录
3. 重启 Home Assistant

## ⚙️ 配置说明

### 初始配置
1. 进入 Home Assistant 「配置」→「设备与服务」
2. 点击「+ 添加集成」
3. 搜索「万象盒子」
4. 选择要启用的服务
5. 按步骤配置每个服务

### 服务配置详情

#### 每日一言
- **更新间隔**: 10分钟（默认）
- **分类选择**: 动画、漫画、游戏、文学、原创、网络、影视、诗词、哲学、随机

#### 每日诗词  
- **更新间隔**: 10分钟（默认）
- **API**: 自动 Token 管理，无需配置

#### 每日天气 ⭐
- **更新间隔**: 30分钟（默认）
- **认证方式**: JWT + EdDSA 私钥
- **配置要求**:
  1. 注册和风天气开发者账号：[https://dev.qweather.com/](https://dev.qweather.com/)
  2. 创建项目获取项目ID、密钥ID和EdDSA私钥
  3. 私钥字段已加密显示，确保安全输入

#### 每日油价
- **更新间隔**: 360分钟（默认）
- **支持省份**: 全国31个省市自治区

#### 每日历史
- **更新间隔**: 10分钟（默认）

## 🔒 安全特性

- **密码字段加密**: 所有敏感信息（如私钥）在配置界面中均显示为密码输入框
- **Token 自动管理**: 诗词服务自动处理 API Token 的获取和刷新
- **JWT 认证**: 天气服务使用行业标准的 JWT 认证
- **数据本地缓存**: 减少不必要的 API 调用

## 📊 实体命名规范

所有传感器实体按照以下格式命名：

## 🏷️ 版本管理与发布流程

`manifest.json` 是版本号、应用名称、domain 的**唯一权威来源**。每次发版只需：

1. 修改 `custom_components/myraid_box/manifest.json` 中的 `version` 字段
2. 同步更新 README 顶部的 version badge（不改 CI 会失败提示）
3. 在 README「更新日志」顶部新增 `### v{version}` 章节，写本次更新内容
4. push main 或手动触发 release workflow → 自动生成 tag / zip / 发布说明

CI 会做两件事：
- 校验 README badge 版本号 == manifest 版本号（不一致则 CI 失败并提示同步）
- 从 README「更新日志」章节按版本号提取 changelog，注入 GitHub Release 的 body

## 更新日志

### v2.1.0
- 🔴 **安全修复**：`MyraidBoxAPIView.requires_auth` 由 `False` 改为 `True`（原来会向任意 HTTP 客户端吐出 token / 私钥）
- ✨ **HA 现代范式**：`ConfigEntry.runtime_data` 泛型替代 `hass.data[DOMAIN]`，最低 HA 版本升 2024.6+
- ✨ **性能优化**：改用 `async_get_clientsession(hass)` 复用全局 aiohttp session（消除每 sensor 一个 session 对象的浪费）
- ✨ **Service 单例复用**：`ServiceCoordinator` 持有唯一 service 实例，sensor 从 coordinator 拿（60 个 sensor = 60 个 service 对象 → 6 个）
- ✨ **油价解析修复**：重写 `services/oil.py` 的调价信息解析，修复 tip 重复、方向词丢失、吨价丢失、countdown 计算路径问题；countdown 传感器新增「调整方向 / 调整幅度 / 吨价」三个 attribute
- 🔧 `const.py` 改为显式 `SERVICE_CLASSES` 列表，去掉 `dir(module) + getattr` 运行时扫描
- 🔧 `hacs.json` 精简，删除冗余的 `name` / `homeassistant` 字段（HACS 官方支持从 manifest 自动 fallback）
- 🔧 `manifest.json` 移除 `aiohttp>=3.8.0`（HA 自带，声明会冲突），补充 `minimum_ha_version` / `loggers` / `translations`
- 🔧 `release.yml` 全部从 manifest 派生元数据（tag / zip / 目录），Release 描述自动从 README「更新日志」章节提取 changelog 注入
- 🔧 `config_flow.py` 清理冗余：mixin `__init__` 同步调 `discover_services()`、简化 `_process_password_fields`
- 🔧 删除死代码 `_last_successful_data`（`result != ...` 因 update_time 每次都变，实际从没命中过）
- 🔧 删除 `BaseService` 自建的 aiohttp session 相关代码（`_ensure_session` / `async_unload` / `_session`）

## 许可证

MIT License

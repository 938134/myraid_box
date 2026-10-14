[file name]: README.md
[file content begin]
# 万象盒子 (Myraid Box) - 智能生活数据聚合平台

![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)
![Version](https://img.shields.io/badge/version-3.4.0-blue.svg)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.8%2B-orange.svg)
![CI](https://github.com/938134/myraid_box/actions/workflows/ci.yml/badge.svg)

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

### v3.4.0
- 🐛 **修复卡片注册崩溃**：`async_add_executor_job(os.makedirs, dir, exist_ok=True)` 的 kwarg 会被 HA 转成位置参数，导致 `os.makedirs(dir, True)` → TypeError。改用 `_ensure_dir` 包装函数，避免 kwarg 传递问题
- 🐛 **修复 `async_migrate_unique_id` AttributeError**：HA < 2024.8 版本没有此方法，老版本用户首次启动即崩溃。加 `hasattr` 防御性检查——老版本跳过迁移继续运行（保留 v1 unique_id），并 log warning 提示升级 HA
- 🐛 **修复 HACS 版本声明不一致**：`hacs.json.homeassistant` 从 `2024.6` 改为 `2024.8`（与 `manifest.json.minimum_ha_version` 一致），防止 HACS 让 2024.6 用户装到依赖 2024.8 API 的版本
- 🔧 `hacs.json` 新增 `"hacs": "2.0.0"`：显式声明最低 HACS 版本
- 版本说明：3.3.0 → 3.4.0 为**修复版本**，无破坏性变更，功能完全兼容。老版本用户升级后无需任何操作即可恢复正常运行


### v3.3.0
- 🎯 **职责分离**：`SERVICE_REGISTRY` 与 `discover_services()` 从 `const.py` 迁到独立模块 **`registry.py`**，`const.py` 回归纯数据（常量 + unique_id 工具），符合"constants 只放静态数据、runtime 逻辑独立"的分层原则
- 🔧 `config_flow.py` / `coordinator.py` / `sensor.py` / `tests/*` 的 `SERVICE_REGISTRY` import 全部改为 `from .registry import ...`
- 依赖方向单向：`registry.py` → `service_base.py`（后者不反向依赖）；被扫描的 `services/*.py` 只依赖 `const`，不会反向 import `registry`，**无循环 import**
- 保留：动态发现语义不变、幂等 `discover_services(force=…)`、模块加载时立即扫描（下游 import 者开箱即用）、新增服务"丢一个文件"的开发体验
- 🧪 111 tests passed（测试用例仅调整 import 源，无行为变化）

### v3.2.0
- 🔄 **回归动态服务发现**：`SERVICE_REGISTRY` 从 v3.1 的静态字典改回**运行时扫描 `services/` 目录**（`discover_services()` 幂等，模块加载时自动执行）。新增服务**只需在 `services/` 下丢一个 `.py` 文件**，实现 `BaseService` 子类即可，**无需再改 `const.py`**
- 🔧 `const.py`：新增 `discover_services(force=False)`，`SERVICE_REGISTRY` 初始化时为空 dict；用 `Path.glob("*.py")` 扫描 + `importlib.import_module` 动态加载 + `dir(module)` 识别 `BaseService` 子类；扫描/加载失败只记 warning，不中断
- 🧪 测试从 108 → **111**：新增 3 条动态发现回归防线
  - `test_discover_services_idempotent` — 默认调用是 no-op，不重复扫描
  - `test_discover_forces_repopulate` — `force=True` 后 registry 被清空再自动填满
  - `test_new_service_requires_no_const_change` — 用 monkeypatch 伪造一个新的 services 子模块，验证 discover 真的能自动注册（真正的"丢文件就好"体验回归防线）
- 保留：`coordinator.py` / `api_view.py` 拆分（v3.1 成果）、`services/*.py` 平铺单文件结构、`test_registry_keys_match_service_id_property` 一致性回归测试
- ⚠️ 说明：v3.1 静态字典 → v3.2 动态发现是一次小型架构回退，原因是**扩展性（新增服务的成本）**在 myraid_box 的规模下比"import 期报错提前"更重要；`test_new_service_requires_no_const_change` 锁死了这个体验


### v3.1.0
- 🏗️ **文件组织重构**（P0，无行为变化）：拆分 `__init__.py`（363 → 280 行），职责更清晰
  - 新增 `coordinator.py`：`ServiceCoordinator` 从 `__init__.py` 抽出，独立模块（103 行）
  - 新增 `api_view.py`：`MyraidBoxAPIView` 从 `__init__.py` 抽出，独立模块（70 行）
  - `__init__.py` 只保留入口逻辑（`async_setup_entry` / `async_unload_entry` / 类型别名 / frontend card 注册）
- 🧹 **删除 `discover_services()`**：`SERVICE_REGISTRY` 改为**静态字典**（模块导入即完整），去掉 `SERVICE_CLASSES` / `register_service` / `init_services` / `discover_services` 四个函数（合计 -30 行）
- 🔧 `config_flow.py`：删除 `discover_services()` 调用（服务注册表现在是静态的）
- 🧪 新增回归测试 `test_registry_keys_match_service_id_property`：验证 `SERVICE_REGISTRY` 的 key 与每个 service 类的 `service_id` property 一致（避免手写静态字典时 key 写错）
- 保留：`services/*.py` 平铺单文件结构、`service_base.py` 单文件（P1 里的 `strings.json` / `models.py` / `options_flow.py` 拆分包留 v3.2+）

### v3.0.0
- 🔴 **BREAKING: unique_id 去 token 化**（大版本）：老 unique_id 基于 `md5(config_data)` 生成，包含 token / private_key / api_host 等敏感字段。用户改一次 token 就会得到新 unique_id，HA 视为"新配置"，触发仪表盘重建、历史记录断裂。v3 改为基于 `md5(sorted(selected_services))`，不含任何敏感字段
- 🔴 **BREAKING: minimum_ha_version 升 2024.8+**：需要 `async_migrate_unique_id` API
- ✨ **无缝迁移**：升级 3.0 后首次启动会自动把老 unique_id 迁到新格式，用户**无需重新走配置流程**，实体 ID 保持连续
- 🔧 `const.py` 新增 `generate_config_unique_id(selected_services)` / `is_legacy_unique_id(unique_id)` 两个纯函数，作为 config_flow 与 migration 共享的实现
- 🔧 `config_flow._async_create_entry` 调用 `generate_config_unique_id`，去掉 `hashlib` 依赖
- 🔧 `__init__.async_setup_entry` 开头新增迁移检测：识别旧格式 unique_id → 生成新 unique_id → `await entry.async_migrate_unique_id(hass, new_unique_id)`

### v2.2.0
- ✨ **翻译系统迁移**：`sensor.py` 从 `_attr_name` 硬编码中文名改为 `_attr_translation_key`，HA 从 `translations/*.json` 加载实体名，为多语言用户铺路
- ✨ **translations 补全**：`zh-Hans.json` / `en.json` 新增 `entity.sensor.myraid_box.*` 段落，覆盖 6 个服务共 35 个传感器（含 `oilprice_92` / `oilprice_95` / `oilprice_98` / `oilprice_0` 等非法字符 slug 化后的 key）
- 🏗️ **weather.py 内部重排**：`services/weather.py` 保留单文件结构，把格式化逻辑抽成模块级**纯函数**（`format_temperature` / `format_weather_text` / `format_wind_text` / `format_future_weather` / `format_today_detail` / `format_sensor_value` / `build_sensor_attributes`），`WeatherService` 类只保留"编排"（JWT / API / config schema）
- 🧪 **新增翻译回归测试**：`tests/test_translations.py`（7 项）校验 translation_key 格式合法、全局唯一、`zh-Hans.json` 与 `en.json` 都完整覆盖、所有 key 都有非空 `name` 字段、油号 `#` 被正确 slug 化
- 🔧 `sensor.py` 新增 `_generate_translation_key`：优先使用 `sensor_config` 显式指定的 `translation_key`，否则自动生成 `f"{service_id}_{slug(key)}"`，并把非法字符（`#`、`-`）替换为下划线
- 🔧 `BaseService._create_sensor_config` 已支持 `translation_key` 参数（默认 `None`，走自动生成规则），子类可显式覆盖

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

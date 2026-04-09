// ============================================================
// 万象盒子多功能卡片 - myraid_box_card.js
// 支持天气、油价、一言、诗词、版本、历史6种形态
// 自动适配深色/浅色模式
// ============================================================

// ============================================================
// 1. CSS 样式模块
// ============================================================

const Styles = {
  base: `
    :host {
      display: block;
      /* 浅色模式默认值 */
      --weather-grad: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
      --oil-grad: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 100%);
      --oil-item-grad: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%);
      --yiyan-grad: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      --poem-grad: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
      --version-grad: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
      --history-bg: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
      --history-card-bg: #ffffff;
      --history-card-hover: #f5f5f5;
      --history-text: #333333;
      --history-year: #d35400;
      --accent-gold: #ffd700;
    }
    /* 深色模式覆盖 */
    :host([data-theme="dark"]) {
      --weather-grad: linear-gradient(135deg, #2b5876 0%, #4e4376 100%);
      --oil-grad: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 100%);
      --oil-item-grad: linear-gradient(135deg, #e65c2e 0%, #d47a15 100%);
      --yiyan-grad: linear-gradient(135deg, #5a4fcf 0%, #6b3a8a 100%);
      --poem-grad: linear-gradient(135deg, #1e3a4a 0%, #2c6280 100%);
      --version-grad: linear-gradient(135deg, #0a0a1a 0%, #1e1e3a 50%, #1a1a2e 100%);
      --history-bg: linear-gradient(135deg, #0d0d1a 0%, #1a1a2e 100%);
      --history-card-bg: #2d2d3a;
      --history-card-hover: #3d3d4e;
      --history-text: #e0e0e0;
      --history-year: #f39c12;
    }
    ha-card { overflow: visible; position: relative; border-radius: 16px; transition: all 0.2s; }
    .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .header-icon { font-size: 20px; margin-right: 8px; }
    .header-title { font-weight: 600; font-size: 16px; color: var(--primary-text-color, #1a1a1a); }
    .header-buttons { display: flex; gap: 8px; position: relative; }
    .btn-icon { background: none; border: none; cursor: pointer; font-size: 16px; padding: 4px; border-radius: 4px; transition: opacity 0.2s; color: inherit; }
    .btn-icon:hover { opacity: 0.7; }
    .type-menu { position: absolute; right: 0; top: 32px; background: var(--card-background-color, white); border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); z-index: 1000; min-width: 120px; display: none; overflow: visible; }
    .type-menu.show { display: block; }
    .type-option { padding: 8px 12px; cursor: pointer; border-bottom: 1px solid var(--divider-color, #eee); transition: background 0.2s; white-space: nowrap; }
    .type-option:last-child { border-bottom: none; }
    .type-option:hover { background: var(--secondary-background-color, #f5f5f5); }
    .error-container { padding: 16px; text-align: center; color: var(--error-color, #e74c3c); }
    .retry-btn { margin-top: 12px; padding: 6px 12px; background: var(--primary-color); border: none; border-radius: 4px; color: white; cursor: pointer; }
    .loading { padding: 16px; text-align: center; }
  `,

  weather: `
    .weather-bg { background: var(--weather-grad); color: white; padding: 16px; border-radius: 16px; }
    .weather-temp { font-size: 48px; font-weight: bold; }
    .weather-stats { display: flex; justify-content: space-around; margin: 16px 0; }
    .weather-stat { text-align: center; flex: 1; font-size: 14px; }
    .forecast-container { display: flex; gap: 8px; margin-top: 8px; }
    .forecast-item { background: rgba(255,255,255,0.2); border-radius: 12px; padding: 8px; text-align: center; flex: 1; font-size: 12px; backdrop-filter: blur(4px); }
    .temp-container { text-align: center; margin: 8px 0; }
    .weather-desc { font-size: 16px; opacity: 0.9; }
    .weather-city { font-size: 14px; opacity: 0.7; }
  `,

  oil: `
    .oil-bg { background: var(--oil-grad); color: white; padding: 16px; border-radius: 16px; }
    .oil-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .oil-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 600; }
    .oil-price-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 16px 0; }
    .oil-item { text-align: center; background: var(--oil-item-grad); border-radius: 14px; padding: 10px 6px; transition: all 0.2s; box-shadow: 0 2px 12px rgba(0,0,0,0.2); }
    .oil-item:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.3); }
    .oil-item-label { font-size: 12px; opacity: 0.9; margin-bottom: 6px; font-weight: 500; color: white; }
    .oil-price { font-size: 22px; font-weight: bold; color: white; text-shadow: 0 1px 2px rgba(0,0,0,0.2); }
    .countdown-badge { background: linear-gradient(135deg, #e74c3c, #c0392b); border-radius: 20px; padding: 4px 12px; font-size: 11px; font-weight: bold; white-space: nowrap; }
    .countdown-badge.urgent { animation: pulse 1s infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
    .oil-footer { margin-top: 12px; text-align: left; }
    .oil-tip { font-size: 11px; opacity: 0.8; padding: 8px 10px; background: rgba(255,255,255,0.1); border-radius: 8px; line-height: 1.5; display: flex; align-items: center; gap: 6px; backdrop-filter: blur(4px); }
  `,

  yiyan: `
    .yiyan-bg { background: var(--yiyan-grad); padding: 20px; border-radius: 16px; min-height: 140px; display: flex; flex-direction: column; justify-content: center; }
    .yiyan-content { font-size: 15px; line-height: 1.7; font-style: normal; margin: 0 0 12px 0; color: white; font-weight: 400; text-align: left; }
    .yiyan-author { font-size: 12px; opacity: 0.8; text-align: right; margin-top: 4px; color: rgba(255,255,255,0.9); }
  `,

  poem: `
    .poem-bg { background: var(--poem-grad); padding: 16px; border-radius: 16px; color: white; }
    .poem-title { font-size: 20px; font-weight: bold; text-align: center; margin-bottom: 6px; color: #ffd700; letter-spacing: 2px; }
    .poem-author { font-size: 13px; opacity: 0.8; text-align: center; margin-bottom: 16px; color: rgba(255,255,255,0.8); }
    .poem-content { font-family: "KaiTi", "华文楷书", serif; line-height: 2; text-align: center; font-size: 16px; color: rgba(255,255,255,0.95); }
    .poem-line { margin: 6px 0; }
    .poem-translate { margin-top: 16px; padding-top: 12px; border-top: 1px dashed rgba(255,255,255,0.2); }
    .poem-translate summary { cursor: pointer; font-size: 12px; opacity: 0.8; color: #ffd700; }
    .poem-translate-content { font-size: 13px; margin-top: 8px; padding: 10px; background: rgba(255,255,255,0.1); border-radius: 8px; line-height: 1.6; color: rgba(255,255,255,0.9); }
  `,

  version: `
    .version-bg { background: var(--version-grad); color: white; padding: 16px; border-radius: 16px; text-align: center; }
    .version-image { display: flex; justify-content: center; margin-bottom: 12px; }
    .version-image img { max-width: 80px; max-height: 80px; width: auto; height: auto; object-fit: contain; border-radius: 12px; background: rgba(255,255,255,0.1); padding: 8px; }
    .version-image .no-image { width: 70px; height: 70px; background: rgba(255,255,255,0.1); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 36px; }
    .version-name { font-size: 18px; font-weight: bold; margin-bottom: 4px; color: white; }
    .version-number { font-size: 28px; font-weight: bold; color: #00d4aa; margin: 8px 0; letter-spacing: 1px; text-shadow: 0 0 10px rgba(0,212,170,0.3); }
    .version-link { display: inline-flex; align-items: center; justify-content: center; gap: 6px; width: 100%; margin-top: 12px; padding: 8px 12px; background: rgba(0,212,170,0.15); border-radius: 10px; text-decoration: none; color: #00d4aa; font-size: 13px; font-weight: 500; transition: all 0.2s; border: 1px solid rgba(0,212,170,0.3); }
    .version-link:hover { background: rgba(0,212,170,0.25); transform: translateY(-1px); }
  `,

  history: `
    .history-bg { background: var(--history-bg); padding: 16px; border-radius: 16px; }
    .history-date { font-size: 14px; color: var(--accent-gold); margin-bottom: 14px; text-align: center; letter-spacing: 1px; font-weight: 500; }
    .history-event-card { background: var(--history-card-bg); border-radius: 12px; padding: 10px 14px; margin-bottom: 6px; transition: all 0.2s; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
    .history-event-card:hover { background: var(--history-card-hover); transform: translateX(2px); box-shadow: 0 2px 6px rgba(0,0,0,0.12); }
    .history-event-year { font-size: 13px; font-weight: bold; color: var(--history-year); margin-bottom: 4px; }
    .history-event-num { display: inline-block; margin-right: 8px; color: var(--history-year); }
    .history-event-desc { font-size: 12px; line-height: 1.5; color: var(--history-text); }
    .history-count { font-size: 11px; color: rgba(255,255,255,0.5); text-align: center; margin-top: 10px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.08); }
    .history-more { margin-top: 8px; text-align: center; }
    .history-more-btn { background: transparent; border: 1px solid var(--accent-gold); border-radius: 20px; padding: 5px 14px; color: var(--accent-gold); cursor: pointer; font-size: 11px; transition: all 0.2s; }
    .history-more-btn:hover { background: rgba(255,215,0,0.1); transform: translateY(-1px); }
    .history-event-list { margin-top: 8px; max-height: 320px; overflow-y: auto; }
    .history-event-item { padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.1); display: flex; align-items: flex-start; gap: 8px; }
    .history-event-item-num { color: var(--history-year); font-weight: bold; min-width: 28px; font-size: 12px; }
    .history-event-item-year { color: var(--history-year); font-weight: bold; min-width: 55px; font-size: 12px; }
    .history-event-item-desc { flex: 1; line-height: 1.4; font-size: 12px; color: var(--history-text); }
    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-track { background: rgba(255,255,255,0.1); border-radius: 4px; }
    ::-webkit-scrollbar-thumb { background: var(--accent-gold); border-radius: 4px; }
  `
};

// ============================================================
// 2. 卡片类型配置
// ============================================================

const CardTypes = {
  weather: { name: '每日天气', icon: '🌤️', defaultTitle: '每日天气' },
  oil: { name: '每日油价', icon: '⛽', defaultTitle: '每日油价' },
  yiyan: { name: '每日一言', icon: '💬', defaultTitle: '每日一言' },
  poem: { name: '每日诗词', icon: '📜', defaultTitle: '每日诗词' },
  version: { name: 'iStoreOS版本', icon: '🔄', defaultTitle: 'iStoreOS版本' },
  history: { name: '每日历史', icon: '📅', defaultTitle: '每日历史' }
};

// ============================================================
// 3. 数据获取模块
// ============================================================

const DataFetcher = {
  async fetchAll() {
    try {
      const response = await fetch('/api/myraid_box/data');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error('API获取失败:', error);
      return null;
    }
  },

  parseWeather(data) {
    const weather = data?.weather?.data || {};
    const forecast = weather.daily_forecast || [];
    const today = forecast[0] || {};
    const tomorrow = forecast[1] || {};
    const day3 = forecast[2] || {};
    const cityInfo = weather.city_info || {};

    const parseTemp = (min, max) => {
      if (!min && !max) return '--';
      if (min === max) return `${min}°C`;
      return `${min}~${max}°C`;
    };

    const getWeatherText = (day) => {
      const dayText = day.textDay || '';
      const nightText = day.textNight || '';
      if (dayText === nightText) return dayText || '--';
      if (dayText && nightText) return `${dayText}转${nightText}`;
      return dayText || nightText || '--';
    };

    const getWind = (day) => {
      const dir = day.windDirDay || '';
      const scale = day.windScaleDay || '';
      if (dir && scale) return `${dir}${scale}级`;
      if (dir) return dir;
      if (scale) return `${scale}级`;
      return '--';
    };

    return {
      city: cityInfo.name || '未知',
      today: getWeatherText(today),
      temp: parseTemp(today.tempMin, today.tempMax),
      humidity: today.humidity || '--',
      wind: getWind(today),
      uv: today.uvIndex ? `${today.uvIndex}级` : '--',
      tomorrow: getWeatherText(tomorrow),
      day3: getWeatherText(day3)
    };
  },

  parseOil(data) {
    const d = data?.oilprice?.data || {};
    return {
      province: d.province || '浙江',
      price92: d['92#'] ? parseFloat(d['92#']) : null,
      price95: d['95#'] ? parseFloat(d['95#']) : null,
      price98: d['98#'] ? parseFloat(d['98#']) : null,
      price0: d['0#'] ? parseFloat(d['0#']) : null,
      tip: d.tip || '暂无调价信息',
      countdown: d.countdown
    };
  },

  parseYiyan(data) {
    const d = data?.hitokoto?.data || {};
    return {
      content: d.content || '暂无内容',
      author: d.author || '佚名',
      source: d.source || '未知来源'
    };
  },

  parsePoem(data) {
    const d = data?.poetry?.data || {};
    return {
      title: d.title || '未知',
      author: d.author || '佚名',
      dynasty: d.dynasty || '未知',
      content: d.content || '暂无',
      fullContent: d.full_content || '',
      translate: d.translate || ''
    };
  },

  parseVersion(data) {
    const d = data?.istoreos?.data || {};
    return {
      device: d.device_name || '未知设备',
      current: d.latest_version || '未知',
      deviceCover: d.device_cover || ''
    };
  },

  parseHistory(data) {
    const d = data?.history?.data || {};
    let events = [];
    if (d.events && Array.isArray(d.events)) {
      events = d.events;
    } else if (d.events && typeof d.events === 'object') {
      events = Object.entries(d.events)
        .filter(([k]) => !['更新时间', '数据状态', '错误信息', '事件总数'].includes(k))
        .map(([year, event]) => ({
          year: year,
          event: typeof event === 'string' ? event : (event.event || event.desc)
        }));
    }
    return {
      today: d.today || '',
      count: d.count || events.length,
      event: d.event || (events[0]?.event || '暂无事件'),
      events: events
    };
  }
};

// ============================================================
// 4. 主卡片类
// ============================================================

class MyraidBoxCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement('myraid-box-card-editor');
  }

  static getStubConfig() {
    return {
      card_type: 'weather',
      show_refresh: true,
      auto_rotate: false,
      rotate_interval: 10,
      enabled_types: ['weather', 'oil', 'yiyan', 'poem', 'version', 'history']
    };
  }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._currentType = null;
    this._rotateInterval = null;
    this._data = {};
    this.config = {};
    this._showFullHistory = false;
  }

  setConfig(config) {
    this.config = { ...MyraidBoxCard.getStubConfig(), ...config };
    this._currentType = this.config.card_type;
    this._applyStyles();
    this._setupAutoRotate();
    this._loadData();
  }

  set hass(hass) {
    this._hass = hass;
    this._updateTheme();
    this._loadData();
  }

  _updateTheme() {
    const isDark = this._hass?.themes?.darkMode || 
                   window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (isDark) {
      this.setAttribute('data-theme', 'dark');
    } else {
      this.setAttribute('data-theme', 'light');
    }
  }

  getCardSize() {
    const sizes = { weather: 4, oil: 3, yiyan: 2, poem: 4, version: 3, history: 3 };
    return sizes[this._currentType] || 3;
  }

  _applyStyles() {
    if (this._currentStyle) this._currentStyle.remove();
    this._currentStyle = document.createElement('style');
    this._currentStyle.textContent = Styles.base + Styles[this._currentType];
    this.shadowRoot.appendChild(this._currentStyle);
  }

  _setupAutoRotate() {
    if (this._rotateInterval) clearInterval(this._rotateInterval);
    if (this.config.auto_rotate && this.config.enabled_types.length > 1) {
      this._rotateInterval = setInterval(() => {
        const currentIndex = this.config.enabled_types.indexOf(this._currentType);
        const nextIndex = (currentIndex + 1) % this.config.enabled_types.length;
        this._currentType = this.config.enabled_types[nextIndex];
        this._applyStyles();
        this._render();
      }, this.config.rotate_interval * 1000);
    }
  }

  async _loadData() {
    const raw = await DataFetcher.fetchAll();
    if (raw) {
      this._data = {
        weather: DataFetcher.parseWeather(raw),
        oil: DataFetcher.parseOil(raw),
        yiyan: DataFetcher.parseYiyan(raw),
        poem: DataFetcher.parsePoem(raw),
        version: DataFetcher.parseVersion(raw),
        history: DataFetcher.parseHistory(raw)
      };
    }
    this._render();
  }

  _render() {
    if (!this._data.weather) {
      this.shadowRoot.innerHTML = `<ha-card><div class="loading">加载中...</div></ha-card>`;
      this._applyStyles();
      return;
    }

    const cardData = this._data[this._currentType];
    const config = this.config;
    const showRefresh = config.show_refresh;
    const icon = CardTypes[this._currentType]?.icon || '📋';
    const title = CardTypes[this._currentType]?.defaultTitle || '';

    let contentHtml = '';

    switch (this._currentType) {
      case 'weather':
        contentHtml = this._renderWeather(cardData, showRefresh, icon, title);
        break;
      case 'oil':
        contentHtml = this._renderOil(cardData, showRefresh, icon, title);
        break;
      case 'yiyan':
        contentHtml = this._renderYiyan(cardData, showRefresh, icon, title);
        break;
      case 'poem':
        contentHtml = this._renderPoem(cardData, showRefresh, icon, title);
        break;
      case 'version':
        contentHtml = this._renderVersion(cardData, showRefresh, icon, title);
        break;
      case 'history':
        contentHtml = this._renderHistory(cardData, showRefresh, icon, title);
        break;
      default:
        contentHtml = `<div class="error-container">未知卡片类型</div>`;
    }

    this.shadowRoot.innerHTML = `<ha-card style="overflow: visible;">${contentHtml}</ha-card>`;
    this._applyStyles();
    this._attachEvents();
  }

  _getHeader(showRefresh, title, icon) {
    const config = this.config;
    return `
      <div class="card-header">
        <div style="display: flex; align-items: center;">
          <span class="header-icon">${icon}</span>
          <span class="header-title">${title}</span>
        </div>
        <div class="header-buttons">
          ${showRefresh ? '<button class="btn-icon refresh-btn">🔄</button>' : ''}
          <button class="btn-icon type-switch-btn">▼</button>
        </div>
      </div>
      <div class="type-menu">
        ${config.enabled_types.map(type => `
          <div class="type-option" data-type="${type}">${CardTypes[type]?.icon || '📋'} ${CardTypes[type]?.name || type}</div>
        `).join('')}
      </div>
    `;
  }

  _renderWeather(data, showRefresh, icon, title) {
    const tempMatch = String(data.temp).match(/(\d+)/);
    const tempValue = tempMatch ? tempMatch[0] : '--';
    return `
      <div class="weather-bg">
        ${this._getHeader(showRefresh, title, icon)}
        <div class="temp-container">
          <div class="weather-temp">${tempValue}°C</div>
          <div class="weather-desc">${data.today}</div>
          <div class="weather-city">${data.city}</div>
        </div>
        <div class="weather-stats">
          <div class="weather-stat">💧 ${data.humidity}%</div>
          <div class="weather-stat">💨 ${data.wind}</div>
          <div class="weather-stat">☀️ ${data.uv}</div>
        </div>
        <div class="forecast-container">
          <div class="forecast-item">明天<br>${String(data.tomorrow).split('，')[0]}</div>
          <div class="forecast-item">后天<br>${String(data.day3).split('，')[0]}</div>
        </div>
      </div>
    `;
  }

  _renderOil(data, showRefresh, icon, title) {
    const formatPrice = (p) => (p !== null && !isNaN(p)) ? p.toFixed(2) : '--';
    const countdown = data.countdown !== null && data.countdown !== '暂无数据' ? parseInt(data.countdown) : null;
    const countdownHtml = (countdown && countdown > 0 && countdown < 365)
      ? `<div class="countdown-badge ${countdown <= 3 ? 'urgent' : ''}">⏰ 倒计时 ${countdown}天</div>`
      : '';

    const oilTitle = `${data.province}${title}`;

    return `
      <div class="oil-bg">
        <div class="oil-header">
          <div class="oil-title">
            <span>${icon}</span>
            <span>${oilTitle}</span>
          </div>
          <div style="display: flex; gap: 8px; align-items: center;">
            ${countdownHtml}
            ${showRefresh ? '<button class="btn-icon refresh-btn">🔄</button>' : ''}
            <button class="btn-icon type-switch-btn">▼</button>
          </div>
        </div>
        <div class="type-menu">
          ${this.config.enabled_types.map(type => `
            <div class="type-option" data-type="${type}">${CardTypes[type]?.icon || '📋'} ${CardTypes[type]?.name || type}</div>
          `).join('')}
        </div>
        <div class="oil-price-grid">
          <div class="oil-item"><div class="oil-item-label">92#</div><div class="oil-price">${formatPrice(data.price92)}</div></div>
          <div class="oil-item"><div class="oil-item-label">95#</div><div class="oil-price">${formatPrice(data.price95)}</div></div>
          <div class="oil-item"><div class="oil-item-label">98#</div><div class="oil-price">${formatPrice(data.price98)}</div></div>
          <div class="oil-item"><div class="oil-item-label">0#</div><div class="oil-price">${formatPrice(data.price0)}</div></div>
        </div>
        <div class="oil-footer">
          <div class="oil-tip">📢 ${data.tip}</div>
        </div>
      </div>
    `;
  }

  _renderYiyan(data, showRefresh, icon, title) {
    let content = data.content;
    if (content.startsWith('“') && content.endsWith('”')) {
      content = content.slice(1, -1);
    }
    if (content.startsWith('"') && content.endsWith('"')) {
      content = content.slice(1, -1);
    }

    return `
      <div class="yiyan-bg">
        ${this._getHeader(showRefresh, title, icon)}
        <div class="yiyan-content">${content}</div>
        <div class="yiyan-author">—— ${data.author}${data.source !== '未知来源' ? `《${data.source}》` : ''}</div>
      </div>
    `;
  }

  _renderPoem(data, showRefresh, icon, title) {
    const lines = String(data.fullContent || data.content).split('\n').filter(l => l.trim());
    const hasTranslate = data.translate && data.translate !== '无译文' && data.translate !== '加载中...';

    return `
      <div class="poem-bg">
        ${this._getHeader(showRefresh, title, icon)}
        <div class="poem-title">${data.title}</div>
        <div class="poem-author">${data.dynasty} · ${data.author}</div>
        <div class="poem-content">
          ${lines.slice(0, 12).map(l => `<div class="poem-line">${l}</div>`).join('')}
          ${lines.length > 12 ? `<div class="poem-line">......</div>` : ''}
        </div>
        ${hasTranslate ? `
          <details class="poem-translate">
            <summary>📖 查看译文</summary>
            <div class="poem-translate-content">${data.translate}</div>
          </details>
        ` : ''}
      </div>
    `;
  }

  _renderVersion(data, showRefresh, icon, title) {
    const deviceImage = data.deviceCover;
    const downloadUrl = 'https://fw.koolcenter.com/iStoreOS/';

    return `
      <div class="version-bg">
        ${this._getHeader(showRefresh, title, icon)}
        <div class="version-image">
          ${deviceImage ?
            `<img src="${deviceImage}" alt="${data.device}" onerror="this.style.display='none';this.parentElement.querySelector('.no-image').style.display='flex'">` :
            ''}
          <div class="no-image" style="${deviceImage ? 'display:none' : 'display:flex'}">🖥️</div>
        </div>
        <div class="version-name">${data.device}</div>
        <div class="version-number">${data.current}</div>
        <a href="${downloadUrl}" target="_blank" rel="noopener noreferrer" class="version-link">
          🔗 前往下载中心
        </a>
      </div>
    `;
  }

  _renderHistory(data, showRefresh, icon, title) {
    let events = [];

    if (data.events && Array.isArray(data.events)) {
      events = data.events.map(item => ({
        year: item.year || '未知',
        desc: item.event || item.desc || String(item)
      }));
    }

    const defaultShowCount = 3;
    const displayEvents = this._showFullHistory ? events : events.slice(0, defaultShowCount);
    const hasMore = events.length > defaultShowCount;
    const eventCount = data.count || events.length;

    if (events.length === 0) {
      return `
        <div class="history-bg">
          ${this._getHeader(showRefresh, title, icon)}
          <div class="history-date">📅 ${data.today || '--'}</div>
          <div class="history-event-card">
            <div class="history-event-desc">暂无历史事件</div>
          </div>
          <div class="history-count">📋 共 0 件历史大事</div>
        </div>
      `;
    }

    return `
      <div class="history-bg">
        ${this._getHeader(showRefresh, title, icon)}
        <div class="history-date">📅 ${data.today || '--'}</div>
        ${this._showFullHistory ? `
          <div class="history-event-list">
            ${displayEvents.map((event, idx) => `
              <div class="history-event-item">
                <span class="history-event-item-num">${idx + 1}.</span>
                <span class="history-event-item-year">${event.year}</span>
                <span class="history-event-item-desc">${event.desc}</span>
              </div>
            `).join('')}
          </div>
        ` : `
          ${displayEvents.map((event, idx) => `
            <div class="history-event-card">
              <div class="history-event-year">
                <span class="history-event-num">${idx + 1}.</span>
                ${event.year}
              </div>
              <div class="history-event-desc">${event.desc}</div>
            </div>
          `).join('')}
        `}
        <div class="history-count">📋 共 ${eventCount} 件历史大事</div>
        ${hasMore ? `
          <div class="history-more">
            <button class="history-more-btn">${this._showFullHistory ? '收起 ▲' : '展开更多 ▼'}</button>
          </div>
        ` : ''}
      </div>
    `;
  }

  _attachEvents() {
    const refreshBtn = this.shadowRoot?.querySelector('.refresh-btn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this._refresh();
      });
    }

    const switchBtn = this.shadowRoot?.querySelector('.type-switch-btn');
    const menu = this.shadowRoot?.querySelector('.type-menu');

    if (switchBtn && menu) {
      const newSwitchBtn = switchBtn.cloneNode(true);
      switchBtn.parentNode.replaceChild(newSwitchBtn, switchBtn);

      newSwitchBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = menu.classList.contains('show');
        document.querySelectorAll('.type-menu').forEach(m => m.classList.remove('show'));
        if (!isOpen) menu.classList.add('show');
      });

      const options = menu.querySelectorAll('.type-option');
      options.forEach(opt => {
        const newOpt = opt.cloneNode(true);
        opt.parentNode.replaceChild(newOpt, opt);

        newOpt.addEventListener('click', (e) => {
          e.stopPropagation();
          const type = newOpt.dataset.type;
          if (type && type !== this._currentType) {
            this._currentType = type;
            this._applyStyles();
            menu.classList.remove('show');
            this._render();
          } else {
            menu.classList.remove('show');
          }
        });
      });

      document.addEventListener('click', (e) => {
        if (!this.shadowRoot?.contains(e.target)) {
          if (menu) menu.classList.remove('show');
        }
      });
    }

    const moreBtn = this.shadowRoot?.querySelector('.history-more-btn');
    if (moreBtn) {
      moreBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this._showFullHistory = !this._showFullHistory;
        this._render();
      });
    }
  }

  async _refresh() {
    const btn = this.shadowRoot?.querySelector('.refresh-btn');
    if (btn) btn.style.opacity = '0.5';
    await this._loadData();
    if (btn) btn.style.opacity = '';
  }
}

// ============================================================
// 5. 可视化编辑器
// ============================================================

class MyraidBoxCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = {};
  }

  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        .editor { padding: 8px 0; display: flex; flex-direction: column; gap: 16px; }
        .section { border: 1px solid var(--divider-color, #e0e0e0); border-radius: 12px; overflow: hidden; }
        .section-title { display: flex; align-items: center; gap: 8px; padding: 10px 14px; background: var(--secondary-background-color, #f5f5f5); font-weight: 600; font-size: 13px; border-bottom: 1px solid var(--divider-color, #e0e0e0); }
        .section-content { padding: 12px 14px; display: flex; flex-direction: column; gap: 12px; }
        .field-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
        .field label { font-size: 13px; font-weight: 500; color: var(--primary-text-color); }
        .field-description { font-size: 11px; color: var(--secondary-text-color); }
        .type-selector { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
        .type-option-card { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 8px 4px; background: var(--card-background-color); border: 2px solid var(--divider-color, #e0e0e0); border-radius: 10px; cursor: pointer; transition: all 0.2s; }
        .type-option-card:hover { border-color: var(--primary-color); transform: translateY(-1px); }
        .type-option-card.selected { border-color: var(--primary-color); background: rgba(var(--primary-rgb), 0.05); }
        .type-option-icon { font-size: 22px; }
        .type-option-name { font-size: 11px; font-weight: 500; }
        .switch { position: relative; display: inline-block; width: 40px; height: 22px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: 0.3s; border-radius: 22px; }
        .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 3px; bottom: 3px; background-color: white; transition: 0.3s; border-radius: 50%; }
        input:checked + .slider { background-color: var(--primary-color, #03a9f4); }
        input:checked + .slider:before { transform: translateX(18px); }
        input[type="number"] { width: 70px; padding: 6px 8px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); font-size: 13px; text-align: center; }
        .tag-group { display: flex; flex-wrap: wrap; gap: 6px; }
        .tag { display: flex; align-items: center; gap: 4px; padding: 5px 10px; background: var(--secondary-background-color); border-radius: 20px; cursor: pointer; font-size: 12px; transition: all 0.2s; }
        .tag.selected { background: var(--primary-color); color: white; }
        .tag:hover { opacity: 0.8; }
      </style>

      <div class="editor">
        <div class="section">
          <div class="section-title"><span>📋</span> 卡片形态</div>
          <div class="section-content">
            <div class="type-selector">
              ${Object.entries(CardTypes).map(([key, val]) => `
                <div class="type-option-card ${this._config.card_type === key ? 'selected' : ''}" data-type="${key}">
                  <div class="type-option-icon">${val.icon}</div>
                  <div class="type-option-name">${val.name}</div>
                </div>
              `).join('')}
            </div>
          </div>
        </div>

        <div class="section">
          <div class="section-title"><span>⚙️</span> 交互设置</div>
          <div class="section-content">
            <div class="field-row">
              <label>🔄 显示刷新按钮</label>
              <label class="switch">
                <input type="checkbox" id="show_refresh" ${this._config.show_refresh !== false ? 'checked' : ''}>
                <span class="slider"></span>
              </label>
            </div>
            <div class="field-row">
              <label>🎠 自动轮播</label>
              <label class="switch">
                <input type="checkbox" id="auto_rotate" ${this._config.auto_rotate ? 'checked' : ''}>
                <span class="slider"></span>
              </label>
            </div>
            <div class="field-row" id="rotate_interval_field" style="${this._config.auto_rotate ? '' : 'display: none;'}">
              <label>⏱️ 轮播间隔（秒）</label>
              <input type="number" id="rotate_interval" min="3" max="60" value="${this._config.rotate_interval || 10}">
            </div>
          </div>
        </div>

        <div class="section">
          <div class="section-title"><span>✨</span> 启用的形态</div>
          <div class="section-content">
            <div class="tag-group" id="enabled_types">
              ${Object.entries(CardTypes).map(([key, val]) => `
                <div class="tag ${this._config.enabled_types?.includes(key) !== false ? 'selected' : ''}" data-type="${key}">
                  ${val.icon} ${val.name}
                </div>
              `).join('')}
            </div>
            <div class="field-description">自动轮播时，只有勾选的形态会被切换</div>
          </div>
        </div>
      </div>
    `;

    this._bindEvents();
  }

  _bindEvents() {
    this.shadowRoot.querySelectorAll('.type-option-card').forEach(el => {
      el.addEventListener('click', () => {
        const type = el.dataset.type;
        if (type) {
          this._config.card_type = type;
          this._render();
          this._fireEvent();
        }
      });
    });

    this.shadowRoot.getElementById('show_refresh')?.addEventListener('change', (e) => {
      this._config.show_refresh = e.target.checked;
      this._fireEvent();
    });

    const autoRotate = this.shadowRoot.getElementById('auto_rotate');
    autoRotate?.addEventListener('change', (e) => {
      this._config.auto_rotate = e.target.checked;
      const intervalField = this.shadowRoot.getElementById('rotate_interval_field');
      if (intervalField) intervalField.style.display = e.target.checked ? 'flex' : 'none';
      this._fireEvent();
    });

    this.shadowRoot.getElementById('rotate_interval')?.addEventListener('change', (e) => {
      this._config.rotate_interval = parseInt(e.target.value) || 10;
      this._fireEvent();
    });

    this.shadowRoot.querySelectorAll('.tag').forEach(el => {
      el.addEventListener('click', () => {
        const type = el.dataset.type;
        if (!this._config.enabled_types) {
          this._config.enabled_types = Object.keys(CardTypes);
        }
        if (this._config.enabled_types.includes(type)) {
          this._config.enabled_types = this._config.enabled_types.filter(t => t !== type);
          el.classList.remove('selected');
        } else {
          this._config.enabled_types.push(type);
          el.classList.add('selected');
        }
        if (this._config.enabled_types.length === 0) {
          this._config.enabled_types = ['weather'];
          const weatherTag = this.shadowRoot.querySelector('.tag[data-type="weather"]');
          if (weatherTag) weatherTag.classList.add('selected');
        }
        this._fireEvent();
      });
    });
  }

  _fireEvent() {
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config: this._config },
      bubbles: true,
      composed: true
    }));
  }
}

// ============================================================
// 6. 注册组件
// ============================================================

customElements.define('myraid-box-card', MyraidBoxCard);
customElements.define('myraid-box-card-editor', MyraidBoxCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'myraid-box-card',
  name: '万象盒子多功能卡片',
  description: '支持天气、油价、一言、诗词、版本、历史6种形态切换',
  preview: true
});

const VERSION = (() => {
  const scripts = document.querySelectorAll('script');
  for (const s of scripts) {
    if (s.src?.includes('myraid_box_card')) {
      const match = s.src.match(/ver=([a-f0-9]+)/);
      if (match) return match[1];
    }
  }
  return Date.now().toString(36);
})();
console.log(`🎴 万象盒子卡片 v${VERSION} 已加载`);
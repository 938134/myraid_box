// ============================================================
// 万象盒子多功能卡片 - myraid_box_card.js
// 支持天气、油价、一言、诗词、版本、历史6种形态
// 深色模式高对比配色 | 历史卡片一行显示自动换行
// ============================================================

// ============================================================
// 1. CSS 样式模块
// ============================================================

const Styles = {
  base: `
    :host { display: block; }
    ha-card { overflow: visible; position: relative; border-radius: var(--ha-card-border-radius, 16px); transition: all 0.2s; border: 1px solid rgba(255,255,255,0.15); box-shadow: inset 0 1px 0 rgba(255,255,255,0.08); }
    .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; position: relative; }
    .header-icon { font-size: 20px; margin-right: 8px; }
    .header-title { font-weight: 600; font-size: 16px; color: #e0e0e0; }
    .header-buttons { display: flex; gap: 8px; position: relative; }
    .btn-icon { background: none; border: none; cursor: pointer; font-size: 16px; padding: 4px; border-radius: 4px; transition: opacity 0.2s; color: #e0e0e0; }
    .btn-icon:hover { opacity: 0.7; background: rgba(255,255,255,0.1); }
    .error-container { padding: 16px; text-align: center; color: #e74c3c; }
    .retry-btn { margin-top: 12px; padding: 6px 12px; background: var(--primary-color); border: none; border-radius: 4px; color: white; cursor: pointer; }
    .loading { padding: 16px; text-align: center; color: #aaa; }
    /* 菜单样式 */
    .type-menu { position: fixed; background: #1a1a2e; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); z-index: 10000; min-width: 120px; display: none; overflow: hidden; border: 1px solid rgba(255,255,255,0.1); }
    .type-menu.show { display: block; }
    .type-option { padding: 8px 12px; cursor: pointer; border-bottom: 1px solid rgba(255,255,255,0.1); transition: background 0.2s; white-space: nowrap; color: #e0e0e0; }
    .type-option:last-child { border-bottom: none; }
    .type-option:hover { background: rgba(255,255,255,0.1); }
  `,

  weather: `
    .weather-bg { background: linear-gradient(135deg, #2a4a7a 0%, #3a5a8a 100%); padding: 16px; border-radius: 16px; }
    .weather-temp { font-size: 48px; font-weight: bold; color: white; }
    .weather-stats { display: flex; justify-content: space-around; margin: 16px 0; }
    .weather-stat { text-align: center; flex: 1; font-size: 14px; color: white; }
    .forecast-container { display: flex; gap: 8px; margin-top: 8px; }
    .forecast-item { background: rgba(255,255,255,0.15); border-radius: 12px; padding: 8px; text-align: center; flex: 1; font-size: 12px; color: white; backdrop-filter: blur(4px); border: 1px solid rgba(255,255,255,0.1); }
    .temp-container { text-align: center; margin: 8px 0; }
    .weather-desc { font-size: 16px; opacity: 0.9; color: white; }
    .weather-city { font-size: 14px; opacity: 0.7; color: white; }
  `,

  oil: `
    .oil-bg { background: linear-gradient(135deg, #4a3a2a 0%, #5a4a3a 100%); padding: 16px; border-radius: 16px; }
    .oil-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .oil-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 600; color: #e0e0e0; }
    .oil-price-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin: 16px 0; }
    .oil-item { text-align: center; background: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%); border-radius: 12px; padding: 4px 4px; transition: all 0.2s; box-shadow: 0 2px 8px rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.2); }
    .oil-item:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
    .oil-item-label { font-size: 10px; opacity: 0.9; margin-bottom: 2px; font-weight: 500; color: white; }
    .oil-price { font-size: 16px; font-weight: bold; color: white; text-shadow: 0 1px 2px rgba(0,0,0,0.2); }
    .countdown-badge { background: linear-gradient(135deg, #e74c3c, #c0392b); border-radius: 20px; padding: 4px 12px; font-size: 11px; font-weight: bold; white-space: nowrap; color: white; }
    .countdown-badge.urgent { animation: pulse 1s infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
    .oil-footer { margin-top: 12px; text-align: left; }
    .oil-tip { font-size: 13px; padding: 8px 12px; background: rgba(0,0,0,0.3); border-radius: 10px; line-height: 1.5; display: flex; align-items: center; gap: 8px; font-weight: 500; color: #e0e0e0; }
    .oil-tip-icon { font-size: 14px; }
  `,

  yiyan: `
    .yiyan-bg { background: linear-gradient(135deg, #3a3a6a 0%, #4a4a7a 100%); padding: 16px; border-radius: 16px; min-height: 140px; display: flex; flex-direction: column; justify-content: center; }
    .yiyan-content { font-size: 15px; line-height: 1.7; font-style: normal; margin: 0 0 12px 0; text-align: left; color: #e0e0e0; }
    .yiyan-author { font-size: 12px; opacity: 0.7; text-align: right; margin-top: 4px; color: #aaa; }
  `,

  poem: `
    .poem-bg { background: linear-gradient(135deg, #3a5a5a 0%, #4a6a6a 100%); padding: 16px; border-radius: 16px; }
    .poem-title { font-size: 20px; font-weight: bold; text-align: center; margin-bottom: 6px; letter-spacing: 2px; color: #e0d8c8; }
    .poem-author { font-size: 13px; opacity: 0.7; text-align: center; margin-bottom: 16px; color: #aaa; }
    .poem-content { font-family: "KaiTi", "华文楷书", serif; line-height: 2; text-align: center; font-size: 16px; color: #e0d8c8; }
    .poem-line { margin: 6px 0; }
    .poem-translate { margin-top: 16px; padding-top: 12px; border-top: 1px dashed rgba(255,255,255,0.2); }
    .poem-translate summary { cursor: pointer; font-size: 12px; opacity: 0.7; color: #aaa; }
    .poem-translate-content { font-size: 13px; margin-top: 8px; padding: 10px; background: rgba(0,0,0,0.3); border-radius: 8px; line-height: 1.6; color: #e0d8c8; }
  `,

  version: `
    .version-bg { background: linear-gradient(135deg, #2a4a6a 0%, #3a5a7a 100%); padding: 16px; border-radius: 16px; text-align: center; }
    .version-image { display: flex; justify-content: center; margin-bottom: 12px; }
    .version-image img { max-width: 80px; max-height: 80px; width: auto; height: auto; object-fit: contain; border-radius: 12px; background: rgba(0,0,0,0.3); padding: 8px; }
    .version-image .no-image { width: 70px; height: 70px; background: rgba(0,0,0,0.3); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 36px; color: #888; }
    .version-name { font-size: 18px; font-weight: bold; margin-bottom: 4px; color: #e0e0e0; }
    .version-number { font-size: 28px; font-weight: bold; color: #00d4aa; margin: 8px 0; letter-spacing: 1px; text-shadow: 0 0 10px rgba(0,212,170,0.3); }
    .version-link { display: inline-flex; align-items: center; justify-content: center; gap: 6px; width: 100%; margin-top: 12px; padding: 8px 12px; background: rgba(0,212,170,0.15); border-radius: 10px; text-decoration: none; color: #00d4aa; font-size: 13px; font-weight: 500; transition: all 0.2s; border: 1px solid rgba(0,212,170,0.3); }
    .version-link:hover { background: rgba(0,212,170,0.25); transform: translateY(-1px); }
  `,

  history: `
    .history-bg { background: linear-gradient(135deg, #3a5a6a 0%, #4a6a7a 100%); padding: 16px; border-radius: 16px; }
    .history-date { font-size: 14px; color: #ffd700; margin-bottom: 14px; text-align: center; letter-spacing: 1px; font-weight: 500; }
    .history-event-card { background: #f5f0e8; border-radius: 10px; padding: 8px 12px; margin-bottom: 6px; transition: all 0.2s; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .history-event-card:hover { background: #ede5d8; transform: translateX(2px); }
    .history-event-text { font-size: 12px; line-height: 1.5; color: #333333; text-align: left; word-wrap: break-word; white-space: normal; }
    .history-event-num { font-weight: bold; margin-right: 6px; }
    .history-event-year { margin-right: 6px; }
    .history-event-list { margin-top: 8px; max-height: 320px; overflow-y: auto; }
    .history-count { font-size: 11px; color: rgba(255,255,255,0.4); text-align: center; margin-top: 10px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.08); }
    .history-more { margin-top: 8px; text-align: center; }
    .history-more-btn { background: transparent; border: 1px solid #ffd700; border-radius: 20px; padding: 5px 14px; color: #ffd700; cursor: pointer; font-size: 11px; transition: all 0.2s; }
    .history-more-btn:hover { background: rgba(255,215,0,0.1); transform: translateY(-1px); }
    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-track { background: rgba(255,255,255,0.05); border-radius: 4px; }
    ::-webkit-scrollbar-thumb { background: #ffd700; border-radius: 4px; }
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
  version: { name: '每日固件', icon: '🔄', defaultTitle: '每日固件' },
  history: { name: '每日历史', icon: '📅', defaultTitle: '每日历史' }
};

// ============================================================
// 3. 工具函数
// ============================================================

const Utils = {
  formatPrice(p) { return p !== null && !isNaN(p) ? p.toFixed(2) : '--'; },
  parseTemp(min, max) {
    if (!min && !max) return '--';
    if (min === max) return `${min}°C`;
    return `${min}~${max}°C`;
  },
  getWeatherText(day) {
    const dayText = day.textDay || '';
    const nightText = day.textNight || '';
    if (dayText === nightText) return dayText || '--';
    if (dayText && nightText) return `${dayText}转${nightText}`;
    return dayText || nightText || '--';
  },
  getWind(day) {
    const dir = day.windDirDay || '';
    const scale = day.windScaleDay || '';
    if (dir && scale) return `${dir}${scale}级`;
    if (dir) return dir;
    if (scale) return `${scale}级`;
    return '--';
  }
};

// ============================================================
// 4. 数据获取
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
    return {
      city: cityInfo.name || '未知',
      today: Utils.getWeatherText(today),
      temp: Utils.parseTemp(today.tempMin, today.tempMax),
      humidity: today.humidity || '--',
      wind: Utils.getWind(today),
      uv: today.uvIndex ? `${today.uvIndex}级` : '--',
      tomorrow: Utils.getWeatherText(tomorrow),
      day3: Utils.getWeatherText(day3)
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
        .map(([year, event]) => ({ year, event: typeof event === 'string' ? event : (event.event || event.desc) }));
    }
    return {
      today: d.today || '',
      count: d.count || events.length,
      event: d.event || (events[0]?.event || '暂无事件'),
      events
    };
  }
};

// ============================================================
// 5. 渲染函数
// ============================================================

const Renderers = {
  getHeader(showRefresh, title, icon) {
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
    `;
  },
  weather(data, config) {
    const tempMatch = String(data.temp).match(/(\d+)/);
    const tempValue = tempMatch ? tempMatch[0] : '--';
    return `
      <div class="weather-bg">
        ${Renderers.getHeader(config.show_refresh, '每日天气', '🌤️')}
        <div class="temp-container"><div class="weather-temp">${tempValue}°C</div><div class="weather-desc">${data.today}</div><div class="weather-city">${data.city}</div></div>
        <div class="weather-stats"><div class="weather-stat">💧 ${data.humidity}%</div><div class="weather-stat">💨 ${data.wind}</div><div class="weather-stat">☀️ ${data.uv}</div></div>
        <div class="forecast-container"><div class="forecast-item">明天<br>${String(data.tomorrow).split('，')[0]}</div><div class="forecast-item">后天<br>${String(data.day3).split('，')[0]}</div></div>
      </div>
    `;
  },
  oil(data, config) {
    const countdown = data.countdown !== null && data.countdown !== '暂无数据' ? parseInt(data.countdown) : null;
    const countdownHtml = (countdown && countdown > 0 && countdown < 365) ? `<div class="countdown-badge ${countdown <= 3 ? 'urgent' : ''}">⏰ 倒计时 ${countdown}天</div>` : '';
    return `
      <div class="oil-bg">
        <div class="oil-header">
          <div class="oil-title"><span>⛽</span><span>${data.province}每日油价</span></div>
          <div class="header-buttons">
            ${countdownHtml}
            ${config.show_refresh ? '<button class="btn-icon refresh-btn">🔄</button>' : ''}
            <button class="btn-icon type-switch-btn">▼</button>
          </div>
        </div>
        <div class="oil-price-grid">
          <div class="oil-item"><div class="oil-item-label">92#</div><div class="oil-price">${Utils.formatPrice(data.price92)}</div></div>
          <div class="oil-item"><div class="oil-item-label">95#</div><div class="oil-price">${Utils.formatPrice(data.price95)}</div></div>
          <div class="oil-item"><div class="oil-item-label">98#</div><div class="oil-price">${Utils.formatPrice(data.price98)}</div></div>
          <div class="oil-item"><div class="oil-item-label">0#</div><div class="oil-price">${Utils.formatPrice(data.price0)}</div></div>
        </div>
        <div class="oil-footer"><div class="oil-tip"><span class="oil-tip-icon">📢</span> ${data.tip}</div></div>
      </div>
    `;
  },
  yiyan(data, config) {
    let content = data.content;
    if (content.startsWith('“') && content.endsWith('”')) content = content.slice(1, -1);
    if (content.startsWith('"') && content.endsWith('"')) content = content.slice(1, -1);
    return `
      <div class="yiyan-bg">
        ${Renderers.getHeader(config.show_refresh, '每日一言', '💬')}
        <div class="yiyan-content">${content}</div>
        <div class="yiyan-author">—— ${data.author}${data.source !== '未知来源' ? `《${data.source}》` : ''}</div>
      </div>
    `;
  },
  poem(data, config) {
    const lines = String(data.fullContent || data.content).split('\n').filter(l => l.trim());
    const hasTranslate = data.translate && data.translate !== '无译文' && data.translate !== '加载中...';
    return `
      <div class="poem-bg">
        ${Renderers.getHeader(config.show_refresh, '每日诗词', '📜')}
        <div class="poem-title">${data.title}</div>
        <div class="poem-author">${data.dynasty} · ${data.author}</div>
        <div class="poem-content">${lines.slice(0, 12).map(l => `<div class="poem-line">${l}</div>`).join('')}${lines.length > 12 ? `<div class="poem-line">......</div>` : ''}</div>
        ${hasTranslate ? `<details class="poem-translate"><summary>📖 查看译文</summary><div class="poem-translate-content">${data.translate}</div></details>` : ''}
      </div>
    `;
  },
  version(data, config) {
    const deviceImage = data.deviceCover;
    return `
      <div class="version-bg">
        ${Renderers.getHeader(config.show_refresh, '每日固件', '🔄')}
        <div class="version-image">${deviceImage ? `<img src="${deviceImage}" alt="${data.device}" onerror="this.style.display='none';this.parentElement.querySelector('.no-image').style.display='flex'">` : '<div class="no-image">🖥️</div>'}</div>
        <div class="version-name">${data.device}</div>
        <div class="version-number">${data.current}</div>
        <a href="https://fw.koolcenter.com/iStoreOS/" target="_blank" rel="noopener noreferrer" class="version-link">🔗 前往下载中心</a>
      </div>
    `;
  },
  history(data, config, showFullHistory) {
    let events = [];
    if (data.events && Array.isArray(data.events)) {
      events = data.events.map(item => ({ 
        year: item.year || '未知', 
        desc: item.event || item.desc || String(item) 
      }));
    }
    const defaultShowCount = 3;
    const displayEvents = showFullHistory ? events : events.slice(0, defaultShowCount);
    const hasMore = events.length > defaultShowCount;
    const eventCount = data.count || events.length;
    
    if (events.length === 0) {
      return `<div class="history-bg">${Renderers.getHeader(config.show_refresh, '每日历史', '📅')}<div class="history-date">📅 ${data.today || '--'}</div><div class="history-event-card"><div class="history-event-text">暂无历史事件</div></div><div class="history-count">📋 共 0 件历史大事</div></div>`;
    }
    
    const eventCards = displayEvents.map((event, idx) => `
      <div class="history-event-card">
        <div class="history-event-text">
          <span class="history-event-num">${idx + 1}.</span>
          <span class="history-event-year">${event.year}</span>
          <span>${event.desc}</span>
        </div>
      </div>
    `).join('');
    
    return `
      <div class="history-bg">
        ${Renderers.getHeader(config.show_refresh, '每日历史', '📅')}
        <div class="history-date">📅 ${data.today || '--'}</div>
        <div class="${showFullHistory ? 'history-event-list' : ''}">
          ${eventCards}
        </div>
        <div class="history-count">📋 共 ${eventCount} 件历史大事</div>
        ${hasMore ? `
          <div class="history-more">
            <button class="history-more-btn">${showFullHistory ? '收起 ▲' : '展开更多 ▼'}</button>
          </div>
        ` : ''}
      </div>
    `;
  }
};

// ============================================================
// 6. 主卡片类
// ============================================================

class MyraidBoxCard extends HTMLElement {
  static getConfigElement() { return document.createElement('myraid-box-card-editor'); }
  static getStubConfig() {
    return {
      card_type: 'weather',
      show_refresh: true,
      auto_rotate: false,
      rotate_interval: 10
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
    this._menu = null;
    this._allTypes = Object.keys(CardTypes);
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
    if (this._data.weather) this._render();
    else this._loadData();
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
    if (this.config.auto_rotate && this._allTypes.length > 1) {
      this._rotateInterval = setInterval(() => {
        const idx = this._allTypes.indexOf(this._currentType);
        this._currentType = this._allTypes[(idx + 1) % this._allTypes.length];
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

  _createMenu() {
    if (this._menu) return;
    this._menu = document.createElement('div');
    this._menu.className = 'type-menu';
    this.shadowRoot.appendChild(this._menu);
  }

  _updateMenuContent() {
    if (!this._menu) return;
    this._menu.innerHTML = this._allTypes.map(type => `
      <div class="type-option" data-type="${type}">${CardTypes[type]?.icon || '📋'} ${CardTypes[type]?.name || type}</div>
    `).join('');
  }

  _showMenu(button) {
    if (!this._menu) return;
    this._updateMenuContent();
    const rect = button.getBoundingClientRect();
    this._menu.style.position = 'fixed';
    this._menu.style.top = `${rect.bottom + 4}px`;
    this._menu.style.left = `${rect.right - 120}px`;
    this._menu.classList.add('show');
    
    const options = this._menu.querySelectorAll('.type-option');
    options.forEach(opt => {
      opt.onclick = (e) => {
        e.stopPropagation();
        const type = opt.dataset.type;
        if (type && type !== this._currentType) {
          this._currentType = type;
          this._applyStyles();
          this._render();
        }
        this._menu.classList.remove('show');
      };
    });
  }

  _render() {
    if (!this._data.weather) {
      this.shadowRoot.innerHTML = `<ha-card><div class="loading">加载中...</div></ha-card>`;
      this._applyStyles();
      return;
    }
    
    const existingMenu = this._menu;
    
    const renderMap = {
      weather: () => Renderers.weather(this._data.weather, this.config),
      oil: () => Renderers.oil(this._data.oil, this.config),
      yiyan: () => Renderers.yiyan(this._data.yiyan, this.config),
      poem: () => Renderers.poem(this._data.poem, this.config),
      version: () => Renderers.version(this._data.version, this.config),
      history: () => Renderers.history(this._data.history, this.config, this._showFullHistory)
    };
    const contentHtml = renderMap[this._currentType]?.() || '<div class="error-container">未知卡片类型</div>';
    this.shadowRoot.innerHTML = `<ha-card style="overflow: visible;">${contentHtml}</ha-card>`;
    
    if (existingMenu) {
      this._menu = existingMenu;
      this.shadowRoot.appendChild(this._menu);
    } else {
      this._createMenu();
    }
    
    this._applyStyles();
    this._attachEvents();
  }

  _attachEvents() {
    const refreshBtn = this.shadowRoot?.querySelector('.refresh-btn');
    if (refreshBtn) {
      const newBtn = refreshBtn.cloneNode(true);
      refreshBtn.parentNode?.replaceChild(newBtn, refreshBtn);
      newBtn.addEventListener('click', (e) => { e.stopPropagation(); this._refresh(); });
    }
    
    const switchBtn = this.shadowRoot?.querySelector('.type-switch-btn');
    if (switchBtn) {
      const newBtn = switchBtn.cloneNode(true);
      switchBtn.parentNode?.replaceChild(newBtn, switchBtn);
      newBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (this._menu.classList.contains('show')) {
          this._menu.classList.remove('show');
        } else {
          this._showMenu(newBtn);
        }
      });
    }
    
    const closeMenuHandler = (e) => {
      if (this._menu && !this._menu.contains(e.target) && !this.shadowRoot?.querySelector('.type-switch-btn')?.contains(e.target)) {
        this._menu.classList.remove('show');
      }
    };
    document.removeEventListener('click', closeMenuHandler);
    document.addEventListener('click', closeMenuHandler);
    
    const moreBtn = this.shadowRoot?.querySelector('.history-more-btn');
    if (moreBtn) {
      const newMoreBtn = moreBtn.cloneNode(true);
      moreBtn.parentNode?.replaceChild(newMoreBtn, moreBtn);
      newMoreBtn.addEventListener('click', (e) => { e.stopPropagation(); this._showFullHistory = !this._showFullHistory; this._render(); });
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
// 7. 可视化编辑器（使用HA原生组件）
// ============================================================

class MyraidBoxCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = {};
    this._schema = [
      { name: 'card_type', label: '卡片形态', type: 'select', options: Object.entries(CardTypes).map(([k, v]) => [k, v.name]) },
      { name: 'show_refresh', label: '显示刷新按钮', type: 'boolean' },
      { name: 'auto_rotate', label: '自动轮播', type: 'boolean' },
      { name: 'rotate_interval', label: '轮播间隔（秒）', type: 'integer', min: 3, max: 60 }
    ];
  }

  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
  }

  async _render() {
    if (!this._hass) return;
    const form = document.createElement('ha-form');
    form.schema = this._schema;
    form.data = this._config;
    form.computeLabel = (schema) => schema.label;
    form.addEventListener('value-changed', (e) => {
      this._config = { ...this._config, ...e.detail.value };
      this._fireEvent();
    });
    this.shadowRoot.innerHTML = '';
    this.shadowRoot.appendChild(form);
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
// 8. 注册组件
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
  for (const s of scripts) if (s.src?.includes('myraid_box_card')) {
    const m = s.src.match(/ver=([a-f0-9]+)/);
    if (m) return m[1];
  }
  return Date.now().toString(36);
})();
console.log(`🎴 万象盒子卡片 v${VERSION} 已加载`);
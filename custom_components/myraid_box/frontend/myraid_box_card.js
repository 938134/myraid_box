// ============================================================
// 万象盒子多功能卡片 v1.0.8 - 卡片优化版
// 优化：天气卡片布局、一言问候语+时间、历史标题固定
// ============================================================

const THEMES = {
  red: { name: '中国红', icon: '🟥', bgStart: '#1a0a0a', bgEnd: '#4a1515', accent: '#ff4444' },
  amber: { name: '琥珀橙', icon: '🟧', bgStart: '#1a0e08', bgEnd: '#3d1a0a', accent: '#ffaa00' },
  yellow: { name: '柠檬黄', icon: '🟨', bgStart: '#1a1a08', bgEnd: '#3d3d0a', accent: '#ffdd00' },
  green: { name: '深钢绿', icon: '🟩', bgStart: '#0a1a12', bgEnd: '#0d2d1a', accent: '#00ff88' },
  cyan: { name: '冰霜青', icon: '🟦', bgStart: '#0a1a20', bgEnd: '#0d2d35', accent: '#00e5ff' },
  sky: { name: '天空蓝', icon: '🔷', bgStart: '#0a1030', bgEnd: '#1a2a60', accent: '#60a5fa' },
  purple: { name: '霓虹紫', icon: '🟪', bgStart: '#150a2a', bgEnd: '#2d0d45', accent: '#c084fc' }
};

const CARD_TYPES = {
  weather: { name: '每日天气', icon: '🌤️' },
  oil: { name: '每日油价', icon: '⛽' },
  yiyan: { name: '每日一言', icon: '💬' },
  poem: { name: '每日诗词', icon: '📜' },
  version: { name: '每日固件', icon: '🔄' },
  history: { name: '每日历史', icon: '📅' }
};

const styleCache = new Map();
const getStyles = (theme) => {
  if (styleCache.has(theme)) return styleCache.get(theme);
  const t = THEMES[theme] || THEMES.sky;
  const [r, g, b] = [t.accent.slice(1,3), t.accent.slice(3,5), t.accent.slice(5,7)].map(h => parseInt(h, 16));
  
  const style = `
    :host {
      --bg-start: ${t.bgStart};
      --bg-end: ${t.bgEnd};
      --accent: ${t.accent};
      --card-bg: rgba(${r},${g},${b},0.12);
      --text: #ffffff;
      --text-light: #a0b0d0;
      --border: rgba(255,255,255,0.08);
      display: block;
    }
    
    ha-card {
      background: linear-gradient(135deg, var(--bg-start), var(--bg-end));
      border-radius: 28px;
      border: 1px solid var(--border);
      overflow: hidden;
      color: var(--text);
    }
    
    * {
      color: inherit;
    }
    
    .head { 
      display: flex; 
      justify-content: space-between; 
      align-items: center; 
      padding: 16px 20px; 
      border-bottom: 1px solid var(--border); 
    }
    .head-title { 
      font-weight: 600; 
      color: var(--accent); 
      font-size: 16px;
    }
    .head-btns { 
      display: flex; 
      gap: 8px; 
      align-items: center; 
    }
    .type-select, .theme-select { 
      width: 36px; 
      height: 36px; 
      border-radius: 50%; 
      background: rgba(128,128,128,0.15); 
      border: 1px solid var(--border);
      color: var(--text); 
      font-size: 18px; 
      cursor: pointer;
      display: flex; 
      align-items: center; 
      justify-content: center;
      transition: all 0.2s;
      user-select: none;
    }
    .type-select:hover, .theme-select:hover { 
      background: var(--accent); 
      color: var(--bg-start); 
      transform: scale(1.05); 
    }
    .menu-panel {
      position: fixed;
      background: linear-gradient(135deg, var(--bg-start), var(--bg-end));
      border: 1px solid var(--border);
      border-radius: 20px;
      z-index: 1000000;
      display: none;
      min-width: 160px;
      backdrop-filter: blur(20px);
      box-shadow: 0 8px 32px rgba(0,0,0,0.4);
      overflow: hidden;
    }
    .menu-panel.show { display: block; }
    .menu-item {
      padding: 12px 16px;
      color: var(--text);
      cursor: pointer;
      font-size: 14px;
      display: flex;
      align-items: center;
      gap: 12px;
      transition: all 0.2s;
      white-space: nowrap;
    }
    .menu-item:hover { 
      background: var(--accent); 
      color: var(--bg-start); 
    }
    .menu-item span:first-child { font-size: 18px; }
    .countdown { 
      background: var(--accent); 
      color: var(--bg-start); 
      padding: 4px 12px; 
      border-radius: 24px; 
      font-size: 11px; 
      font-weight: 700; 
    }
    .body { padding: 20px; }
    .loading { 
      text-align: center; 
      padding: 60px; 
      color: var(--text-light); 
    }
    
    /* 天气卡片 */
    .weather-temp {
      font-size: 72px;
      font-weight: 800;
      color: var(--accent);
      line-height: 1;
    }
    .weather-temp span { font-size: 28px; }
    .weather-condition {
      font-size: 18px;
      font-weight: 500;
      margin-bottom: 6px;
    }
    .weather-city {
      font-size: 14px;
      color: var(--text-light);
    }
    .capsule-row {
      display: flex;
      gap: 24px;
      justify-content: center;
      margin-bottom: 20px;
    }
    .capsule {
      text-align: center;
      flex: 1;
    }
    .capsule-value {
      font-size: 18px;
      font-weight: 700;
      color: var(--accent);
    }
    .capsule-label {
      font-size: 11px;
      color: var(--text-light);
      margin-top: 4px;
    }
    .double-row {
      display: flex;
      gap: 12px;
    }
    .double-item {
      flex: 1;
      background: var(--card-bg);
      border-radius: 20px;
      padding: 14px;
      text-align: center;
      border: 1px solid var(--border);
    }
    .double-label {
      font-size: 13px;
      color: var(--text-light);
    }
    .double-value {
      font-size: 16px;
      font-weight: 600;
      color: var(--accent);
      margin-top: 6px;
    }
    
    /* 油价卡片 */
    .oil-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin-bottom: 16px;
    }
    .oil-item {
      text-align: center;
      padding: 12px 8px;
      background: var(--card-bg);
      border-radius: 20px;
      border: 1px solid var(--border);
    }
    .oil-type {
      font-size: 12px;
      color: var(--text-light);
    }
    .oil-price {
      font-size: 20px;
      font-weight: 800;
      color: var(--accent);
      margin-top: 6px;
    }
    .oil-unit {
      font-size: 10px;
      color: var(--text-light);
    }
    .oil-tip {
      padding: 12px 0;
      font-size: 13px;
      border-top: 1px solid var(--border);
    }
    
    /* 一言卡片 */
    .yiyan-card {
      padding: 20px;
    }
    .yiyan-text { 
      font-size: 18px; 
      line-height: 1.6; 
      font-style: italic; 
      margin-bottom: 16px;
      text-align: left;
    }
    .yiyan-author {
      color: var(--accent);
      font-size: 14px;
      text-align: right;
    }
    
    /* 诗词卡片 */
    .poem-card {
      text-align: center;
      font-family: "Noto Serif SC", "Source Han Serif", "STSong", "华文楷书", "KaiTi", serif;
      padding: 20px;
    }
    .poem-title { 
      font-size: 28px; 
      font-weight: 700; 
      color: var(--accent);
      margin-bottom: 8px;
      letter-spacing: 2px;
    }
    .poem-author {
      font-size: 14px;
      color: var(--text-light);
      margin-bottom: 24px;
      font-style: italic;
    }
    .poem-content { 
      font-size: 15px;
      line-height: 2.2;
      margin: 20px 0;
      letter-spacing: 1px;
    }
    .poem-content div {
      margin: 8px 0;
    }
    
    /* 固件卡片 */
    .version-card {
      text-align: center;
    }
    .version-device {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      margin-bottom: 24px;
      font-size: 18px;
      font-weight: 600;
    }
    .version-device-icon {
      width: 40px;
      height: 40px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 32px;
    }
    .version-device-icon img {
      width: 100%;
      height: 100%;
      object-fit: contain;
    }
    .version-number-block {
      margin-bottom: 24px;
    }
    .version-number-value {
      font-size: 28px;
      font-weight: 800;
      color: var(--accent);
      font-family: monospace;
      display: inline-flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: center;
    }
    .new-badge {
      background: var(--accent);
      color: var(--bg-start);
      font-size: 12px;
      font-weight: 700;
      padding: 2px 10px;
      border-radius: 20px;
      display: inline-block;
    }
    .version-actions {
      display: flex;
      gap: 12px;
    }
    .version-link, .version-changelog {
      flex: 1;
      text-align: center;
      padding: 10px;
      border-radius: 30px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
      border: none;
      text-decoration: none;
    }
    .version-link { 
      background: var(--accent); 
      color: var(--bg-start); 
    }
    .version-changelog {
      background: rgba(128,128,128,0.15);
      color: var(--text);
      border: 1px solid var(--border);
    }
    .changelog-content {
      display: none;
      margin-top: 16px;
      padding: 16px;
      background: rgba(0,0,0,0.2);
      border-radius: 16px;
      font-size: 12px;
      line-height: 1.6;
      text-align: left;
    }
    .changelog-content.show { display: block; }
    
    /* 历史卡片 */
    .history-wrapper {
      display: flex;
      flex-direction: column;
    }
    .history-container {
      overflow-y: auto;
      scrollbar-width: thin;
      transition: max-height 0.3s ease-out;
    }
    .history-container.expanded {
      max-height: 400px;
      overflow-y: auto;
    }
    .history-container.collapsed {
      max-height: none;
      overflow-y: visible;
    }
    .history-container::-webkit-scrollbar {
      width: 4px;
    }
    .history-container::-webkit-scrollbar-track {
      background: var(--border);
      border-radius: 4px;
    }
    .history-container::-webkit-scrollbar-thumb {
      background: var(--accent);
      border-radius: 4px;
    }
    .history-date {
      text-align: center;
      font-weight: 600;
      color: var(--accent);
      margin-bottom: 16px;
      font-size: 16px;
    }
    .history-event {
      background: var(--card-bg);
      border-left: 3px solid var(--accent);
      border-radius: 12px;
      padding: 10px 14px;
      margin-bottom: 8px;
      font-size: 14px;
    }
    .history-event-year {
      font-weight: 700;
      color: var(--accent);
      margin-right: 12px;
    }
    .history-footer {
      text-align: center;
      font-size: 11px;
      color: var(--text-light);
      margin-top: 12px;
      padding-top: 8px;
      border-top: 1px solid var(--border);
    }
    .history-more-btn {
      background: transparent;
      border: none;
      border-radius: 24px;
      padding: 6px 16px;
      font-size: 12px;
      color: var(--accent);
      cursor: pointer;
      transition: all 0.2s;
      margin-top: 8px;
    }
    .history-more-btn:hover { 
      opacity: 0.8;
      text-decoration: underline;
    }
  `;
  
  styleCache.set(theme, style);
  return style;
};

const API = {
  async fetch() {
    try {
      const res = await fetch('/api/myraid_box/data');
      return res.ok ? await res.json() : null;
    } catch (e) { 
      console.error('数据获取失败:', e);
      return null; 
    }
  },
  
  parse(raw) {
    if (!raw) return null;
    const w = raw?.weather?.data?.daily_forecast || [];
    const o = raw?.oilprice?.data || {};
    const y = raw?.hitokoto?.data || {};
    const p = raw?.poetry?.data || {};
    const v = raw?.istoreos?.data || {};
    const h = raw?.history?.data || {};
    
    return {
      weather: {
        temp: w[0]?.tempMax || '--',
        city: raw?.weather?.data?.city_info?.name || '未知',
        today: w[0]?.textDay || '--',
        humidity: w[0]?.humidity || '--',
        wind: `${w[0]?.windDirDay || '--'} ${w[0]?.windScaleDay || '--'}级`,
        uv: w[0]?.uvIndex || '--',
        tomorrow: w[1]?.textDay || '--',
        day3: w[2]?.textDay || '--'
      },
      oil: {
        price92: o['92#'] || '--',
        price95: o['95#'] || '--',
        price98: o['98#'] || '--',
        price0: o['0#'] || '--',
        tip: o.tip || '暂无调价信息',
        countdown: parseInt(o.countdown) || 0
      },
      yiyan: {
        content: (y.content || '暂无内容').replace(/^["']|["']$/g, ''),
        author: y.author || '佚名',
        source: y.source && y.source !== '未知来源' ? `《${y.source}》` : ''
      },
      poem: {
        title: p.title || '未知',
        author: p.author || '佚名',
        dynasty: p.dynasty || '未知',
        content: (p.full_content || p.content || '').split('\n').filter(l => l.trim()),
        translate: p.translate || ''
      },
      version: {
        device: v.device_name || '未知设备',
        fullVersion: v.latest_version || '未知',
        deviceCover: v.device_cover || '',
        changelog: v.changelog || '• 修复已知问题\n• 优化系统性能'
      },
      history: {
        today: h.today || '',
        events: h.events?.slice(0, 50).map(e => ({ 
          year: e.year || '未知', 
          desc: e.event || e.desc || '' 
        })) || [],
        count: h.count || 0
      }
    };
  }
};

const Render = {
  weather: (d) => `
    <div style="display: flex; align-items: center; gap: 24px; margin-bottom: 24px;">
      <div class="weather-temp">${d.temp}<span>°C</span></div>
      <div style="flex: 1;">
        <div class="weather-condition">${d.today}</div>
        <div class="weather-city">📍 ${d.city}</div>
      </div>
    </div>
    <div class="capsule-row" style="margin-bottom: 20px;">
      <div class="capsule">
        <div class="capsule-value">${d.humidity}%</div>
        <div class="capsule-label">💧 湿度</div>
      </div>
      <div class="capsule">
        <div class="capsule-value">${d.wind}</div>
        <div class="capsule-label">💨 风力</div>
      </div>
      <div class="capsule">
        <div class="capsule-value">${d.uv}级</div>
        <div class="capsule-label">☀️ 紫外线</div>
      </div>
    </div>
    <div class="double-row">
      <div class="double-item">
        <div class="double-label">📅 明天</div>
        <div class="double-value">${d.tomorrow}</div>
      </div>
      <div class="double-item">
        <div class="double-label">📅 后天</div>
        <div class="double-value">${d.day3}</div>
      </div>
    </div>`,
  
  oil: (d) => `
    <div class="oil-grid">
      <div class="oil-item">
        <div class="oil-type">92#</div>
        <div class="oil-price">${d.price92}</div>
        <div class="oil-unit">元/升</div>
      </div>
      <div class="oil-item">
        <div class="oil-type">95#</div>
        <div class="oil-price">${d.price95}</div>
        <div class="oil-unit">元/升</div>
      </div>
      <div class="oil-item">
        <div class="oil-type">98#</div>
        <div class="oil-price">${d.price98}</div>
        <div class="oil-unit">元/升</div>
      </div>
      <div class="oil-item">
        <div class="oil-type">0#</div>
        <div class="oil-price">${d.price0}</div>
        <div class="oil-unit">元/升</div>
      </div>
    </div>
    <div class="oil-tip">
      📢 ${d.tip}
    </div>`,
  
  yiyan: (d) => {
    const hour = new Date().getHours();
    let greeting = '';
    let timeIcon = '';
    if (hour < 6) { greeting = '夜深了'; timeIcon = '🌙'; }
    else if (hour < 9) { greeting = '早安'; timeIcon = '🌅'; }
    else if (hour < 12) { greeting = '上午好'; timeIcon = '☀️'; }
    else if (hour < 14) { greeting = '中午好'; timeIcon = '🍜'; }
    else if (hour < 18) { greeting = '下午好'; timeIcon = '☕'; }
    else if (hour < 22) { greeting = '晚上好'; timeIcon = '🌆'; }
    else { greeting = '夜深了'; timeIcon = '🌙'; }
    
    const now = new Date();
    const timeStr = `${now.getMonth()+1}/${now.getDate()} ${now.getHours().toString().padStart(2,'0')}:${now.getMinutes().toString().padStart(2,'0')}`;
    
    return `
      <div class="yiyan-card">
        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 20px; font-size: 13px; color: var(--text-light);">
          <span>${timeIcon} ${greeting}</span>
          <span>🕐 ${timeStr}</span>
        </div>
        <div class="yiyan-text">“${d.content}”</div>
        <div class="yiyan-author">—— ${d.author} ${d.source}</div>
      </div>
    `;
  },
  
  poem: (d) => `
    <div class="poem-card">
      <div class="poem-title">${d.title}</div>
      <div class="poem-author">${d.dynasty} · ${d.author}</div>
      <div class="poem-content">${d.content.slice(0, 12).map(l => `<div>${l}</div>`).join('')}</div>
      ${d.translate ? `
        <details style="margin-top:16px">
          <summary style="font-size:13px;color:var(--text-light);cursor:pointer">📖 查看译文</summary>
          <div style="margin-top:12px;padding:12px;background:rgba(0,0,0,0.2);border-radius:12px;font-size:14px;text-align:left">${d.translate}</div>
        </details>
      ` : ''}
    </div>`,
  
  version: (d) => `
    <div class="version-card">
      <div class="version-device">
        <div class="version-device-icon">
          ${d.deviceCover ? `<img src="${d.deviceCover}" onerror="this.parentElement.innerHTML='🖥️'">` : '🖥️'}
        </div>
        <span>${d.device}</span>
      </div>
      <div class="version-number-block">
        <div class="version-number-value">
          ${d.fullVersion}
          <span class="new-badge">NEW</span>
        </div>
      </div>
      <div class="version-actions">
        <a href="https://fw.koolcenter.com/iStoreOS/" target="_blank" class="version-link">📥 下载</a>
        <button class="version-changelog" data-action="toggle-changelog">📋 更新日志</button>
      </div>
      <div class="changelog-content" id="changelogContent">
        <strong style="color:var(--accent)">✨ 更新内容：</strong><br>${d.changelog.replace(/\n/g, '<br>')}
      </div>
    </div>`,
  
  history: (d, full) => {
    const displayEvents = full ? d.events : d.events.slice(0, 3);
    const containerClass = full ? 'history-container expanded' : 'history-container collapsed';
    
    return `
      <div class="history-wrapper">
        <div class="history-date">📅 历史上的今天</div>
        <div class="${containerClass}" id="historyContainer">
          ${displayEvents.map(e => `
            <div class="history-event">
              <span class="history-event-year">${e.year}</span>
              <span>${e.desc}</span>
            </div>
          `).join('')}
        </div>
        <div class="history-footer">
          📋 共 ${d.count || d.events.length} 件大事
          ${d.events.length > 3 ? `
            <button class="history-more-btn" data-action="toggle-history">${full ? '收起 ▲' : '展开更多 ▼'}</button>
          ` : ''}
        </div>
      </div>
    `;
  }
};

class MyraidBoxCard extends HTMLElement {
  static getConfigElement = () => document.createElement('myraid-box-card-editor');
  static getStubConfig = () => ({ card_type: 'weather', theme: 'sky', auto_rotate: false, rotate_interval: 10 });

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = MyraidBoxCard.getStubConfig();
    this._data = null;
    this._timer = null;
    this._full = false;
    this._menu = null;
    this._themeMenu = null;
    this._card = null;
    this._menuOpen = false;
    this._themeMenuOpen = false;
    this._boundOutsideClick = this._handleOutsideClick.bind(this);
    this._boundMenuClick = this._handleMenuClick.bind(this);
    this._boundThemeMenuClick = this._handleThemeMenuClick.bind(this);
    this._boundCardClick = this._handleCardClick.bind(this);
  }

  setConfig(config) {
    this._config = { ...this._config, ...config };
    this._applyTheme();
    this._setupRotate();
    this._load();
  }

  set hass(hass) { 
    this._hass = hass; 
    !this._data && this._load(); 
  }

  _applyTheme() {
    let style = this.shadowRoot.querySelector('style');
    if (!style) {
      style = document.createElement('style');
      this.shadowRoot.appendChild(style);
    }
    style.textContent = getStyles(this._config.theme);
  }

  _setupRotate() {
    clearInterval(this._timer);
    if (this._config.auto_rotate) {
      this._timer = setInterval(() => {
        const types = Object.keys(CARD_TYPES);
        this._config.card_type = types[(types.indexOf(this._config.card_type) + 1) % types.length];
        this._updateDisplay();
      }, (this._config.rotate_interval || 10) * 1000);
    }
  }

  async _load() {
    const raw = await API.fetch();
    this._data = API.parse(raw);
    this._render();
  }

  _render() {
    if (!this._card) {
      this.shadowRoot.innerHTML = '';
      
      const style = document.createElement('style');
      style.textContent = getStyles(this._config.theme);
      this.shadowRoot.appendChild(style);
      
      this._card = document.createElement('ha-card');
      this.shadowRoot.appendChild(this._card);
      
      this._menu = document.createElement('div');
      this._menu.className = 'menu-panel';
      this._menu.innerHTML = Object.entries(CARD_TYPES).map(([k, v]) => `
        <div class="menu-item" data-type="${k}"><span>${v.icon}</span><span>${v.name}</span></div>
      `).join('');
      this.shadowRoot.appendChild(this._menu);
      
      this._themeMenu = document.createElement('div');
      this._themeMenu.className = 'menu-panel';
      this._themeMenu.innerHTML = Object.entries(THEMES).map(([k, v]) => `
        <div class="menu-item" data-theme="${k}"><span>${v.icon}</span><span>${v.name}</span></div>
      `).join('');
      this.shadowRoot.appendChild(this._themeMenu);
      
      this._menu.addEventListener('click', this._boundMenuClick, true);
      this._themeMenu.addEventListener('click', this._boundThemeMenuClick, true);
      document.addEventListener('click', this._boundOutsideClick, true);
      this._card.addEventListener('click', this._boundCardClick);
    }

    if (!this._data) {
      this._card.innerHTML = '<div class="loading">加载中...</div>';
      return;
    }

    this._updateDisplay();
  }
  
  _handleCardClick(e) {
    const target = e.target.closest('[data-action]');
    if (!target) return;
    e.stopPropagation();
    
    const action = target.dataset.action;
    
    if (action === 'toggle-changelog') {
      const content = this._card.querySelector('#changelogContent');
      if (content) {
        content.classList.toggle('show');
        target.textContent = content.classList.contains('show') ? '📋 收起' : '📋 更新日志';
      }
    } else if (action === 'toggle-history') {
      this._full = !this._full;
      this._updateHistoryDisplay();
    }
  }
  
  _updateHistoryDisplay() {
    const body = this._card.querySelector('#cardBody');
    if (!body) return;
    
    const historyData = this._data.history;
    if (!historyData) return;
    
    const displayEvents = this._full ? historyData.events : historyData.events.slice(0, 3);
    const containerClass = this._full ? 'history-container expanded' : 'history-container collapsed';
    
    const newHistoryHTML = `
      <div class="history-wrapper">
        <div class="history-date">📅 历史上的今天</div>
        <div class="${containerClass}" id="historyContainer">
          ${displayEvents.map(e => `
            <div class="history-event">
              <span class="history-event-year">${e.year}</span>
              <span>${e.desc}</span>
            </div>
          `).join('')}
        </div>
        <div class="history-footer">
          📋 共 ${historyData.count || historyData.events.length} 件大事
          ${historyData.events.length > 3 ? `
            <button class="history-more-btn" data-action="toggle-history">${this._full ? '收起 ▲' : '展开更多 ▼'}</button>
          ` : ''}
        </div>
      </div>
    `;
    
    body.innerHTML = newHistoryHTML;
  }
  
  _handleMenuClick(e) {
    e.stopPropagation();
    e.stopImmediatePropagation();
    e.preventDefault();
    
    const item = e.target.closest('.menu-item');
    if (!item) return;
    
    const newType = item.dataset.type;
    if (newType && this._config.card_type !== newType) {
      this._config.card_type = newType;
      this._full = false;
      this._updateDisplay();
    }
    
    this._menu.classList.remove('show');
    this._menuOpen = false;
  }
  
  _handleThemeMenuClick(e) {
    e.stopPropagation();
    e.stopImmediatePropagation();
    e.preventDefault();
    
    const item = e.target.closest('.menu-item');
    if (!item) return;
    
    const newTheme = item.dataset.theme;
    if (newTheme && this._config.theme !== newTheme) {
      this._config.theme = newTheme;
      this._applyTheme();
      this._updateDisplay();
    }
    
    this._themeMenu.classList.remove('show');
    this._themeMenuOpen = false;
  }
  
  _handleOutsideClick(e) {
    if (this._menuOpen || this._menu?.classList.contains('show')) {
      const path = e.composedPath();
      const isMenuClick = path.includes(this._menu);
      const isMenuBtnClick = path.some(node => 
        node?.classList?.contains?.('type-select') || node?.id === 'menuBtn'
      );
      
      if (!isMenuClick && !isMenuBtnClick) {
        this._menu.classList.remove('show');
        this._menuOpen = false;
      }
    }
    
    if (this._themeMenuOpen || this._themeMenu?.classList.contains('show')) {
      const path = e.composedPath();
      const isThemeMenuClick = path.includes(this._themeMenu);
      const isThemeBtnClick = path.some(node => 
        node?.classList?.contains?.('theme-select') || node?.id === 'themeBtn'
      );
      
      if (!isThemeMenuClick && !isThemeBtnClick) {
        this._themeMenu.classList.remove('show');
        this._themeMenuOpen = false;
      }
    }
  }

  _updateDisplay() {
    if (!this._data) return;
    const type = this._config.card_type;
    const cfg = CARD_TYPES[type];
    const data = this._data[type];
    
    let badge = '';
    if (type === 'oil' && data.countdown > 0 && data.countdown < 365) {
      badge = `<div class="countdown">⏰ ${data.countdown}天</div>`;
    }
    
    const currentTheme = THEMES[this._config.theme] || THEMES.sky;
    
    const bodyContent = type === 'history' 
      ? Render[type](data, this._full)
      : Render[type](data);
    
    this._card.innerHTML = `
      <div class="head">
        <div class="head-title">${cfg.icon} ${cfg.name}</div>
        <div class="head-btns">
          ${badge}
          <div class="theme-select" id="themeBtn">${currentTheme.icon}</div>
          <div class="type-select" id="menuBtn">▼</div>
        </div>
      </div>
      <div class="body" id="cardBody">${bodyContent}</div>
    `;
    
    const themeBtn = this._card.querySelector('#themeBtn');
    if (themeBtn) {
      const newThemeBtn = themeBtn.cloneNode(true);
      themeBtn.parentNode.replaceChild(newThemeBtn, themeBtn);
      
      newThemeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        e.preventDefault();
        
        const rect = newThemeBtn.getBoundingClientRect();
        this._themeMenu.style.top = `${rect.bottom + 4}px`;
        this._themeMenu.style.left = `${rect.right - 160}px`;
        
        if (this._themeMenu.classList.contains('show')) {
          this._themeMenu.classList.remove('show');
          this._themeMenuOpen = false;
        } else {
          this._menu.classList.remove('show');
          this._menuOpen = false;
          this._themeMenu.classList.add('show');
          this._themeMenuOpen = true;
        }
      });
    }
    
    const menuBtn = this._card.querySelector('#menuBtn');
    if (menuBtn) {
      const newBtn = menuBtn.cloneNode(true);
      menuBtn.parentNode.replaceChild(newBtn, menuBtn);
      
      newBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        e.preventDefault();
        
        const rect = newBtn.getBoundingClientRect();
        this._menu.style.top = `${rect.bottom + 4}px`;
        this._menu.style.left = `${rect.right - 160}px`;
        
        if (this._menu.classList.contains('show')) {
          this._menu.classList.remove('show');
          this._menuOpen = false;
        } else {
          this._themeMenu.classList.remove('show');
          this._themeMenuOpen = false;
          this._menu.classList.add('show');
          this._menuOpen = true;
        }
      });
    }
  }

  disconnectedCallback() { 
    clearInterval(this._timer);
    document.removeEventListener('click', this._boundOutsideClick, true);
    if (this._menu) {
      this._menu.removeEventListener('click', this._boundMenuClick, true);
    }
    if (this._themeMenu) {
      this._themeMenu.removeEventListener('click', this._boundThemeMenuClick, true);
    }
    if (this._card) {
      this._card.removeEventListener('click', this._boundCardClick);
    }
  }
}

class MyraidBoxCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = MyraidBoxCard.getStubConfig();
    this._initialized = false;
  }

  setConfig(config) { 
    this._config = { ...this._config, ...config }; 
  }
  
  set hass(hass) { 
    this._hass = hass; 
    if (!this._initialized) {
      this._initialized = true;
      this._render(); 
    }
  }

  static getConfigForm() {
    return {
      schema: [
        {
          name: 'card_type',
          selector: {
            select: {
              mode: 'dropdown',
              options: Object.entries(CARD_TYPES).map(([key, val]) => ({
                value: key,
                label: `${val.icon} ${val.name}`
              }))
            }
          }
        },
        {
          name: 'theme',
          selector: {
            select: {
              mode: 'dropdown',
              options: Object.entries(THEMES).map(([key, val]) => ({
                value: key,
                label: `${val.icon} ${val.name}`
              }))
            }
          }
        },
        {
          name: 'auto_rotate',
          selector: { boolean: {} }
        },
        {
          name: 'rotate_interval',
          selector: {
            number: {
              min: 3,
              max: 60,
              step: 1,
              unit_of_measurement: '秒'
            }
          }
        }
      ],
      computeLabel: (schema) => {
        const labels = {
          card_type: '卡片',
          theme: '主题',
          auto_rotate: '自动轮播',
          rotate_interval: '轮播间隔'
        };
        return labels[schema.name] || schema.name;
      },
      computeHelper: (schema) => {
        const helpers = {
          rotate_interval: '仅在启用自动轮播时有效',
          auto_rotate: '开启后卡片会自动切换类型'
        };
        return helpers[schema.name] || '';
      }
    };
  }

  async _render() {
    if (!this._hass || !customElements.get('ha-form')) {
      setTimeout(() => this._render(), 100);
      return;
    }
    
    this.shadowRoot.innerHTML = '';
    
    const form = document.createElement('ha-form');
    form.hass = this._hass;
    form.schema = MyraidBoxCardEditor.getConfigForm().schema;
    form.data = { ...this._config };
    form.computeLabel = MyraidBoxCardEditor.getConfigForm().computeLabel;
    form.computeHelper = MyraidBoxCardEditor.getConfigForm().computeHelper;
    
    form.addEventListener('value-changed', (e) => {
      e.stopPropagation();
      const newConfig = { ...this._config, ...e.detail.value };
      if (!newConfig.auto_rotate) delete newConfig.rotate_interval;
      this._config = newConfig;
      this.dispatchEvent(new CustomEvent('config-changed', { 
        detail: { config: this._config }, 
        bubbles: true, 
        composed: true 
      }));
    });
    
    form.addEventListener('click', (e) => e.stopPropagation());
    form.addEventListener('mousedown', (e) => e.stopPropagation());
    
    this.shadowRoot.appendChild(form);
  }
}

if (!customElements.get('myraid-box-card')) {
  customElements.define('myraid-box-card', MyraidBoxCard);
}
if (!customElements.get('myraid-box-card-editor')) {
  customElements.define('myraid-box-card-editor', MyraidBoxCardEditor);
}

window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === 'myraid-box-card')) {
  window.customCards.push({ 
    type: 'myraid-box-card', 
    name: '万象盒子', 
    description: '6合1多功能卡片 | 7色光谱主题 | 天气/一言/历史优化版', 
    preview: true
  });
}

console.log('✨ 万象盒子 v1.0.8 已加载（卡片优化版）');
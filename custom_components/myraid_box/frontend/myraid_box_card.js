// ============================================================
// 万象盒子多功能卡片 v2.0.5 - 最终定版
// 优化：天气字体颜色、油价2x2网格、历史高度280px
// ============================================================

const THEMES = {
  red: { name: '中国红', icon: '🟥', gradientStart: '#ff4444', gradientEnd: '#ff8844', accent: '#ff6644' },
  amber: { name: '琥珀橙', icon: '🟧', gradientStart: '#ffaa00', gradientEnd: '#ffdd44', accent: '#ffcc44' },
  yellow: { name: '柠檬黄', icon: '🟨', gradientStart: '#ffdd00', gradientEnd: '#88ff44', accent: '#ccff44' },
  green: { name: '深钢绿', icon: '🟩', gradientStart: '#00ff88', gradientEnd: '#00ffcc', accent: '#00ffaa' },
  cyan: { name: '冰霜青', icon: '🟦', gradientStart: '#00e5ff', gradientEnd: '#4488ff', accent: '#44aaff' },
  sky: { name: '天空蓝', icon: '🟦', gradientStart: '#60a5fa', gradientEnd: '#a855f7', accent: '#8877ff' },
  purple: { name: '霓虹紫', icon: '🟪', gradientStart: '#c084fc', gradientEnd: '#ff4488', accent: '#dd66aa' }
};

const CARD_TYPES = {
  weather: { name: '每日天气', icon: '🌤️' },
  oil: { name: '每日油价', icon: '⛽' },
  yiyan: { name: '每日一言', icon: '💬' },
  poem: { name: '每日诗词', icon: '📜' },
  version: { name: '每日固件', icon: '🔄' },
  history: { name: '每日历史', icon: '📅' }
};

const CONFIG = { CACHE_TTL: 5 * 60 * 1000, MAX_RETRIES: 3, RETRY_DELAY: 1000, MENU_WIDTH: 160, MENU_OFFSET: 4, HISTORY_MAX_HEIGHT: 280 };

const styleCache = new Map();

const getStyles = (theme) => {
  if (styleCache.has(theme)) return styleCache.get(theme);
  const t = THEMES[theme] || THEMES.sky;
  
  const style = `
    :host { --gradient-start: ${t.gradientStart}; --gradient-end: ${t.gradientEnd}; --accent: ${t.accent}; --text-primary: #ffffff; --text-secondary: rgba(255,255,255,0.7); --card-bg: rgba(0,0,0,0.3); --border: rgba(255,255,255,0.12); display: block; }
    ha-card { background: linear-gradient(135deg, var(--gradient-start), var(--gradient-end)); border-radius: 28px; border: 1px solid var(--border); overflow: hidden; color: var(--text-primary); }
    .head { display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; background: rgba(0,0,0,0.2); backdrop-filter: blur(8px); border-bottom: 1px solid var(--border); }
    .head-title { font-weight: 600; color: var(--accent); font-size: 16px; text-shadow: 0 1px 2px rgba(0,0,0,0.2); }
    .head-btns { display: flex; gap: 8px; align-items: center; }
    .type-select, .theme-select, .refresh-btn { width: 36px; height: 36px; border-radius: 50%; background: rgba(0,0,0,0.3); border: 1px solid var(--border); font-size: 18px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s; user-select: none; backdrop-filter: blur(4px); }
    .type-select:hover, .theme-select:hover, .refresh-btn:hover { background: var(--accent); color: #000; transform: scale(1.05); }
    .menu-panel { position: fixed; background: linear-gradient(135deg, var(--gradient-start), var(--gradient-end)); border: 1px solid var(--border); border-radius: 20px; z-index: 1000000; display: none; min-width: 160px; backdrop-filter: blur(20px); box-shadow: 0 8px 32px rgba(0,0,0,0.4); overflow: hidden; }
    .menu-panel.show { display: block; }
    .menu-item { padding: 12px 16px; cursor: pointer; font-size: 14px; display: flex; align-items: center; gap: 12px; white-space: nowrap; background: rgba(0,0,0,0.2); transition: all 0.2s; }
    .menu-item:hover { background: var(--accent); color: #000; }
    .menu-item span:first-child { font-size: 18px; }
    .countdown { background: var(--accent); color: #000; padding: 4px 12px; border-radius: 24px; font-size: 11px; font-weight: 700; }
    .body { padding: 16px 20px; background: var(--card-bg); backdrop-filter: blur(4px); margin: 8px; border-radius: 20px; }
    .loading, .error { text-align: center; padding: 40px; color: var(--text-primary); }
    .retry-btn { background: var(--accent); color: #000; border: none; border-radius: 20px; padding: 6px 16px; margin-top: 12px; cursor: pointer; }
    /* 天气卡片 */
    .weather-container { display: flex; align-items: center; justify-content: center; gap: 32px; margin-bottom: 24px; }
    .weather-temp { font-size: 64px; font-weight: 800; color: var(--accent); line-height: 1; text-shadow: 0 2px 4px rgba(0,0,0,0.2); }
    .weather-temp span { font-size: 28px; }
    .weather-info { text-align: left; }
    .weather-condition { font-size: 18px; font-weight: 600; margin-bottom: 4px; color: var(--accent); }
    .weather-city { font-size: 14px; color: var(--text-secondary); }
    .capsule-row { display: flex; gap: 32px; justify-content: center; margin-bottom: 20px; }
    .capsule { text-align: center; }
    .capsule-value { font-size: 18px; font-weight: 700; color: var(--accent); }
    .capsule-label { font-size: 11px; color: var(--text-secondary); margin-top: 4px; }
    .double-row { display: flex; gap: 12px; }
    .double-item { flex: 1; background: rgba(0,0,0,0.2); border-radius: 20px; padding: 14px; text-align: center; border: 1px solid var(--border); }
    .double-label { font-size: 13px; color: var(--text-secondary); }
    .double-value { font-size: 16px; font-weight: 600; color: var(--accent); margin-top: 6px; }
    /* 油价卡片 - 2x2网格 */
    .oil-title { font-size: 14px; font-weight: 600; color: var(--accent); text-align: center; margin-bottom: 16px; letter-spacing: 1px; }
    .oil-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }
    .oil-item { text-align: center; padding: 12px 8px; background: rgba(0,0,0,0.2); border-radius: 16px; border: 1px solid var(--border); }
    .oil-type { font-size: 14px; font-weight: 600; color: var(--accent); margin-bottom: 6px; }
    .oil-price { font-size: 22px; font-weight: 800; color: var(--text-primary); letter-spacing: 1px; }
    .oil-tip { padding: 12px 0 0 0; font-size: 12px; border-top: 1px solid var(--border); text-align: center; color: var(--text-secondary); }
    /* 一言卡片 */
    .yiyan-header { display: flex; align-items: center; justify-content: center; gap: 24px; margin-bottom: 24px; }
    .year-ring { position: relative; width: 70px; height: 70px; flex-shrink: 0; }
    .year-ring svg { width: 100%; height: 100%; transform: rotate(-90deg); }
    .ring-percent { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 14px; font-weight: 700; color: var(--accent); }
    .yiyan-info { text-align: center; }
    .time-greeting { font-size: 20px; font-weight: 600; color: var(--accent); margin-bottom: 4px; }
    .week-info { font-size: 14px; color: var(--text-secondary); }
    .progress-section { margin-bottom: 24px; }
    .progress-header { display: flex; justify-content: space-between; font-size: 11px; color: var(--text-secondary); margin-bottom: 6px; }
    .progress-bar { height: 6px; background: rgba(255,255,255,0.2); border-radius: 3px; overflow: hidden; }
    .progress-fill { height: 100%; background: var(--accent); border-radius: 3px; }
    .week-days { display: flex; justify-content: space-between; font-size: 10px; color: var(--text-secondary); margin-top: 6px; }
    .yiyan-text { font-size: 18px; line-height: 1.6; font-style: italic; margin-bottom: 16px; text-align: left; color: var(--text-primary); }
    .yiyan-author { color: var(--accent); font-size: 14px; text-align: right; }
    /* 诗词卡片 */
    .poem-card { text-align: center; font-family: "Noto Serif SC", "Source Han Serif", "STSong", "KaiTi", serif; padding: 8px; }
    .poem-title { font-size: 28px; font-weight: 700; color: var(--accent); margin-bottom: 8px; letter-spacing: 2px; }
    .poem-author { font-size: 14px; color: var(--text-secondary); margin-bottom: 24px; font-style: italic; }
    .poem-content { font-size: 15px; line-height: 2.2; margin: 20px 0; letter-spacing: 1px; color: var(--text-primary); }
    .poem-content div { margin: 8px 0; }
    /* 固件卡片 */
    .version-card { text-align: center; }
    .version-device { display: flex; align-items: center; justify-content: center; gap: 12px; margin-bottom: 20px; font-size: 18px; font-weight: 600; }
    .version-device-icon { width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; font-size: 28px; background: rgba(0,0,0,0.2); border-radius: 12px; }
    .version-device-icon img { width: 100%; height: 100%; object-fit: contain; border-radius: 8px; }
    .version-number { font-size: 28px; font-weight: 800; color: var(--accent); font-family: monospace; margin-bottom: 20px; }
    .new-badge { background: var(--accent); color: #000; font-size: 12px; font-weight: 700; padding: 2px 10px; border-radius: 20px; margin-left: 8px; }
    .version-actions { display: flex; gap: 12px; margin-bottom: 16px; }
    .version-btn { flex: 1; padding: 10px; border-radius: 30px; font-size: 13px; font-weight: 600; cursor: pointer; border: none; text-decoration: none; text-align: center; transition: all 0.2s; background: rgba(0,0,0,0.3); color: var(--text-primary); border: 1px solid var(--border); }
    .version-btn:hover { background: var(--accent); color: #000; }
    .changelog-content { display: none; margin-top: 16px; padding: 16px; background: rgba(0,0,0,0.3); border-radius: 16px; font-size: 12px; line-height: 1.6; text-align: left; }
    .changelog-content.show { display: block; }
    /* 历史卡片 */
    .history-wrapper { text-align: center; }
    .history-date { font-weight: 600; color: var(--accent); margin-bottom: 16px; font-size: 16px; }
    .history-list { max-height: ${CONFIG.HISTORY_MAX_HEIGHT}px; overflow-y: auto; scrollbar-width: thin; scrollbar-color: var(--accent) rgba(255,255,255,0.1); margin-bottom: 12px; }
    .history-list::-webkit-scrollbar { width: 4px; }
    .history-list::-webkit-scrollbar-track { background: rgba(255,255,255,0.08); border-radius: 4px; margin: 4px 0; }
    .history-list::-webkit-scrollbar-thumb { background: var(--accent); border-radius: 4px; }
    .history-list::-webkit-scrollbar-thumb:hover { background: var(--accent); opacity: 0.8; }
    .history-event { padding: 10px 0; border-bottom: 1px solid var(--border); text-align: left; }
    .history-event:last-child { border-bottom: none; }
    .history-event-year { font-weight: 700; color: var(--accent); margin-right: 12px; }
    .history-footer { font-size: 11px; color: var(--text-secondary); padding-top: 8px; border-top: 1px solid var(--border); }
  `;
  
  styleCache.set(theme, style);
  return style;
};

const API = {
  _cache: null, _cacheTime: 0,
  async fetchWithRetry(retries = CONFIG.MAX_RETRIES) {
    for (let i = 0; i < retries; i++) {
      try {
        const res = await fetch('/api/myraid_box/data');
        if (res.ok) return await res.json();
        throw new Error(`HTTP ${res.status}`);
      } catch (e) {
        if (i === retries - 1) throw e;
        await new Promise(r => setTimeout(r, CONFIG.RETRY_DELAY * (i + 1)));
      }
    }
  },
  async fetch() {
    const now = Date.now();
    if (this._cache && (now - this._cacheTime) < CONFIG.CACHE_TTL) return this._cache;
    try {
      const raw = await this.fetchWithRetry();
      this._cache = raw; this._cacheTime = now;
      return raw;
    } catch (e) {
      console.error('数据获取失败:', e);
      return this._cache || null;
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
      weather: { temp: w[0]?.tempMax || '--', city: raw?.weather?.data?.city_info?.name || '未知', today: w[0]?.textDay || '--', humidity: w[0]?.humidity || '--', wind: `${w[0]?.windDirDay || '--'} ${w[0]?.windScaleDay || '--'}级`, uv: w[0]?.uvIndex || '--', tomorrow: w[1]?.textDay || '--', day3: w[2]?.textDay || '--' },
      oil: { province: raw?.oilprice?.data?.province || '全国', price92: o['92#'] || '--', price95: o['95#'] || '--', price98: o['98#'] || '--', price0: o['0#'] || '--', tip: o.tip || '暂无调价信息', countdown: parseInt(o.countdown) || 0 },
      yiyan: { content: (y.content || '暂无内容').replace(/^["']|["']$/g, ''), author: y.author || '佚名', source: y.source && y.source !== '未知来源' ? `《${y.source}》` : '' },
      poem: { title: p.title || '未知', author: p.author || '佚名', dynasty: p.dynasty || '未知', content: (p.full_content || p.content || '').split('\n').filter(l => l.trim()), translate: p.translate || '' },
      version: { device: v.device_name || '未知设备', fullVersion: v.latest_version || '未知', deviceCover: v.device_cover || '', changelog: v.changelog || '• 修复已知问题\n• 优化系统性能' },
      history: { events: h.events?.slice(0, 50).map(e => ({ year: e.year || '未知', desc: e.event || e.desc || '' })) || [], count: h.count || 0 }
    };
  }
};

const Render = {
  weather: (d) => `<div class="weather-container"><div class="weather-temp">${d.temp}<span>°C</span></div><div class="weather-info"><div class="weather-condition">${d.today}</div><div class="weather-city">${d.city}</div></div></div><div class="capsule-row"><div class="capsule"><div class="capsule-value">${d.humidity}%</div><div class="capsule-label">💧 湿度</div></div><div class="capsule"><div class="capsule-value">${d.wind}</div><div class="capsule-label">💨 风力</div></div><div class="capsule"><div class="capsule-value">${d.uv}级</div><div class="capsule-label">☀️ 紫外线</div></div></div><div class="double-row"><div class="double-item"><div class="double-label">📅 明天</div><div class="double-value">${d.tomorrow}</div></div><div class="double-item"><div class="double-label">📅 后天</div><div class="double-value">${d.day3}</div></div></div>`,
  oil: (d) => `<div class="oil-title">${d.province}</div><div class="oil-grid"><div class="oil-item"><div class="oil-type">92#</div><div class="oil-price">${d.price92}</div></div><div class="oil-item"><div class="oil-type">95#</div><div class="oil-price">${d.price95}</div></div><div class="oil-item"><div class="oil-type">98#</div><div class="oil-price">${d.price98}</div></div><div class="oil-item"><div class="oil-type">0#</div><div class="oil-price">${d.price0}</div></div></div><div class="oil-tip">📢 ${d.tip}</div>`,
  yiyan: (d) => {
    const now = new Date();
    const startOfYear = new Date(now.getFullYear(), 0, 1);
    const endOfYear = new Date(now.getFullYear() + 1, 0, 1);
    const yearProgress = ((now - startOfYear) / (endOfYear - startOfYear)) * 100;
    const getWeekNumber = (date) => { const d = new Date(date); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() + 3 - (d.getDay() + 6) % 7); const week1 = new Date(d.getFullYear(), 0, 4); return Math.ceil(((d - week1) / 86400000 + 1) / 7); };
    const weekNum = getWeekNumber(now);
    const weekProgress = ((now.getDay() + 6) % 7 + 1) / 7 * 100;
    const hour = now.getHours();
    let greeting = '', timeIcon = '';
    if (hour < 6) { greeting = '夜深了'; timeIcon = '🌙'; }
    else if (hour < 9) { greeting = '早安'; timeIcon = '🌅'; }
    else if (hour < 12) { greeting = '上午好'; timeIcon = '☀️'; }
    else if (hour < 14) { greeting = '中午好'; timeIcon = '🍜'; }
    else if (hour < 18) { greeting = '下午好'; timeIcon = '☕'; }
    else if (hour < 22) { greeting = '晚上好'; timeIcon = '🌆'; }
    else { greeting = '夜深了'; timeIcon = '🌙'; }
    const timeStr = `${now.getHours().toString().padStart(2,'0')}:${now.getMinutes().toString().padStart(2,'0')}`;
    const radius = 16, circumference = 2 * Math.PI * radius, dashoffset = circumference * (1 - yearProgress / 100);
    return `<div class="yiyan-card"><div class="yiyan-header"><div class="year-ring"><svg viewBox="0 0 40 40"><circle cx="20" cy="20" r="16" fill="none" stroke="rgba(255,255,255,0.2)" stroke-width="3"/><circle cx="20" cy="20" r="16" fill="none" stroke="var(--accent)" stroke-width="3" stroke-dasharray="${circumference}" stroke-dashoffset="${dashoffset}" stroke-linecap="round"/></svg><div class="ring-percent">${Math.floor(yearProgress)}%</div></div><div class="yiyan-info"><div class="time-greeting">${timeStr} ${timeIcon} ${greeting}</div><div class="week-info">📅 第${weekNum}周</div></div></div><div class="progress-section"><div class="progress-header"><span>📊 本周进度</span><span>${Math.floor(weekProgress)}%</span></div><div class="progress-bar"><div class="progress-fill" style="width: ${weekProgress}%"></div></div><div class="week-days"><span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span><span>日</span></div></div><div class="yiyan-text">“${d.content}”</div><div class="yiyan-author">—— ${d.author} ${d.source}</div></div>`;
  },
  poem: (d) => `<div class="poem-card"><div class="poem-title">${d.title}</div><div class="poem-author">${d.dynasty} · ${d.author}</div><div class="poem-content">${d.content.slice(0, 12).map(l => `<div>${l}</div>`).join('')}</div>${d.translate ? `<details style="margin-top:16px"><summary style="font-size:13px;color:var(--text-secondary);cursor:pointer">📖 查看译文</summary><div style="margin-top:12px;padding:12px;background:rgba(0,0,0,0.3);border-radius:12px;font-size:14px;text-align:left">${d.translate}</div></details>` : ''}</div>`,
  version: (d) => `<div class="version-card"><div class="version-device"><div class="version-device-icon">${d.deviceCover ? `<img src="${d.deviceCover}" onerror="this.parentElement.innerHTML='🖥️'">` : '🖥️'}</div><span>${d.device}</span></div><div class="version-number">${d.fullVersion}<span class="new-badge">NEW</span></div><div class="version-actions"><a href="https://fw.koolcenter.com/iStoreOS/" target="_blank" class="version-btn">📥 下载</a><button class="version-btn" data-action="toggle-changelog">📋 更新日志</button></div><div class="changelog-content" id="changelogContent"><strong style="color:var(--accent)">✨ 更新内容：</strong><br>${d.changelog.replace(/\n/g, '<br>')}</div></div>`,
  history: (d) => `<div class="history-wrapper"><div class="history-date">📅 历史上的今天</div><div class="history-list">${d.events.map(e => `<div class="history-event"><span class="history-event-year">${e.year}</span><span>${e.desc}</span></div>`).join('')}</div><div class="history-footer">📋 共 ${d.count || d.events.length} 件大事</div></div>`
};

class MyraidBoxCard extends HTMLElement {
  static getConfigElement = () => document.createElement('myraid-box-card-editor');
  static getStubConfig = () => ({ card_type: 'weather', theme: 'sky', auto_rotate: false, rotate_interval: 10 });
  constructor() { super(); this.attachShadow({ mode: 'open' }); this._config = MyraidBoxCard.getStubConfig(); this._data = null; this._timer = null; this._menu = null; this._themeMenu = null; this._card = null; this._boundCardClick = this._handleCardClick.bind(this); this._boundOutsideClick = this._handleOutsideClick.bind(this); }
  setConfig(config) { this._config = { ...this._config, ...config }; this._applyTheme(); this._setupRotate(); this._load(); }
  set hass(hass) { this._hass = hass; !this._data && this._load(); }
  _applyTheme() { let style = this.shadowRoot.querySelector('style'); if (!style) { style = document.createElement('style'); this.shadowRoot.appendChild(style); } style.textContent = getStyles(this._config.theme); }
  _setupRotate() { if (this._timer) clearInterval(this._timer); if (this._config.auto_rotate) { this._timer = setInterval(() => { const types = Object.keys(CARD_TYPES); this._config.card_type = types[(types.indexOf(this._config.card_type) + 1) % types.length]; this._updateDisplay(); }, (this._config.rotate_interval || 10) * 1000); } }
  async _load() { this._showLoading(); const raw = await API.fetch(); if (raw) { this._data = API.parse(raw); this._render(); } else { this._showError(); } }
  async _refresh() { API._cache = null; API._cacheTime = 0; await this._load(); }
  _showLoading() { if (this._card) this._card.innerHTML = '<div class="loading">加载中...</div>'; }
  _showError() { if (this._card) this._card.innerHTML = `<div class="error">⚠️ 数据加载失败<br><button class="retry-btn" data-action="refresh">点击重试</button></div>`; }
  _render() { if (!this._card) { this.shadowRoot.innerHTML = ''; const style = document.createElement('style'); style.textContent = getStyles(this._config.theme); this.shadowRoot.appendChild(style); this._card = document.createElement('ha-card'); this.shadowRoot.appendChild(this._card); this._menu = document.createElement('div'); this._menu.className = 'menu-panel'; this._menu.innerHTML = Object.entries(CARD_TYPES).map(([k, v]) => `<div class="menu-item" data-type="${k}"><span>${v.icon}</span><span>${v.name}</span></div>`).join(''); this.shadowRoot.appendChild(this._menu); this._themeMenu = document.createElement('div'); this._themeMenu.className = 'menu-panel'; this._themeMenu.innerHTML = Object.entries(THEMES).map(([k, v]) => `<div class="menu-item" data-theme="${k}"><span>${v.icon}</span><span>${v.name}</span></div>`).join(''); this.shadowRoot.appendChild(this._themeMenu); this._card.addEventListener('click', this._boundCardClick); this._menu.addEventListener('click', this._handleMenuClick.bind(this)); this._themeMenu.addEventListener('click', this._handleThemeMenuClick.bind(this)); document.addEventListener('click', this._boundOutsideClick); } if (!this._data) { this._card.innerHTML = '<div class="loading">加载中...</div>'; return; } this._updateDisplay(); }
  _handleCardClick(e) { const target = e.target.closest('[data-action]'); if (!target) return; e.stopPropagation(); const action = target.dataset.action; if (action === 'toggle-changelog') { const content = this._card.querySelector('#changelogContent'); if (content) { content.classList.toggle('show'); } } else if (action === 'refresh') { this._refresh(); } else if (action === 'open-theme-menu') { this._showMenu(this._themeMenu, target, 'theme'); } else if (action === 'open-type-menu') { this._showMenu(this._menu, target, 'type'); } }
  _showMenu(menu, btn, menuType) { const rect = btn.getBoundingClientRect(); menu.style.top = `${rect.bottom + CONFIG.MENU_OFFSET}px`; menu.style.left = `${rect.right - CONFIG.MENU_WIDTH}px`; const isOpen = menu.classList.contains('show'); this._closeAllMenus(); if (!isOpen) { menu.classList.add('show'); if (menuType === 'theme') this._themeMenuOpen = true; else this._menuOpen = true; } }
  _closeAllMenus() { this._menu.classList.remove('show'); this._themeMenu.classList.remove('show'); this._menuOpen = false; this._themeMenuOpen = false; }
  _handleMenuClick(e) { e.stopPropagation(); const item = e.target.closest('.menu-item'); if (!item) return; const newType = item.dataset.type; if (newType && this._config.card_type !== newType) { this._config.card_type = newType; this._updateDisplay(); } this._closeAllMenus(); }
  _handleThemeMenuClick(e) { e.stopPropagation(); const item = e.target.closest('.menu-item'); if (!item) return; const newTheme = item.dataset.theme; if (newTheme && this._config.theme !== newTheme) { this._config.theme = newTheme; this._applyTheme(); this._updateDisplay(); } this._closeAllMenus(); }
  _handleOutsideClick(e) { const path = e.composedPath(); const isMenuClick = path.includes(this._menu); const isThemeMenuClick = path.includes(this._themeMenu); const isMenuBtnClick = path.some(node => node?.classList?.contains?.('type-select') || node?.dataset?.action === 'open-type-menu'); const isThemeBtnClick = path.some(node => node?.classList?.contains?.('theme-select') || node?.dataset?.action === 'open-theme-menu'); if (!isMenuClick && !isMenuBtnClick && this._menuOpen) { this._menu.classList.remove('show'); this._menuOpen = false; } if (!isThemeMenuClick && !isThemeBtnClick && this._themeMenuOpen) { this._themeMenu.classList.remove('show'); this._themeMenuOpen = false; } }
  _updateDisplay() { if (!this._data) return; const type = this._config.card_type; const cfg = CARD_TYPES[type]; const data = this._data[type]; let badge = ''; if (type === 'oil' && data.countdown > 0 && data.countdown < 365) badge = `<div class="countdown">⏰ ${data.countdown}天</div>`; const currentTheme = THEMES[this._config.theme] || THEMES.sky; const bodyContent = Render[type](data); this._card.innerHTML = `<div class="head"><div class="head-title">${cfg.icon} ${cfg.name}</div><div class="head-btns">${badge}<div class="refresh-btn" data-action="refresh">🔄</div><div class="theme-select" data-action="open-theme-menu">${currentTheme.icon}</div><div class="type-select" data-action="open-type-menu">▼</div></div></div><div class="body" id="cardBody">${bodyContent}</div>`; }
  disconnectedCallback() { if (this._timer) clearInterval(this._timer); document.removeEventListener('click', this._boundOutsideClick); if (this._card) this._card.removeEventListener('click', this._boundCardClick); }
}

class MyraidBoxCardEditor extends HTMLElement {
  constructor() { super(); this.attachShadow({ mode: 'open' }); this._config = null; this._initialized = false; }
  setConfig(config) { this._config = config; if (this._initialized) this._render(); }
  set hass(hass) { this._hass = hass; if (!this._initialized && this._config) { this._initialized = true; this._render(); } }
  async _render() { if (!this._hass || !customElements.get('ha-form')) { setTimeout(() => this._render(), 100); return; } this.shadowRoot.innerHTML = ''; const form = document.createElement('ha-form'); form.hass = this._hass; form.schema = [ { name: 'card_type', selector: { select: { mode: 'dropdown', options: Object.entries(CARD_TYPES).map(([k, v]) => ({ value: k, label: `${v.icon} ${v.name}` })) } } }, { name: 'theme', selector: { select: { mode: 'dropdown', options: Object.entries(THEMES).map(([k, v]) => ({ value: k, label: `${v.icon} ${v.name}` })) } } }, { name: 'auto_rotate', selector: { boolean: {} } }, { name: 'rotate_interval', selector: { number: { min: 3, max: 60, step: 1, unit_of_measurement: '秒' } } } ]; form.data = this._config ? { ...this._config } : { card_type: 'weather', theme: 'sky', auto_rotate: false, rotate_interval: 10 }; form.computeLabel = (schema) => ({ card_type: '卡片', theme: '主题', auto_rotate: '自动轮播', rotate_interval: '轮播间隔' }[schema.name] || schema.name); form.computeHelper = (schema) => ({ rotate_interval: '仅在启用自动轮播时有效', auto_rotate: '开启后卡片会自动切换类型' }[schema.name] || ''); form.addEventListener('value-changed', (e) => { e.stopPropagation(); const newConfig = { ...this._config, ...e.detail.value }; if (!newConfig.auto_rotate) delete newConfig.rotate_interval; this._config = newConfig; this.dispatchEvent(new CustomEvent('config-changed', { detail: { config: this._config }, bubbles: true, composed: true })); }); this.shadowRoot.appendChild(form); }
}

if (!customElements.get('myraid-box-card')) customElements.define('myraid-box-card', MyraidBoxCard);
if (!customElements.get('myraid-box-card-editor')) customElements.define('myraid-box-card-editor', MyraidBoxCardEditor);

window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === 'myraid-box-card')) { window.customCards.push({ type: 'myraid-box-card', name: '万象盒子', description: '6合1多功能卡片 | 7色相邻渐变主题 | 最终定版', preview: true }); }

console.log('✨ 万象盒子 v2.0.5 已加载（最终定版）');
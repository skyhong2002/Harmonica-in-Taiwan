import { t, getLocale, locales, languageNames } from './i18n.js';
import { esc, icon, link } from './utils.js';

const labels = {
  more: ['More', '更多', 'その他', '더 보기'],
  appearance: ['Appearance', '外觀', '表示設定', '화면 설정'],
  light: ['Light', '淺色', 'ライト', '라이트'],
  dark: ['Dark', '深色', 'ダーク', '다크'],
  system: ['System', '系統', 'システム', '시스템'],
  back: ['Back', '返回', '戻る', '뒤로'],
  home: ['Home', '首頁', 'ホーム', '홈'],
};
const text = (key) => labels[key][Math.max(0, locales.indexOf(getLocale()))];
const themeKey = 'observatory-appearance';
let initialized = false;
let currentTheme = 'system';
function storedTheme() {
  try {
    const value = localStorage.getItem(themeKey) || localStorage.getItem('atlas-theme') || 'system';
    return ['light', 'dark'].includes(value) ? value : 'system';
  } catch { return currentTheme; }
}
function applyTheme(value, persist = false) {
  currentTheme = ['light', 'dark'].includes(value) ? value : 'system';
  if (persist) {
    try { localStorage.setItem(themeKey, currentTheme); } catch {}
  }
  const dark = currentTheme === 'dark' || (currentTheme === 'system' && window.matchMedia?.('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', dark ? '#101310' : '#f6f4ed');
  document.querySelectorAll('[data-theme-choice]').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.themeChoice === currentTheme)));
}
const glyph = (name) => {
  const paths = {
    home: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z"/>',
    posts: '<rect x="4" y="3" width="16" height="18" rx="3"/><path d="M8 8h8M8 12h8M8 16h5"/>',
    sources: '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 5"/>',
    palette: '<path d="M12 21a9 9 0 0 1 0-18c5 0 9 3.6 9 8 0 2.2-2 4-4.5 4H14a2 2 0 0 0-1 3.75A1.3 1.3 0 0 1 12 21Z"/><circle cx="7.5" cy="10.5" r="1"/><circle cx="12" cy="7.5" r="1"/><circle cx="16.5" cy="10.5" r="1"/>',
    filter: '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="2" fill="var(--color-canvas)"/><circle cx="15" cy="17" r="2" fill="var(--color-canvas)"/>',
    harmonica: '<rect x="2" y="6" width="20" height="12" rx="3"/><path d="M2 9h20M2 15h20M6 9v6M10 9v6M14 9v6M18 9v6"/>',
  };
  return paths[name] ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]}</svg>` : icon(name);
};
const navIcons = { discover: 'home', posts: 'posts', events: 'calendar', sources: 'sources', scores: 'music', scoreSources: 'layers', feeds: 'rss', status: 'info', contribute: 'heart', submit: 'plus', about: 'info', privacy: 'info' };
function active(url, current) {
  return current === url || (url === '/source/' && current.startsWith('/source/')) || (url === '/scores/' && current.startsWith('/scores/'));
}
function navLink(url, key, current, extra = '') {
  const label = key === 'discover' ? text('home') : t(key);
  return `<a href="${url}" class="nav-item ${extra}" title="${esc(label)}" ${active(url, current) ? 'aria-current="page"' : ''}>${glyph(navIcons[key])}<span class="nav-label">${label}</span></a>`;
}
export function navigation(current = location.pathname, routes = {}) {
  const primary = [['/post/', 'posts'], ['/source/', 'sources'], ['/scores/', 'scores'], ['/status/', 'status'], ['/submit/', 'submit']];
  const extras = Object.entries(routes).filter(([url]) => url !== '/' && !primary.some(([p]) => p === url));
  const brand = t('brand');
  return `<a class="skip-link" href="#main">${t('skip')}</a><header class="site-header legacy-site-header"><a class="brand" href="/" aria-label="${esc(brand)}"><span class="brand-mark"><img src="/web/assets/observatory-mark.svg" width="34" height="34" alt="" aria-hidden="true"></span><span class="brand-name">${esc(brand)}</span></a><nav class="site-nav" aria-label="${t('navigation')}">${primary.map(([url, key]) => navLink(url, key, current)).join('')}<details class="nav-more"><summary class="nav-item" title="${text('more')}">${glyph('menu')}<span class="nav-label">${text('more')}</span></summary><div class="nav-more-menu"><div data-shell-panel="main">${extras.map(([url, key]) => `<a href="${url}" ${active(url,current) ? 'aria-current="page"' : ''}>${glyph(navIcons[key])}<span>${t(key)}</span></a>`).join('')}<button class="appear-open" data-shell-action="appearance">${glyph('palette')}<span>${text('appearance')}</span>${glyph('chevron')}</button><label class="language-picker" for="language-select">${t('language')}<select id="language-select">${locales.map((locale) => `<option value="${locale}" ${locale === getLocale() ? 'selected' : ''}>${languageNames[locale]}</option>`).join('')}</select></label></div><div data-shell-panel="appearance" hidden><div class="appear-head"><button class="appear-back" data-shell-action="back" aria-label="${text('back')}">←</button><strong>${text('appearance')}</strong></div><div class="appear-seg">${['light', 'dark', 'system'].map((theme) => `<button data-theme-choice="${theme}" aria-pressed="${theme === storedTheme()}">${text(theme)}</button>`).join('')}</div></div></div></details></nav></header>`;
}
export function footer() {
  return `<footer class="site-footer"><div class="footer-links">${[['/about/', 'about'], ['/privacy/', 'privacy'], ['/status/', 'status'], ['/feeds/', 'feeds'], ['/submit/', 'submit'], ['/scores/sources/', 'scoreSources']].map(([url, key]) => link(url, t(key))).join('')}</div><div class="footer-bottom"><span>© ${new Date().getFullYear()} ${esc(t('brand'))}</span>${link('https://github.com/skyhong2002/chumei', t('credit'))}${link('/api/v1/catalog', t('dataLink'))}</div></footer>`;
}
export function initializeShell() {
  applyTheme(storedTheme());
  if (initialized) return;
  initialized = true;
  const initialAction = new URLSearchParams(location.search).get('focus');
  if (['search', 'filter'].includes(initialAction)) {
    const restoreControl = () => {
      if (!focusPageControl(initialAction)) return;
      observer.disconnect();
      const url = new URL(location.href);
      url.searchParams.delete('focus');
      window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash);
    };
    const observer = new window.MutationObserver(restoreControl);
    observer.observe(document.querySelector('#app') || document.body, { childList: true, subtree: true });
    restoreControl();
  }
  window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener?.('change', () => { if (storedTheme() === 'system') applyTheme('system'); });
  window.addEventListener('storage', (event) => { if (event.key === themeKey) applyTheme(storedTheme()); });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    const more = document.querySelector('.nav-more[open]');
    if (more) { more.open = false; more.querySelector('summary')?.focus(); }
  });
  document.addEventListener('click', (event) => {
    const more = document.querySelector('.nav-more[open]');
    if (more && !more.contains(event.target)) more.open = false;
  });
  document.addEventListener('toggle', (event) => {
    if (event.target.matches?.('.nav-more') && !event.target.open) {
      event.target.querySelector('[data-shell-panel="main"]').hidden = false;
      event.target.querySelector('[data-shell-panel="appearance"]').hidden = true;
    }
  }, true);
}
export function handleShellClick(event) {
  const theme = event.target.closest('[data-theme-choice]');
  if (theme) { applyTheme(theme.dataset.themeChoice, true); return true; }
  const action = event.target.closest('[data-shell-action]')?.dataset.shellAction;
  if (!action) return false;
  if (action === 'appearance' || action === 'back') {
    document.querySelector('[data-shell-panel="main"]').hidden = action === 'appearance';
    document.querySelector('[data-shell-panel="appearance"]').hidden = action !== 'appearance';
    return true;
  }
  if (!focusPageControl(action)) {
    location.href = '/post/?lang=' + encodeURIComponent(getLocale()) + '&focus=' + action;
  }
  return true;
}
function focusPageControl(action) {
  const main = document.querySelector('#main');
  const riverPicker = main?.querySelector(window.matchMedia?.('(max-width: 699px)').matches ? '.river-mobile .col-picker' : '.feed-cols .col-picker');
  if (riverPicker) {
    riverPicker.open = true;
    riverPicker.querySelector(action === 'search' ? 'input[data-river-field="q"]' : 'select[data-river-field="country"]')?.focus();
    return true;
  }
  const filter = main?.querySelector('.filter-bar');
  const search = main?.querySelector('input[type="search"]');
  if (action === 'search' && search) {
    for (let el = search.parentElement; el && el !== main; el = el.parentElement) { if (el.tagName === 'DETAILS') el.open = true; }
    search.focus();
    search.scrollIntoView?.({ block: 'center', behavior: 'smooth' });
    return true;
  }
  if (filter) {
    const details = filter.closest('details');
    if (details) details.open = true;
    filter.scrollIntoView?.({ block: 'start', behavior: 'smooth' });
    (filter.querySelector('select[data-filter="country"]') || filter.querySelector('select, input, button'))?.focus();
    return true;
  }
  return false;
}

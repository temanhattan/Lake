import { lakeLoader } from './lake-loader.js';

const DEMO_KEY = 'lake-demo-mode';
const START_KEY = 'lake-welcome-started';
const SEEN_KEY = 'lake-welcome-seen';
const SUMMARY_SHORT = 96;
const ROTATE_MS = 7200;
const L_PATH = 'M240 281 C224 280 216 296 215 323 C214 354 214 379 222 392 C232 430 221 480 221 519 M222 392 C204 399 181 406 158 409 M221 519 C219 540 204 561 188 562 C172 562 164 549 168 534 C172 517 188 514 200 520 C215 526 220 542 235 551';

const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[char]);
const oneLine = value => String(value ?? '').replace(/\s+/g, ' ').trim();
const isTypingTarget = target => target instanceof HTMLElement &&
  (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName));

function lakeLogo() {
  // One logo component; replace this SVG body when the handwritten wordmark is ready.
  return `<span class="welcome-logo" id="welcome-logo" aria-label="Lake"><svg class="brand-mark" viewBox="145 270 150 310" aria-hidden="true"><path d="${L_PATH}"/></svg></span>`;
}

function hashHue(value) {
  let hash = 2166136261;
  for (const char of value || 'Lake') hash = Math.imul(hash ^ char.charCodeAt(0), 16777619);
  return (hash >>> 0) % 360;
}

function cardMarkup(tile, featured, index) {
  const title = esc(tile.title || 'Untitled conversation');
  const summary = oneLine(tile.summary);
  const shortSummary = summary.length > SUMMARY_SHORT ? `${summary.slice(0, SUMMARY_SHORT).trimEnd()}…` : summary;
  const tags = Array.isArray(tile.tags) ? tile.tags.slice(0, 3) : [];
  const accentKey = tile.project || tags[0] || 'Lake';
  const date = tile.date ? new Date(tile.date).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '';
  const label = `Open chat: ${oneLine(tile.title)}. ${summary}`;
  // Keep this deterministic 1×1 / 2×1 / 1×2 cycle in sync with welcome.css and README.md.
  const sizePattern = ['square', 'wide', 'tall', 'square', 'wide', 'square', 'tall', 'square'];
  const size = featured ? 'featured' : sizePattern[index % sizePattern.length];
  return `<button class="welcome-card welcome-card--${size}${featured ? ' is-featured' : ''}" type="button" data-chat-id="${esc(tile.id)}" aria-label="${esc(label)}" style="--tile-hue:${hashHue(accentKey)};--reveal-index:${Math.min(index, 18)}">
    <span class="welcome-card__accent" aria-hidden="true"></span>
    <span class="welcome-card__head"><span class="welcome-card__project">${esc(tile.project || 'Lake library')}</span>${tile.model ? `<span class="welcome-card__model">${esc(tile.model)}</span>` : ''}</span>
    <span class="welcome-card__title">${title}</span>
    <span class="welcome-card__summary-short">${esc(shortSummary)}</span>
    <span class="welcome-card__summary-full">${esc(summary)}</span>
    <span class="welcome-card__foot">${date ? `<time>${esc(date)}</time>` : '<span>Saved conversation</span>'}<span class="welcome-card__tags">${tags.map(tag => `<span class="welcome-tag">${esc(tag)}</span>`).join('')}</span></span>
  </button>`;
}

function loadWelcomeStyle() {
  if (document.querySelector('#lake-welcome-style')) return Promise.resolve();
  return new Promise(resolve => {
    const link = document.createElement('link');
    link.id = 'lake-welcome-style'; link.rel = 'stylesheet'; link.href = '/static/welcome.css';
    link.onload = resolve; link.onerror = resolve;
    document.head.append(link);
  });
}

export async function startWelcome() {
  void loadWelcomeStyle();
  const view = document.querySelector('#welcome-view');
  if (!view) return;
  document.body.classList.add('lake-welcome-active');
  document.querySelector('#home-view')?.setAttribute('hidden', '');
  document.querySelector('#reader')?.setAttribute('hidden', '');
  document.querySelector('#design-view')?.setAttribute('hidden', '');
  document.querySelector('.skip-link')?.setAttribute('tabindex', '-1');
  document.querySelector('.topbar .brand')?.setAttribute('tabindex', '-1');
  view.hidden = false;
  document.title = 'Lake — Your conversations, close at hand';

  const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
  let demoMode = localStorage.getItem(DEMO_KEY) === '1';
  let tiles = [];
  let featuredIndex = 0;
  let rotationTimer = 0;
  let rotationPaused = false;
  let exitTimer = 0;
  let introPlayed = sessionStorage.getItem(SEEN_KEY) === '1';
  let fetchSequence = 0;
  let fetchController = null;
  let loadingTimer = 0;

  view.innerHTML = `<div class="welcome-page${introPlayed ? ' is-ready' : ' is-intro'}">
    <section class="welcome-intro" aria-labelledby="welcome-title">
      <div class="welcome-brand-row">${lakeLogo()}<span class="welcome-brand-name">Lake</span><span class="eyebrow">YOUR LOCAL CHAT GALLERY</span></div>
      <div class="welcome-copy"><h1 id="welcome-title">Good work,<br><em>kept close.</em></h1><p>Find the fixes and decisions you have already figured out. Your conversations stay on this device.</p></div>
      <div class="welcome-startbar"><button class="primary welcome-start" id="welcome-start" type="button">Start <span aria-hidden="true">→</span></button></div>
    </section>
    <section class="welcome-wall-wrap" aria-label="A selection of your chats">
      <div class="welcome-wall-status" id="welcome-wall-status" role="status" aria-live="polite"></div>
      <div class="welcome-wall" id="welcome-wall" role="group" aria-label="Chat gallery"></div>
    </section>
    <section class="welcome-controls" aria-label="Welcome preferences">
      <div class="welcome-demo-row"><label class="welcome-toggle"><input id="welcome-demo-toggle" type="checkbox"><span class="toggle-switch" aria-hidden="true"></span><span>Demo mode</span></label><span class="demo-shortcut">Press D to toggle</span><span class="real-chat-indicator" id="real-chat-indicator" hidden>Real chats visible</span></div>
      <label class="welcome-toggle welcome-launch-toggle"><input id="welcome-launch-toggle" type="checkbox"><span class="toggle-switch" aria-hidden="true"></span><span>Show welcome on launch</span></label>
      <div class="welcome-display-controls"><button class="quiet-link welcome-theme-toggle" id="welcome-theme-toggle" type="button">Theme: <span id="welcome-theme-label"></span></button><button class="quiet-link welcome-motion-toggle" id="welcome-motion-toggle" type="button">Motion: <span id="welcome-motion-label"></span></button></div>
      <a class="welcome-skip" href="/">Skip to your library</a>
    </section>
    <div class="welcome-import" id="welcome-import" hidden><p>Looking for a first look?</p><a class="secondary" id="welcome-import-link" href="/?import=1">Import your first export</a></div>
  </div>`;

  const page = view.querySelector('.welcome-page');
  const wall = view.querySelector('#welcome-wall');
  const status = view.querySelector('#welcome-wall-status');
  const startButton = view.querySelector('#welcome-start');
  const demoToggle = view.querySelector('#welcome-demo-toggle');
  const launchToggle = view.querySelector('#welcome-launch-toggle');
  const themeButton = view.querySelector('#welcome-theme-toggle');
  const motionButton = view.querySelector('#welcome-motion-toggle');
const reduced = () => preference.matches || localStorage.getItem('lake-motion') === 'reduced';
  document.documentElement.dataset.motion = reduced() ? 'reduced' : 'full';

  function updatePreferences() {
    demoToggle.checked = demoMode;
    launchToggle.checked = localStorage.getItem('lake-welcome-on-launch') !== '0';
    const theme = document.documentElement.dataset.theme || 'light';
    view.querySelector('#welcome-theme-label').textContent = theme === 'dark' ? 'Dark' : 'Light';
    view.querySelector('#welcome-motion-label').textContent = reduced() ? 'Reduced' : 'Full';
    const realVisible = !demoMode && tiles.some(tile => !String(tile.id).startsWith('sample-'));
    view.querySelector('#real-chat-indicator').hidden = !realVisible;
  }

  function renderWall() {
    if (!tiles.length) {
      wall.innerHTML = '<div class="welcome-empty"><p>No chat summaries are available yet.</p><a class="secondary" href="/?import=1">Import your first export</a></div>';
      return;
    }
    featuredIndex %= tiles.length;
    const feature = tiles[featuredIndex];
    const others = tiles.filter((_, index) => index !== featuredIndex);
    wall.innerHTML = cardMarkup(feature, true, 0) + others.map((tile, index) => cardMarkup(tile, false, index)).join('');
    const isSamples = tiles.every(tile => String(tile.id).startsWith('sample-'));
    view.querySelector('#welcome-import').hidden = demoMode || !isSamples;
  }

  function stopRotation() {
    clearTimeout(rotationTimer);
    rotationTimer = 0;
  }

  function scheduleRotation() {
    stopRotation();
    if (reduced() || rotationPaused || document.hidden || tiles.length < 2 || page.classList.contains('is-exiting')) return;
    rotationTimer = window.setTimeout(() => {
      wall.classList.add('is-switching');
      window.setTimeout(() => {
        featuredIndex = (featuredIndex + 1) % tiles.length;
        renderWall();
        window.setTimeout(() => wall.classList.remove('is-switching'), 20);
        scheduleRotation();
      }, 180);
    }, ROTATE_MS);
  }

  async function fetchTiles() {
    const requestId = ++fetchSequence;
    fetchController?.abort();
    fetchController = new AbortController();
    tiles = [];
    featuredIndex = 0;
    renderWall();
    status.replaceChildren(lakeLoader({ size: 'sm', label: 'Loading chat gallery' }), document.createTextNode(' Loading your gallery…'));
    let loaderVisible = false;
    loadingTimer = window.setTimeout(() => {
      if (requestId !== fetchSequence) return;
      loaderVisible = true;
      status.hidden = false;
      window.setTimeout(() => {
        if (requestId === fetchSequence && loaderVisible && !status.hidden) {
          status.textContent = 'Preparing your gallery…';
        }
      }, 1100);
    }, 80);
    try {
      const response = await fetch(`/api/welcome/tiles?demo=${demoMode ? '1' : '0'}`, { cache: 'no-store', signal: fetchController.signal });
      if (!response.ok) throw new Error('The gallery could not be loaded.');
      const result = await response.json();
      if (requestId !== fetchSequence) return;
      tiles = Array.isArray(result) ? result.slice(0, 24) : [];
      status.replaceChildren(); status.hidden = true;
    } catch {
      if (requestId !== fetchSequence) return;
      tiles = [];
      status.textContent = 'Lake could not reach its local library. You can still Start or import an export.';
      status.hidden = false;
    } finally {
      if (requestId === fetchSequence) clearTimeout(loadingTimer);
    }
    if (requestId !== fetchSequence) return;
    renderWall();
    updatePreferences();
    if (loaderVisible && status.textContent.includes('Loading')) status.hidden = true;
    scheduleRotation();
  }

  function setDemoMode(nextValue, persist = true) {
    const next = Boolean(nextValue);
    if (next === demoMode) return;
    demoMode = next;
    if (persist) localStorage.setItem(DEMO_KEY, demoMode ? '1' : '0');
    fetchController?.abort(); ++fetchSequence;
    tiles = [];
    view.querySelector('#welcome-import').hidden = true;
    renderWall(); updatePreferences();
    void fetchTiles();
  }

  function enterApp(chatId = '', importFirst = false, immediate = false) {
    clearTimeout(exitTimer);
    sessionStorage.setItem(START_KEY, '1');
    sessionStorage.setItem(SEEN_KEY, '1');
    stopRotation();
    const logo = view.querySelector('#welcome-logo');
    const headerMark = document.querySelector('.topbar .brand-mark');
    if (!reduced() && logo && headerMark) {
      const from = logo.getBoundingClientRect(), to = headerMark.getBoundingClientRect();
      page.style.setProperty('--logo-dx', `${to.left - from.left}px`);
      page.style.setProperty('--logo-dy', `${to.top - from.top}px`);
      page.style.setProperty('--logo-scale', `${Math.max(.45, Math.min(1, to.width / Math.max(1, from.width)))}`);
    }
    page.classList.add('is-exiting');
    exitTimer = window.setTimeout(() => {
      const url = new URL('/', location.href);
      if (chatId) url.searchParams.set('chat', chatId);
      if (importFirst) url.searchParams.set('import', '1');
      location.href = url.pathname + url.search;
    }, immediate || reduced() ? 0 : 320);
  }

  startButton.addEventListener('click', () => enterApp());
  view.querySelector('.welcome-skip').addEventListener('click', event => { event.preventDefault(); enterApp('', false, true); });
  view.querySelector('#welcome-import-link').addEventListener('click', event => { event.preventDefault(); enterApp('', true, true); });
  wall.addEventListener('click', event => {
    const button = event.target.closest('[data-chat-id]');
    if (button) enterApp(button.dataset.chatId, false, true);
  });
  wall.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
    const current = event.target.closest('[data-chat-id]');
    if (!current) return;
    event.preventDefault();
    const buttons = [...wall.querySelectorAll('[data-chat-id]')];
    const rect = current.getBoundingClientRect();
    const cx = rect.left + rect.width / 2, cy = rect.top + rect.height / 2;
    const sign = event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1 : 1;
    const horizontal = event.key === 'ArrowLeft' || event.key === 'ArrowRight';
    const options = buttons.filter(button => button !== current).map(button => {
      const r = button.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
      const primary = horizontal ? (x - cx) * sign : (y - cy) * sign;
      const secondary = horizontal ? Math.abs(y - cy) : Math.abs(x - cx);
      return { button, primary, secondary };
    }).filter(item => item.primary > 0).sort((a, b) => a.secondary - b.secondary || a.primary - b.primary);
    const fallback = buttons[(buttons.indexOf(current) + sign + buttons.length) % buttons.length];
    (options[0]?.button || fallback)?.focus();
  });
  wall.addEventListener('mouseenter', () => { rotationPaused = true; stopRotation(); });
  wall.addEventListener('mouseleave', () => { rotationPaused = false; scheduleRotation(); });
  wall.addEventListener('focusin', () => { rotationPaused = true; stopRotation(); });
  wall.addEventListener('focusout', event => {
    if (!wall.contains(event.relatedTarget)) { rotationPaused = false; scheduleRotation(); }
  });
  document.addEventListener('visibilitychange', () => document.hidden ? stopRotation() : scheduleRotation());
  demoToggle.addEventListener('change', () => setDemoMode(demoToggle.checked));
  window.addEventListener('storage', event => {
    if (event.key === DEMO_KEY) setDemoMode(event.newValue === '1', false);
  });
  window.addEventListener('pageshow', () => {
    document.title = 'Lake — Your conversations, close at hand';
    setDemoMode(localStorage.getItem(DEMO_KEY) === '1', false);
  });
  launchToggle.addEventListener('change', () => localStorage.setItem('lake-welcome-on-launch', launchToggle.checked ? '1' : '0'));
  themeButton.addEventListener('click', () => {
    const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('lake-theme', theme); document.documentElement.dataset.theme = theme; updatePreferences();
  });
  motionButton.addEventListener('click', () => {
    const value = reduced() ? 'full' : 'reduced';
    localStorage.setItem('lake-motion', value); document.documentElement.dataset.motion = value; updatePreferences();
    if (value === 'reduced') stopRotation(); else scheduleRotation();
  });
  preference.addEventListener('change', () => {
    document.documentElement.dataset.motion = reduced() ? 'reduced' : 'full';
    updatePreferences();
    if (reduced()) stopRotation(); else scheduleRotation();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); enterApp('', false, true); }
    if (event.key.toLowerCase() === 'd' && !event.altKey && !event.ctrlKey && !event.metaKey && !isTypingTarget(event.target)) {
      demoToggle.checked = !demoToggle.checked; demoToggle.dispatchEvent(new Event('change'));
    }
  });

  updatePreferences();
  status.hidden = true;
  await fetchTiles();
  if (!introPlayed) {
    sessionStorage.setItem(SEEN_KEY, '1');
    window.setTimeout(() => page.classList.add('is-ready'), 45);
  }
}

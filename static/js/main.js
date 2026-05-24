// ============================================
// TEZAURUS - Enhanced JS with Theme Customizer
// ============================================

document.addEventListener('DOMContentLoaded', function () {

  // ---- Mobile Menu ----
  const navToggle = document.getElementById('navToggle');
  const navMenu = document.getElementById('navMenu');

  if (navToggle) {
    navToggle.addEventListener('click', function () {
      navMenu.classList.toggle('active');
    });
  }

  // ---- Navbar Search Autocomplete ----
  const searchInput = document.getElementById('searchInput');
  const suggestionsBox = document.getElementById('suggestionsBox');

  if (searchInput) {
    let debounceTimer;

    searchInput.addEventListener('input', function () {
      clearTimeout(debounceTimer);
      const query = this.value.trim();

      if (query.length < 2) {
        suggestionsBox.style.display = 'none';
        return;
      }

      debounceTimer = setTimeout(() => {
        fetch(`/api/search?q=${encodeURIComponent(query)}`)
          .then(res => res.json())
          .then(suggestions => {
            if (suggestions.length > 0) {
              suggestionsBox.innerHTML = suggestions
                .map(word => `<div class="suggestion-item" onclick="selectSuggestion('${word}')">${word}</div>`)
                .join('');
              suggestionsBox.style.display = 'block';
            } else {
              suggestionsBox.style.display = 'none';
            }
          })
          .catch(() => { suggestionsBox.style.display = 'none'; });
      }, 300);
    });

    document.addEventListener('click', function (e) {
      if (!e.target.closest('.nav-search')) {
        suggestionsBox.style.display = 'none';
      }
    });
  }

  // ---- Init Customizer ----
  initCustomizer();
});

function selectSuggestion(word) {
  const searchInput = document.getElementById('searchInput');
  const suggestionsBox = document.getElementById('suggestionsBox');
  if (searchInput) {
    searchInput.value = word;
    suggestionsBox.style.display = 'none';
    window.location.href = `/search?q=${encodeURIComponent(word)}`;
  }
}

// ============================================
// THEME CUSTOMIZER
// ============================================

const THEMES = [
  { id: 'default', label: 'Default', colors: ['#667eea', '#764ba2'] },
  { id: 'ocean', label: 'Ocean', colors: ['#0c4a6e', '#164e63'] },
  { id: 'forest', label: 'Forest', colors: ['#052e16', '#14532d'] },
  { id: 'sunset', label: 'Sunset', colors: ['#7c2d12', '#9333ea'] },
  { id: 'midnight', label: 'Midnight', colors: ['#0f0f23', '#1e1b4b'] },
  { id: 'rose', label: 'Rose', colors: ['#881337', '#c2410c'] },
  { id: 'light', label: 'Light', colors: ['#f1f5f9', '#e2e8f0'] },
];

const BG_PATTERNS = [
  { id: 'none', label: 'None', icon: '◻️' },
  { id: 'particles', label: 'Dots', icon: '⋯' },
  { id: 'grid', label: 'Grid', icon: '⊞' },
  { id: 'waves', label: 'Lines', icon: '≡' },
  { id: 'bokeh', label: 'Bokeh', icon: '◉' },
];

const RADIUS_OPTIONS = [
  { id: 'sharp', label: 'Sharp', value: '4px' },
  { id: 'rounded', label: 'Rounded', value: '16px' },
  { id: 'pill', label: 'Pill', value: '28px' },
];

function initCustomizer() {
  // Inject HTML
  document.body.insertAdjacentHTML('beforeend', buildCustomizerHTML());

  // Load saved preferences
  const prefs = loadPrefs();
  applyPrefs(prefs);

  // Bind events
  document.getElementById('themeBtn').addEventListener('click', openCustomizer);
  document.getElementById('customizerClose').addEventListener('click', closeCustomizer);
  document.getElementById('customizerOverlay').addEventListener('click', closeCustomizer);
  document.getElementById('customizerReset').addEventListener('click', resetPrefs);

  // Theme swatches
  document.querySelectorAll('.swatch').forEach(el => {
    el.addEventListener('click', () => {
      const theme = el.dataset.theme;
      saveAndApply({ ...loadPrefs(), theme });
      updateActiveSwatch(theme);
    });
  });

  // BG options
  document.querySelectorAll('.bg-opt').forEach(el => {
    el.addEventListener('click', () => {
      const bg = el.dataset.bg;
      saveAndApply({ ...loadPrefs(), bg });
      updateActiveBg(bg);
    });
  });

  // Radius options
  document.querySelectorAll('.radius-opt').forEach(el => {
    el.addEventListener('click', () => {
      const radius = el.dataset.radius;
      saveAndApply({ ...loadPrefs(), radius });
      updateActiveRadius(radius);
    });
  });

  // Font size slider
  const slider = document.getElementById('fontSizeSlider');
  if (slider) {
    slider.addEventListener('input', () => {
      const size = slider.value;
      document.documentElement.style.fontSize = size + 'px';
      saveAndApply({ ...loadPrefs(), fontSize: size });
    });
  }
}

function buildCustomizerHTML() {
  const themeSwatches = THEMES.map(t => `
    <div>
      <div class="swatch" data-theme="${t.id}" style="background: linear-gradient(135deg, ${t.colors[0]}, ${t.colors[1]})"></div>
      <div class="swatch-label">${t.label}</div>
    </div>
  `).join('');

  const bgOptions = BG_PATTERNS.map(b => `
    <button class="bg-opt" data-bg="${b.id}">
      <span class="bg-icon">${b.icon}</span>
      ${b.label}
    </button>
  `).join('');

  const radiusOptions = RADIUS_OPTIONS.map(r => `
    <button class="radius-opt" data-radius="${r.id}" style="border-radius: ${r.value}">
      ${r.label}
    </button>
  `).join('');

  return `
    <div class="customizer-overlay" id="customizerOverlay"></div>
    <div class="customizer-panel" id="customizerPanel">
      <div class="customizer-header">
        <h3>🎨 Dizayn sozlamalari</h3>
        <button class="customizer-close" id="customizerClose">✕</button>
      </div>

      <div class="customizer-section">
        <h4>🎨 Rang sxemasi</h4>
        <div class="theme-swatches">${themeSwatches}</div>
      </div>

      <div class="customizer-section">
        <h4>🖼️ Fon naqshi</h4>
        <div class="bg-options">${bgOptions}</div>
      </div>

      <div class="customizer-section">
        <h4>⬛ Burchak shakli</h4>
        <div class="radius-options">${radiusOptions}</div>
      </div>

      <div class="customizer-section">
        <h4>🔤 Matn o'lchami</h4>
        <input type="range" class="font-slider" id="fontSizeSlider" min="13" max="18" step="0.5" value="15">
        <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:#94a3b8; margin-top:0.3rem">
          <span>Kichik</span><span>Katta</span>
        </div>
      </div>

      <button class="reset-btn" id="customizerReset">↺ Qayta tiklash</button>
    </div>
  `;
}

function openCustomizer() {
  document.getElementById('customizerPanel').classList.add('open');
  document.getElementById('customizerOverlay').classList.add('open');
}

function closeCustomizer() {
  document.getElementById('customizerPanel').classList.remove('open');
  document.getElementById('customizerOverlay').classList.remove('open');
}

function loadPrefs() {
  try {
    return JSON.parse(localStorage.getItem('tezaurus_prefs') || '{}');
  } catch { return {}; }
}

function saveAndApply(prefs) {
  try { localStorage.setItem('tezaurus_prefs', JSON.stringify(prefs)); } catch {}
  applyPrefs(prefs);
}

function applyPrefs(prefs) {
  const theme = prefs.theme || 'default';
  const bg = prefs.bg || 'none';
  const radius = prefs.radius || 'rounded';
  const fontSize = prefs.fontSize || 15;

  // Theme
  document.documentElement.dataset.theme = theme === 'default' ? '' : theme;

  // Background
  const body = document.body;
  body.dataset.bg = bg === 'none' ? '' : bg;
  if (bg === 'none') delete body.dataset.bg;

  // Border Radius
  const radiusMap = { sharp: '4px', rounded: '16px', pill: '28px' };
  document.documentElement.style.setProperty('--radius', radiusMap[radius] || '16px');

  // Font Size
  document.documentElement.style.fontSize = fontSize + 'px';

  // Update slider
  const slider = document.getElementById('fontSizeSlider');
  if (slider) slider.value = fontSize;

  updateActiveSwatch(theme);
  updateActiveBg(bg);
  updateActiveRadius(radius);
}

function resetPrefs() {
  try { localStorage.removeItem('tezaurus_prefs'); } catch {}
  applyPrefs({});
}

function updateActiveSwatch(active) {
  document.querySelectorAll('.swatch').forEach(el => {
    el.classList.toggle('active', el.dataset.theme === active);
  });
}

function updateActiveBg(active) {
  document.querySelectorAll('.bg-opt').forEach(el => {
    el.classList.toggle('active', el.dataset.bg === active);
  });
}

function updateActiveRadius(active) {
  document.querySelectorAll('.radius-opt').forEach(el => {
    el.classList.toggle('active', el.dataset.radius === active);
  });
}
// ============================================================ Helpers API
const api = {
  get: (url) => fetch(url).then(r => r.json()),
  post: (url, body) => fetch(url, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}),
  }).then(r => r.json()),
  put: (url, body) => fetch(url, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}),
  }).then(r => r.json()),
  del: (url) => fetch(url, { method: "DELETE" }).then(r => r.json()),
  upload: (url, formData) => fetch(url, { method: "POST", body: formData }).then(r => r.json()),
};

// ============================================================ Debounce (avoids one request per keystroke)
function debounce(fn, delayMs) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delayMs);
  };
}

// ============================================================ HTML escaping
// Game titles, reviews, notes, and other free-text fields are user-controlled
// data — they can arrive not just from typing in the UI but from an
// imported Excel file (someone else's spreadsheet, possibly crafted
// maliciously). Every one of them gets interpolated into innerHTML template
// strings throughout this file, so anything that isn't run through this
// first is a stored-XSS opening (e.g. a title of
// `<img src=x onerror="...">` would otherwise execute as real HTML the
// moment a grid tile renders it). Safe for both text-content and
// attribute-value (`value="..."`) contexts.
function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// ============================================================ Markdown (lightweight, no dependency)
function mdToHtml(text) {
  if (!text) return "";
  let escaped = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  escaped = escaped.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  escaped = escaped.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, "<em>$1</em>");
  const lines = escaped.split("\n");
  let html = "", inList = false;
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("- ")) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += `<li>${trimmed.slice(2)}</li>`;
    } else {
      if (inList) { html += "</ul>"; inList = false; }
      if (trimmed === "") html += "<br>";
      else html += `<p>${trimmed}</p>`;
    }
  }
  if (inList) html += "</ul>";
  return html;
}

// ============================================================ Themes
// Every theme sets both the accent colors AND the background/text colors —
// text colors used to be fixed at :root regardless of theme, which meant
// light themes were unreadable (light background, light text). Each entry
// is self-contained and safe to apply on its own.
const THEMES = {
  // ---- Dark (10) ----
  violet: { mode: "dark", "--accent": "#7c5cff", "--accent-2": "#c9ff5e", "--accent-soft": "#7c5cff26", "--bg": "#121319", "--bg-elevated": "#191b23", "--bg-card": "#1f212b", "--bg-card-hover": "#262835", "--border": "#2b2e3a", "--text": "#edeef4", "--text-muted": "#8d92a6", "--text-faint": "#5f6376" },
  emerald: { mode: "dark", "--accent": "#2fae72", "--accent-2": "#a8ff9e", "--accent-soft": "#2fae7226", "--bg": "#0e1613", "--bg-elevated": "#14201a", "--bg-card": "#192721", "--bg-card-hover": "#20332b", "--border": "#233830", "--text": "#edeef4", "--text-muted": "#8d92a6", "--text-faint": "#5f6376" },
  amber: { mode: "dark", "--accent": "#e8973b", "--accent-2": "#ffd76e", "--accent-soft": "#e8973b26", "--bg": "#17130f", "--bg-elevated": "#1e1811", "--bg-card": "#251d15", "--bg-card-hover": "#2d2419", "--border": "#392c1c", "--text": "#edeef4", "--text-muted": "#8d92a6", "--text-faint": "#5f6376" },
  contrast: { mode: "dark", "--accent": "#00e0ff", "--accent-2": "#f5ff3d", "--accent-soft": "#00e0ff26", "--bg": "#000000", "--bg-elevated": "#0c0c0c", "--bg-card": "#131313", "--bg-card-hover": "#1c1c1c", "--border": "#2e2e2e", "--text": "#f5f5f5", "--text-muted": "#a8a8a8", "--text-faint": "#707070" },
  rose: { mode: "dark", "--accent": "#ff6fa8", "--accent-2": "#ffc2dd", "--accent-soft": "#ff6fa826", "--bg": "#171015", "--bg-elevated": "#1e151b", "--bg-card": "#261a21", "--bg-card-hover": "#2f2029", "--border": "#3a2530", "--text": "#edeef4", "--text-muted": "#8d92a6", "--text-faint": "#5f6376" },
  ocean: { mode: "dark", "--accent": "#3fa9f5", "--accent-2": "#7fe6e0", "--accent-soft": "#3fa9f526", "--bg": "#0c1420", "--bg-elevated": "#101c2c", "--bg-card": "#152537", "--bg-card-hover": "#1b3044", "--border": "#213a50", "--text": "#edeef4", "--text-muted": "#8d92a6", "--text-faint": "#5f6376" },
  "gruvbox-dark": { mode: "dark", "--accent": "#fe8019", "--accent-2": "#fabd2f", "--accent-soft": "#fe801926", "--bg": "#282828", "--bg-elevated": "#32302f", "--bg-card": "#3c3836", "--bg-card-hover": "#45403d", "--border": "#504945", "--text": "#ebdbb2", "--text-muted": "#bdae93", "--text-faint": "#8a7f6c" },
  dracula: { mode: "dark", "--accent": "#bd93f9", "--accent-2": "#50fa7b", "--accent-soft": "#bd93f926", "--bg": "#282a36", "--bg-elevated": "#21222c", "--bg-card": "#343746", "--bg-card-hover": "#3d4052", "--border": "#44475a", "--text": "#f8f8f2", "--text-muted": "#b6b8c2", "--text-faint": "#7d8098" },
  nord: { mode: "dark", "--accent": "#88c0d0", "--accent-2": "#a3be8c", "--accent-soft": "#88c0d026", "--bg": "#2e3440", "--bg-elevated": "#272c36", "--bg-card": "#3b4252", "--bg-card-hover": "#434c5e", "--border": "#4c566a", "--text": "#eceff4", "--text-muted": "#b8c0d0", "--text-faint": "#7f8aa3" },
  "catppuccin-mocha": { mode: "dark", "--accent": "#cba6f7", "--accent-2": "#a6e3a1", "--accent-soft": "#cba6f726", "--bg": "#1e1e2e", "--bg-elevated": "#181825", "--bg-card": "#313244", "--bg-card-hover": "#3a3c4e", "--border": "#45475a", "--text": "#cdd6f4", "--text-muted": "#a6adc8", "--text-faint": "#6c7086" },

  // ---- Light (8) ----
  "github-light": { mode: "light", "--accent": "#0969da", "--accent-2": "#1a7f37", "--accent-soft": "#0969da1f", "--bg": "#ffffff", "--bg-elevated": "#f6f8fa", "--bg-card": "#ffffff", "--bg-card-hover": "#f3f4f6", "--border": "#d0d7de", "--text": "#1f2328", "--text-muted": "#59636e", "--text-faint": "#8c959f" },
  "catppuccin-latte": { mode: "light", "--accent": "#8839ef", "--accent-2": "#40a02b", "--accent-soft": "#8839ef1f", "--bg": "#eff1f5", "--bg-elevated": "#e6e9ef", "--bg-card": "#ffffff", "--bg-card-hover": "#f2f4f8", "--border": "#ccd0da", "--text": "#4c4f69", "--text-muted": "#6c6f85", "--text-faint": "#8c8fa1" },
  "gruvbox-light": { mode: "light", "--accent": "#af3a03", "--accent-2": "#79740e", "--accent-soft": "#af3a031f", "--bg": "#fbf1c7", "--bg-elevated": "#f2e5bc", "--bg-card": "#fffdf5", "--bg-card-hover": "#f2e5bc", "--border": "#d5c4a1", "--text": "#3c3836", "--text-muted": "#665c54", "--text-faint": "#8a7c65" },
  "solarized-light": { mode: "light", "--accent": "#268bd2", "--accent-2": "#859900", "--accent-soft": "#268bd21f", "--bg": "#fdf6e3", "--bg-elevated": "#f5edd6", "--bg-card": "#fffdf7", "--bg-card-hover": "#eee8d5", "--border": "#d3cbb7", "--text": "#073642", "--text-muted": "#586e75", "--text-faint": "#839496" },
  daylight: { mode: "light", "--accent": "#4361ee", "--accent-2": "#06a77d", "--accent-soft": "#4361ee1f", "--bg": "#f7f7f9", "--bg-elevated": "#ffffff", "--bg-card": "#ffffff", "--bg-card-hover": "#f0f1f4", "--border": "#e2e4e9", "--text": "#1c1e21", "--text-muted": "#5b5f6b", "--text-faint": "#8a8f99" },
  "mint-light": { mode: "light", "--accent": "#12a578", "--accent-2": "#e8871e", "--accent-soft": "#12a5781f", "--bg": "#f2fbf8", "--bg-elevated": "#ffffff", "--bg-card": "#ffffff", "--bg-card-hover": "#e9f7f2", "--border": "#d3ede4", "--text": "#14332a", "--text-muted": "#4d6b60", "--text-faint": "#7d968c" },
  "rose-light": { mode: "light", "--accent": "#d6336c", "--accent-2": "#e8710a", "--accent-soft": "#d6336c1f", "--bg": "#fff5f7", "--bg-elevated": "#ffffff", "--bg-card": "#ffffff", "--bg-card-hover": "#fdebef", "--border": "#f3d9df", "--text": "#402330", "--text-muted": "#8a6473", "--text-faint": "#ad8b96" },
  "sepia-warm": { mode: "light", "--accent": "#a15c2d", "--accent-2": "#4c7a3d", "--accent-soft": "#a15c2d1f", "--bg": "#f4ecd8", "--bg-elevated": "#faf3e3", "--bg-card": "#fffaf0", "--bg-card-hover": "#efe4c8", "--border": "#e3d5b8", "--text": "#3a2f22", "--text-muted": "#6e5c48", "--text-faint": "#93816b" },

  // ---- Colorblind-friendly (accent pairs from the Okabe–Ito palette,
  // chosen specifically to stay distinguishable for the common forms of
  // color vision deficiency, rather than relying on red/green contrast) ----
  "colorblind-dark": { mode: "dark", a11y: true, "--accent": "#0072b2", "--accent-2": "#e69f00", "--accent-soft": "#0072b226", "--bg": "#14161c", "--bg-elevated": "#191c24", "--bg-card": "#20232d", "--bg-card-hover": "#282c38", "--border": "#2c313d", "--text": "#eef0f4", "--text-muted": "#9aa0ad", "--text-faint": "#666d7a" },
  "colorblind-light": { mode: "light", a11y: true, "--accent": "#0072b2", "--accent-2": "#e69f00", "--accent-soft": "#0072b21f", "--bg": "#fbfbfd", "--bg-elevated": "#ffffff", "--bg-card": "#ffffff", "--bg-card-hover": "#eef1f5", "--border": "#dde1e8", "--text": "#1a1d22", "--text-muted": "#565c66", "--text-faint": "#868d99" },
  "colorblind-tritanopia-dark": { mode: "dark", a11y: true, "--accent": "#d55e00", "--accent-2": "#009e73", "--accent-soft": "#d55e0026", "--bg": "#15161a", "--bg-elevated": "#1a1c21", "--bg-card": "#212328", "--bg-card-hover": "#2a2d33", "--border": "#33363d", "--text": "#f0f0f2", "--text-muted": "#9c9ea6", "--text-faint": "#6a6c74" },
};
const THEME_GROUPS = {
  dark: ["violet", "emerald", "amber", "contrast", "rose", "ocean", "gruvbox-dark", "dracula", "nord", "catppuccin-mocha"],
  light: ["github-light", "catppuccin-latte", "gruvbox-light", "solarized-light", "daylight", "mint-light", "rose-light", "sepia-warm"],
  a11y: ["colorblind-dark", "colorblind-light", "colorblind-tritanopia-dark"],
};
const THEME_LABELS = {
  violet: "themeViolet", emerald: "themeEmerald", amber: "themeAmber", contrast: "themeContrast",
  rose: "themeRose", ocean: "themeOcean", "gruvbox-dark": "themeGruvboxDark", dracula: "themeDracula",
  nord: "themeNord", "catppuccin-mocha": "themeCatppuccinMocha",
  "github-light": "themeGithubLight", "catppuccin-latte": "themeCatppuccinLatte",
  "gruvbox-light": "themeGruvboxLight", "solarized-light": "themeSolarizedLight",
  daylight: "themeDaylight", "mint-light": "themeMintLight", "rose-light": "themeRoseLight",
  "sepia-warm": "themeSepiaWarm",
  "colorblind-dark": "themeColorblindDark", "colorblind-light": "themeColorblindLight",
  "colorblind-tritanopia-dark": "themeColorblindTritanopia",
};

function applyTheme(name) {
  if (name === "custom") { applyCustomColors(getCustomColors()); return; }
  const theme = THEMES[name] || THEMES.violet;
  Object.entries(theme).forEach(([k, v]) => {
    if (k.startsWith("--")) document.documentElement.style.setProperty(k, v);
  });
  document.documentElement.dataset.themeMode = theme.mode || "dark";
  localStorage.setItem("backlog_theme", name);
}
function currentTheme() { return localStorage.getItem("backlog_theme") || "violet"; }

// Custom theme: originally only the accent color was adjustable ("badges"
// only really changed visibly) — now every major surface (background,
// cards, border, text) has its own picker, so a from-scratch palette is
// actually possible instead of just retinting the default dark theme.
const CUSTOM_DEFAULTS = {
  accent: "#7c5cff", bg: "#121319", card: "#1f212b", border: "#2b2e3a", text: "#edeef4", mode: "dark",
};
function getCustomColors() {
  try {
    const saved = JSON.parse(localStorage.getItem("backlog_custom_colors") || "null");
    return saved ? { ...CUSTOM_DEFAULTS, ...saved } : { ...CUSTOM_DEFAULTS };
  } catch { return { ...CUSTOM_DEFAULTS }; }
}
function saveCustomColors(colors) {
  localStorage.setItem("backlog_custom_colors", JSON.stringify(colors));
  localStorage.setItem("backlog_theme", "custom");
}
function applyCustomColors(colors) {
  const root = document.documentElement.style;
  root.setProperty("--accent", colors.accent);
  root.setProperty("--accent-2", lightenHex(colors.accent, 45));
  root.setProperty("--accent-soft", colors.accent + "26");
  root.setProperty("--bg", colors.bg);
  root.setProperty("--bg-elevated", adjustHexLightness(colors.bg, colors.mode === "light" ? -4 : 6));
  root.setProperty("--bg-card", colors.card);
  root.setProperty("--bg-card-hover", adjustHexLightness(colors.card, colors.mode === "light" ? -5 : 6));
  root.setProperty("--border", colors.border);
  root.setProperty("--text", colors.text);
  root.setProperty("--text-muted", adjustHexLightness(colors.text, colors.mode === "light" ? 35 : -35));
  root.setProperty("--text-faint", adjustHexLightness(colors.text, colors.mode === "light" ? 55 : -55));
  document.documentElement.dataset.themeMode = colors.mode || "dark";
}
function lightenHex(hex, amount) {
  const n = parseInt(hex.replace("#", ""), 16);
  let r = (n >> 16) + amount, g = ((n >> 8) & 0xff) + amount, b = (n & 0xff) + amount;
  r = Math.min(255, Math.max(0, r)); g = Math.min(255, Math.max(0, g)); b = Math.min(255, Math.max(0, b));
  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
}
function adjustHexLightness(hex, amount) { return lightenHex(hex, Math.round(amount * 2.55)); }

// ============================================================ Accessibility (dyslexia font, text scaling)
const A11Y_DEFAULTS = { dyslexiaFont: false, textScale: 1.0 };
function getA11yPrefs() {
  try {
    return { ...A11Y_DEFAULTS, ...JSON.parse(localStorage.getItem("backlog_a11y_prefs") || "{}") };
  } catch { return { ...A11Y_DEFAULTS }; }
}
function saveA11yPrefs(patch) {
  const prefs = { ...getA11yPrefs(), ...patch };
  localStorage.setItem("backlog_a11y_prefs", JSON.stringify(prefs));
  return prefs;
}
function applyA11yPrefs() {
  const prefs = getA11yPrefs();
  document.documentElement.dataset.dyslexiaFont = prefs.dyslexiaFont ? "1" : "0";
  document.documentElement.style.fontSize = `${Math.round(prefs.textScale * 100)}%`;
}
function themeSwatchHtml(key, currentThemeKey) {
  const theme = THEMES[key];
  return `
    <div class="theme-swatch ${key === currentThemeKey ? "active" : ""}" data-theme="${key}">
      <div class="theme-swatch-colors">
        <span style="background:${theme["--bg-elevated"]}"></span>
        <span style="background:${theme["--accent"]}"></span>
        <span style="background:${theme["--accent-2"]}"></span>
      </div>
      <div class="theme-swatch-label">${t(THEME_LABELS[key])}</div>
    </div>`;
}

// ============================================================ Custom wallpaper
function getBgMediaConfig() {
  try { return JSON.parse(localStorage.getItem("backlog_bg_media") || "null"); } catch { return null; }
}
function applyBgMedia() {
  const cfg = getBgMediaConfig();
  const layer = document.getElementById("bg-media-layer");
  if (!cfg || !cfg.dataUrl) { layer.innerHTML = ""; layer.style.opacity = 0; return; }
  const isVideo = cfg.mime && cfg.mime.startsWith("video");
  layer.innerHTML = isVideo
    ? `<video src="${cfg.dataUrl}" autoplay loop muted playsinline></video>`
    : `<img src="${cfg.dataUrl}" alt="">`;
  layer.style.opacity = cfg.opacity ?? 0.25;
}

// ============================================================ Interface preferences
const UI_DEFAULTS = {
  addButtonPos: "start",       // 'start' | 'end'
  tabBacklog: "",              // empty = default (translated) name
  tabCompleted: "",
  showYearBands: true,
  abandonedTag: true,          // small red tag (DLC-style)
  abandonedGrey: false,        // greyed-out cover
  abandonedStrike: false,      // struck-through title
};
function getLayoutPrefs() {
  try {
    return { size: 150, gapX: 16, gapY: 16, ...JSON.parse(localStorage.getItem("backlog_layout_prefs") || "{}") };
  } catch { return { size: 150, gapX: 16, gapY: 16 }; }
}
function saveLayoutPrefs(patch) {
  const prefs = { ...getLayoutPrefs(), ...patch };
  localStorage.setItem("backlog_layout_prefs", JSON.stringify(prefs));
  return prefs;
}
function applyLayoutPrefs() {
  const prefs = getLayoutPrefs();
  document.documentElement.style.setProperty("--grid-min", `${prefs.size}px`);
  document.documentElement.style.setProperty("--grid-gap-x", `${prefs.gapX}px`);
  document.documentElement.style.setProperty("--grid-gap-y", `${prefs.gapY}px`);
  document.getElementById("grid-size-slider").value = prefs.size;
  document.getElementById("grid-gap-x-slider").value = prefs.gapX;
  document.getElementById("grid-gap-y-slider").value = prefs.gapY;
}
function initLayoutControls() {
  applyLayoutPrefs();
  document.getElementById("grid-size-slider").addEventListener("input", (e) => {
    document.documentElement.style.setProperty("--grid-min", `${e.target.value}px`);
    saveLayoutPrefs({ size: parseInt(e.target.value, 10) });
  });
  document.getElementById("grid-gap-x-slider").addEventListener("input", (e) => {
    document.documentElement.style.setProperty("--grid-gap-x", `${e.target.value}px`);
    saveLayoutPrefs({ gapX: parseInt(e.target.value, 10) });
  });
  document.getElementById("grid-gap-y-slider").addEventListener("input", (e) => {
    document.documentElement.style.setProperty("--grid-gap-y", `${e.target.value}px`);
    saveLayoutPrefs({ gapY: parseInt(e.target.value, 10) });
  });
  document.getElementById("layout-control-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    document.getElementById("layout-popover").classList.toggle("hidden");
  });
  document.addEventListener("click", (e) => {
    const control = document.getElementById("layout-control");
    if (!control.contains(e.target)) document.getElementById("layout-popover").classList.add("hidden");
  });
}
function getUiPrefs() {
  try {
    return { ...UI_DEFAULTS, ...JSON.parse(localStorage.getItem("backlog_ui_prefs") || "{}") };
  } catch { return { ...UI_DEFAULTS }; }
}
function saveUiPrefs(patch) {
  const prefs = { ...getUiPrefs(), ...patch };
  localStorage.setItem("backlog_ui_prefs", JSON.stringify(prefs));
  return prefs;
}
function getCachedPlayerName() { return localStorage.getItem("backlog_player_name") || ""; }
function setCachedPlayerName(name) { localStorage.setItem("backlog_player_name", name || ""); }

const MONTHS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                   "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"];

// ============================================================ Rating stars (out of 10, half-points supported)
function ratingStarsHtml(rating) {
  const val = parseFloat(rating) || 0;
  let stars = "";
  for (let i = 1; i <= 10; i++) {
    let fillPct = 0;
    if (val >= i) fillPct = 100;
    else if (val >= i - 0.5) fillPct = 50;
    stars += `
      <span class="star-wrap">
        <span class="star-empty">★</span>
        <span class="star-fill" style="width:${fillPct}%">★</span>
        <span class="star-hit star-hit-half" data-val="${i - 0.5}"></span>
        <span class="star-hit star-hit-full" data-val="${i}"></span>
      </span>`;
  }
  return stars;
}
function bindRatingStars() {
  const container = document.getElementById("f-rating");
  if (!container) return;
  container.addEventListener("click", (e) => {
    const hit = e.target.closest(".star-hit");
    if (!hit) return;
    const val = parseFloat(hit.dataset.val);
    container.dataset.value = val;
    container.innerHTML = ratingStarsHtml(val);
    const display = document.getElementById("rating-value-display");
    if (display) display.textContent = `${val}/10`;
  });
}

// ============================================================ Generic confirmation (replaces confirm())
// ============================================================ Notifications (remplace alert())
function showToast(message, type = "info", duration = 4500) {
  const container = document.getElementById("toast-container");
  const icons = { info: "ℹ️", warning: "⚠️", error: "❌" };
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || icons.info}</span>
    <span class="toast-msg"></span>
    <button class="toast-close">×</button>`;
  toast.querySelector(".toast-msg").textContent = message; // avoids any HTML injection
  container.appendChild(toast);

  const remove = () => {
    toast.classList.add("toast-out");
    setTimeout(() => toast.remove(), 200);
  };
  toast.querySelector(".toast-close").addEventListener("click", remove);
  if (duration) setTimeout(remove, duration);
}

function showConfirm({ message, okLabel, cancelLabel, danger = true }) {
  return new Promise((resolve) => {
    const overlay = document.getElementById("confirm-modal");
    document.getElementById("confirm-message").textContent = message;
    const okBtn = document.getElementById("confirm-ok-btn");
    const cancelBtn = document.getElementById("confirm-cancel-btn");
    okBtn.textContent = okLabel || t("confirmDelete");
    okBtn.className = danger ? "btn btn-danger-solid" : "btn btn-primary";
    cancelBtn.textContent = cancelLabel || t("confirmCancel");
    overlay.classList.remove("hidden");

    const cleanup = (result) => {
      overlay.classList.add("hidden");
      okBtn.removeEventListener("click", onOk);
      cancelBtn.removeEventListener("click", onCancel);
      overlay.removeEventListener("click", onOverlay);
      resolve(result);
    };
    const onOk = () => cleanup(true);
    const onCancel = () => cleanup(false);
    const onOverlay = (e) => { if (e.target.id === "confirm-modal") cleanup(false); };
    okBtn.addEventListener("click", onOk);
    cancelBtn.addEventListener("click", onCancel);
    overlay.addEventListener("click", onOverlay);
  });
}

// ============================================================ Display sort (never modifies the stored original order)
function sortGamesForDisplay(games, sortMode) {
  const arr = [...games];
  switch (sortMode) {
    case "chrono":
      return arr.sort((a, b) => (a.year_finished || 0) - (b.year_finished || 0) || a.id - b.id);
    case "chrono-rev":
      return arr.sort((a, b) => (b.year_finished || 0) - (a.year_finished || 0) || b.id - a.id);
    case "alpha":
      return arr.sort((a, b) => a.title.localeCompare(b.title));
    case "alpha-rev":
      return arr.sort((a, b) => b.title.localeCompare(a.title));
    default:
      return arr.sort((a, b) => a.id - b.id); // "original": insertion order = row order from the imported file, never modified
  }
}

// ============================================================ Consentement recherche internet (jaquettes)
let _consentCache = null;

async function ensureInternetConsent() {
  if (_consentCache === null) {
    const settings = await api.get("/api/settings");
    _consentCache = !!settings.internet_search_consent;
  }
  if (_consentCache) return true;
  return await showConsentModal();
}

function showConsentModal() {
  return new Promise((resolve) => {
    const overlay = document.getElementById("consent-modal");
    const body = document.getElementById("consent-body");
    body.innerHTML = `
      <h3>${t("consentTitle")}</h3>
      <p>${t("consentIntro")}</p>
      <ul class="consent-api-list">
        <li>Steam Store (store.steampowered.com)</li>
        <li>RAWG.io API (${t("consentIfKeyConfigured")})</li>
        <li>Giant Bomb API (${t("consentIfKeyConfigured")})</li>
        <li>Wikipedia (en.wikipedia.org)</li>
      </ul>
      <p>${t("consentNoCommercial")}</p>
      <p class="consent-legal">Steam est une marque de Valve Corporation. Les images et métadonnées récupérées appartiennent à leurs propriétaires respectifs.</p>
      <div class="consent-checkbox-row">
        <input type="checkbox" id="consent-checkbox">
        <label for="consent-checkbox">${t("consentCheckboxLabel")}</label>
      </div>
      <div class="modal-actions">
        <button class="btn btn-outline" id="consent-decline-btn">${t("consentDecline")}</button>
        <button class="btn btn-primary" id="consent-accept-btn" disabled>${t("consentAccept")}</button>
      </div>`;
    overlay.classList.remove("hidden");

    const checkbox = document.getElementById("consent-checkbox");
    const acceptBtn = document.getElementById("consent-accept-btn");
    checkbox.addEventListener("change", () => { acceptBtn.disabled = !checkbox.checked; });

    const cleanup = async (result) => {
      overlay.classList.add("hidden");
      if (result) {
        _consentCache = true;
        await api.post("/api/settings", { internet_search_consent: true });
      }
      resolve(result);
    };
    acceptBtn.addEventListener("click", () => cleanup(true));
    document.getElementById("consent-decline-btn").addEventListener("click", () => cleanup(false));
  });
}
function detectAndSetInitialLanguage() {
  if (localStorage.getItem("backlog_lang")) return; // already chosen explicitly
  const sysLang = (navigator.language || "en").toLowerCase();
  localStorage.setItem("backlog_lang", sysLang.startsWith("fr") ? "fr" : "en");
}

// ============================================================ State
const state = {
  view: "dashboard",
  gamesCache: { backlog: [], completed: [] },
  dashboardEditMode: false,
  lastStats: null,
  chartsYearFilter: null,
  availableYears: null,
};

const GRADIENTS = [
  "linear-gradient(135deg,#7c5cff,#c9ff5e)",
  "linear-gradient(135deg,#ff6b6b,#ffb454)",
  "linear-gradient(135deg,#4d7cff,#7c5cff)",
  "linear-gradient(135deg,#00d4b4,#4d7cff)",
  "linear-gradient(135deg,#ffb454,#ff6b6b)",
  "linear-gradient(135deg,#c9ff5e,#00d4b4)",
];
function gradientFor(title) {
  let hash = 0;
  for (let i = 0; i < title.length; i++) hash = title.charCodeAt(i) + ((hash << 5) - hash);
  return GRADIENTS[Math.abs(hash) % GRADIENTS.length];
}

// ============================================================ Dates

// ============================================================ Setup screen
async function checkSetup() {
  const status = await api.get("/api/setup/status");
  if (status.configured || status.has_data) {
    document.getElementById("setup-screen").classList.add("hidden");
    document.getElementById("app").classList.remove("hidden");
    startApp();
  } else {
    document.getElementById("setup-screen").classList.remove("hidden");
    setupSetupScreen();
  }
}

function setupSetupScreen() {
  applyTranslations();
  document.querySelectorAll(".setup-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".setup-tab").forEach(x => x.classList.remove("active"));
      tab.classList.add("active");
      const mode = tab.dataset.mode;
      document.getElementById("setup-xlsx").classList.toggle("hidden", mode !== "xlsx");
      document.getElementById("setup-csv").classList.toggle("hidden", mode !== "csv");
    });
  });

  const bindFileLabel = (inputId, labelId, fallbackKey) => {
    document.getElementById(inputId).addEventListener("change", (e) => {
      const f = e.target.files[0];
      document.getElementById(labelId).textContent = f ? f.name : t(fallbackKey);
    });
  };
  bindFileLabel("xlsx-input", "xlsx-label", "setupChooseXlsx");
  bindFileLabel("backlog-input", "backlog-label", "setupChooseXlsx");
  bindFileLabel("avis-input", "avis-label", "setupChooseXlsx");
  bindFileLabel("complete-input", "complete-label", "setupChooseXlsx");

  document.getElementById("setup-import-btn").addEventListener("click", async () => {
    const statusEl = document.getElementById("setup-status");
    const playerName = document.getElementById("setup-player-name").value.trim();
    const formData = new FormData();
    const xlsx = document.getElementById("xlsx-input").files[0];
    const b = document.getElementById("backlog-input").files[0];
    const a = document.getElementById("avis-input").files[0];
    const c = document.getElementById("complete-input").files[0];
    if (xlsx) formData.append("xlsx", xlsx);
    if (b) formData.append("backlog_csv", b);
    if (a) formData.append("avis_csv", a);
    if (c) formData.append("complete_csv", c);
    if (!xlsx && !b && !a && !c) {
      statusEl.textContent = t("setupNoFileSelected");
      return;
    }
    statusEl.textContent = t("setupImportInProgress");
    const res = await api.upload("/api/setup/import", formData);
    if (res.error) {
      statusEl.textContent = "❌ " + res.error;
      return;
    }
    if (playerName) {
      await api.post("/api/settings", { player_name: playerName });
      setCachedPlayerName(playerName);
    }
    let msg = t("setupImportSuccess")
      .replace("{completed}", res.summary.completed_imported)
      .replace("{backlog}", res.summary.backlog_imported)
      .replace("{matched}", res.summary.reviews_matched);
    if (res.summary.reviews_needs_confirmation > 0) {
      msg += " " + t("setupImportNeedsConfirmation").replace("{n}", res.summary.reviews_needs_confirmation);
    }
    const trueOrphans = res.summary.reviews_orphan - res.summary.reviews_needs_confirmation;
    if (trueOrphans > 0) {
      msg += " " + t("setupImportOrphans").replace("{n}", trueOrphans);
    }
    statusEl.textContent = msg;
    setTimeout(checkSetup, res.summary.reviews_orphan > 0 ? 2200 : 900);
  });

  document.getElementById("setup-skip-btn").addEventListener("click", async () => {
    const playerName = document.getElementById("setup-player-name").value.trim();
    if (playerName) {
      await api.post("/api/settings", { player_name: playerName });
      setCachedPlayerName(playerName);
    }
    await api.post("/api/setup/skip");
    checkSetup();
  });
}

// ============================================================ App shell
function initEscapeKeyHandler() {
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    // Priority order: modals "on top of" another one (confirmation,
    // consentement) se ferment en premier si elles sont ouvertes.
    const modalCloseMap = [
      ["confirm-modal", () => document.getElementById("confirm-cancel-btn")?.click()],
      ["consent-modal", () => document.getElementById("consent-decline-btn")?.click()],
      ["game-modal", closeModal],
      ["settings-modal", closeSettingsModal],
      ["options-modal", closeOptionsModal],
      ["year-review-modal", closeYearReviewModal],
    ];
    for (const [id, closeFn] of modalCloseMap) {
      const el = document.getElementById(id);
      if (el && !el.classList.contains("hidden")) {
        closeFn();
        break;
      }
    }
  });
}

function startApp() {
  applyTranslations();
  initEscapeKeyHandler();
  document.querySelectorAll(".nav-item").forEach(btn => {
    btn.addEventListener("click", () => switchView(btn.dataset.view));
  });
  document.getElementById("export-xlsx-btn").addEventListener("click", () => {
    window.location.href = "/api/export/xlsx";
  });
  document.getElementById("export-csv-btn").addEventListener("click", () => {
    window.location.href = "/api/export/csv";
  });
  document.getElementById("export-covers-btn").addEventListener("click", () => {
    window.location.href = "/api/export/covers";
  });
  document.getElementById("close-app-btn").addEventListener("click", async () => {
    const ok = await showConfirm({
      message: t("closeAppConfirmMsg"), okLabel: t("closeAppConfirmBtn"),
      cancelLabel: t("confirmCancel"), danger: true,
    });
    if (!ok) return;
    await api.post("/api/shutdown");
    document.body.innerHTML = `<div class="app-closed-screen"><h1>${t("closeAppClosedTitle")}</h1><p>${t("closeAppClosedMsg")}</p></div>`;
  });
  document.getElementById("modal-close").addEventListener("click", closeModal);
  document.getElementById("game-modal").addEventListener("click", (e) => {
    if (e.target.id === "game-modal") closeModal();
  });
  // Debounced so fast typing doesn't fire a network request per keystroke —
  // one GET /api/games after the user pauses, instead of one per character.
  document.getElementById("search-input").addEventListener("input", debounce(() => renderCurrentGrid(), 250));
  document.getElementById("filter-available").addEventListener("change", () => renderCurrentGrid());
  document.getElementById("filter-year").addEventListener("change", () => renderCurrentGrid());
  document.getElementById("filter-dlc").addEventListener("change", () => renderCurrentGrid());
  document.getElementById("filter-abandoned").addEventListener("change", () => renderCurrentGrid());
  document.getElementById("toggle-year-bands-btn").addEventListener("click", () => {
    const prefs = getUiPrefs();
    saveUiPrefs({ showYearBands: !prefs.showYearBands });
    updateYearBandsToggleUi();
    renderCurrentGrid();
  });
  document.getElementById("sort-select").addEventListener("change", (e) => {
    setSortMode(state.view, e.target.value);
    renderCurrentGrid();
  });
  document.getElementById("dashboard-edit-btn").addEventListener("click", toggleDashboardEditMode);
  document.getElementById("year-review-btn").addEventListener("click", openYearReviewModal);
  document.getElementById("year-review-close").addEventListener("click", closeYearReviewModal);
  document.getElementById("random-pick-btn").addEventListener("click", openRandomPickerModal);
  document.getElementById("random-picker-close").addEventListener("click", closeRandomPickerModal);
  document.getElementById("year-review-modal").addEventListener("click", (e) => {
    if (e.target.id === "year-review-modal") closeYearReviewModal();
  });
  initLayoutControls();
  document.getElementById("bulk-cover-btn").addEventListener("click", startBulkCoverFill);
  document.getElementById("bulk-cover-cancel-btn").addEventListener("click", async () => {
    await api.post("/api/covers/bulk-fill/cancel");
  });
  document.getElementById("sanitize-names-btn").addEventListener("click", startSanitizeScan);
  document.getElementById("sanitize-cancel-btn").addEventListener("click", async () => {
    await api.post("/api/sanitize/cancel");
  });
  document.getElementById("sanitize-modal-close").addEventListener("click", closeSanitizeModal);
  document.getElementById("sanitize-modal").addEventListener("click", (e) => {
    if (e.target.id === "sanitize-modal") closeSanitizeModal();
  });
  document.getElementById("settings-btn").addEventListener("click", openSettingsModal);
  document.getElementById("settings-close").addEventListener("click", closeSettingsModal);
  document.getElementById("settings-modal").addEventListener("click", (e) => {
    if (e.target.id === "settings-modal") closeSettingsModal();
  });
  document.getElementById("options-btn").addEventListener("click", openOptionsModal);
  document.getElementById("options-close").addEventListener("click", closeOptionsModal);
  document.getElementById("options-modal").addEventListener("click", (e) => {
    if (e.target.id === "options-modal") closeOptionsModal();
  });

  api.get("/api/covers/bulk-fill/status").then(status => {
    if (status.running) pollBulkCoverStatus();
  });
  api.get("/api/sanitize/status").then(status => {
    if (status.running) pollSanitizeStatus();
  });
  api.get("/api/settings").then(settings => {
    setCachedPlayerName(settings.player_name || "");
    renderPlayerNameTag();
  });
  loadOrphanReviewBanner();
  loadDuplicatesBanner();
  switchView("dashboard");
}

async function loadDuplicatesBanner() {
  const dups = await api.get("/api/duplicates");
  const banner = document.getElementById("duplicates-banner");
  if (!dups.length) {
    banner.classList.add("hidden");
    return;
  }
  const itemsHtml = dups.map(d => `
    <div class="orphan-item" data-backlog-id="${d.backlog_id}">
      <div class="orphan-item-text">${t("duplicateBannerItemText")
        .replace("{title}", `« ${escapeHtml(d.backlog_title)} »`)}</div>
      <div class="orphan-item-actions">
        <button class="btn btn-primary btn-sm dup-delete-backlog-btn" data-id="${d.backlog_id}">${t("duplicateDeleteBacklogBtn")}</button>
        <button class="btn btn-outline btn-sm dup-dismiss-btn" data-backlog-id="${d.backlog_id}">${t("orphanDismissBtn")}</button>
      </div>
    </div>`).join("");
  banner.innerHTML = `
    <span class="orphan-banner-icon">🔁</span>
    <div class="orphan-banner-body">
      <div class="orphan-banner-title">${t("duplicateBannerTitle")}</div>
      <div class="orphan-suggestions-list">${itemsHtml}</div>
    </div>
    <button class="orphan-banner-close" title="${t("confirmCancel")}">×</button>`;
  banner.classList.remove("hidden");
  banner.querySelector(".orphan-banner-close").addEventListener("click", () => {
    banner.classList.add("hidden");
  });
  banner.querySelectorAll(".dup-delete-backlog-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      await api.del(`/api/games/${btn.dataset.id}`);
      showToast(t("duplicateResolvedToast"), "success");
      loadDuplicatesBanner();
      refreshCurrentView();
    });
  });
  banner.querySelectorAll(".dup-dismiss-btn").forEach(btn => {
    // Dismissing here is purely visual for this session — there's no
    // persisted "seen" state, since the duplicate is computed live from
    // current data. If it's still there next time the app loads, it's
    // because it genuinely hasn't been resolved yet.
    btn.addEventListener("click", () => {
      banner.querySelector(`.orphan-item[data-backlog-id="${btn.dataset.backlogId}"]`)?.remove();
      if (!banner.querySelectorAll(".orphan-item").length) banner.classList.add("hidden");
    });
  });
}

async function loadOrphanReviewBanner() {
  const orphans = await api.get("/api/orphan-reviews");
  const banner = document.getElementById("orphan-review-banner");
  if (!orphans.length) {
    banner.classList.add("hidden");
    return;
  }
  const suggested = orphans.filter(o => o.suggested_game_id);
  const trueOrphans = orphans.filter(o => !o.suggested_game_id);

  const suggestedHtml = suggested.map(o => {
    const isAmbiguous = o.match_type === "ambiguous" && o.alternatives && o.alternatives.length;
    const options = isAmbiguous
      ? [{ id: o.suggested_game_id, title: o.suggested_title }, ...o.alternatives]
      : null;
    return `
    <div class="orphan-item" data-id="${o.id}">
      <div class="orphan-item-text">${isAmbiguous
        ? t("orphanAmbiguousText").replace("{review_title}", `« ${escapeHtml(o.original_title)} »`)
        : t("orphanSuggestionText")
            .replace("{review_title}", `« ${escapeHtml(o.original_title)} »`)
            .replace("{suggested_title}", `« ${escapeHtml(o.suggested_title)} »`)}</div>
      ${isAmbiguous ? `
      <select class="filter-select orphan-choice-select" data-id="${o.id}">
        ${options.map(opt => `<option value="${opt.id}">${escapeHtml(opt.title)}</option>`).join("")}
      </select>` : ""}
      <div class="orphan-item-actions">
        <button class="btn btn-primary btn-sm orphan-confirm-btn" data-id="${o.id}" data-game-id="${o.suggested_game_id}">${t("orphanConfirmBtn")}</button>
        <button class="btn btn-outline btn-sm orphan-dismiss-btn" data-id="${o.id}">${t("orphanDismissBtn")}</button>
      </div>
    </div>`;
  }).join("");

  const trueOrphanList = trueOrphans.map(o => `« ${escapeHtml(o.original_title)} »`).join(", ");

  banner.innerHTML = `
    <span class="orphan-banner-icon">⚠️</span>
    <div class="orphan-banner-body">
      <div class="orphan-banner-title">${t("orphanBannerTitle")}</div>
      ${suggested.length ? `<div class="orphan-suggestions-list">${suggestedHtml}</div>` : ""}
      ${trueOrphans.length ? `<div class="orphan-banner-list">${t("orphanBannerBody").replace("{list}", trueOrphanList)}</div>` : ""}
    </div>
    <button class="orphan-banner-close" title="${t("confirmCancel")}">×</button>`;
  banner.classList.remove("hidden");
  banner.querySelector(".orphan-banner-close").addEventListener("click", () => {
    banner.classList.add("hidden");
  });
  banner.querySelectorAll(".orphan-choice-select").forEach(sel => {
    sel.addEventListener("change", () => {
      const confirmBtn = banner.querySelector(`.orphan-confirm-btn[data-id="${sel.dataset.id}"]`);
      if (confirmBtn) confirmBtn.dataset.gameId = sel.value;
    });
  });
  banner.querySelectorAll(".orphan-confirm-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      await api.post(`/api/orphan-reviews/${btn.dataset.id}/link`, { game_id: parseInt(btn.dataset.gameId, 10) });
      showToast(t("orphanConfirmedToast"), "success");
      loadOrphanReviewBanner();
      refreshCurrentView();
    });
  });
  banner.querySelectorAll(".orphan-dismiss-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      await api.post(`/api/orphan-reviews/${btn.dataset.id}/dismiss`);
      loadOrphanReviewBanner();
    });
  });
}

function renderPlayerNameTag() {
  const name = getCachedPlayerName();
  const el = document.getElementById("player-name-tag");
  if (name) {
    el.textContent = `— ${name}`;
    el.classList.remove("hidden");
  } else {
    el.classList.add("hidden");
  }
}

function renderCurrentGrid() {
  if (state.view === "backlog" || state.view === "completed") {
    renderGrid(
      state.view,
      document.getElementById("search-input").value,
      document.getElementById("filter-available").value,
      document.getElementById("filter-year").value,
      document.getElementById("filter-dlc").value,
      document.getElementById("filter-abandoned").value,
    );
  }
}

function tabLabel(view) {
  const prefs = getUiPrefs();
  if (view === "backlog" && prefs.tabBacklog) return prefs.tabBacklog;
  if (view === "completed" && prefs.tabCompleted) return prefs.tabCompleted;
  const titles = { dashboard: "navDashboard", completed: "navCompleted", backlog: "navBacklog" };
  return t(titles[view]);
}

function applyTabLabels() {
  document.querySelectorAll(".nav-item").forEach(btn => {
    const span = btn.querySelector("span:last-child");
    span.textContent = tabLabel(btn.dataset.view);
  });
}

async function switchView(view) {
  state.view = view;
  applyTabLabels();
  document.querySelectorAll(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  document.querySelectorAll(".view").forEach(v => v.classList.add("hidden"));
  document.getElementById(`view-${view}`).classList.remove("hidden");
  document.getElementById("view-title").textContent = tabLabel(view);

  const isGridView = view !== "dashboard";
  document.getElementById("search-input").classList.toggle("hidden", !isGridView);
  document.getElementById("filter-available").classList.toggle("hidden", !isGridView);
  document.getElementById("filter-year").classList.toggle("hidden", view !== "completed");
  document.getElementById("filter-dlc").classList.toggle("hidden", !isGridView);
  document.getElementById("filter-abandoned").classList.toggle("hidden", !isGridView);
  document.getElementById("toggle-year-bands-btn").classList.toggle("hidden", view !== "completed");
  document.getElementById("random-pick-btn").classList.toggle("hidden", view !== "backlog");
  document.getElementById("sort-select").classList.toggle("hidden", !isGridView);
  document.getElementById("layout-control").classList.toggle("hidden", !isGridView);
  document.getElementById("layout-popover").classList.add("hidden");
  document.getElementById("dashboard-edit-btn").classList.toggle("hidden", view !== "dashboard");
  document.getElementById("year-review-btn").classList.toggle("hidden", view !== "dashboard");
  document.getElementById("search-input").value = "";
  document.getElementById("filter-available").value = "";
  document.getElementById("filter-year").value = "";
  document.getElementById("filter-dlc").value = "";
  document.getElementById("filter-abandoned").value = "";
  document.getElementById("sort-select").value = getSortMode(view);
  updateYearBandsToggleUi();

  if (view === "completed") await populateYearFilter();

  if (view === "dashboard") loadDashboard();
  else renderGrid(view);
}

function updateYearBandsToggleUi() {
  const btn = document.getElementById("toggle-year-bands-btn");
  const on = getUiPrefs().showYearBands;
  btn.textContent = on ? t("toggleYearBandsOn") : t("toggleYearBandsOff");
  btn.classList.toggle("active", on);
}

function getSortMode(view) {
  // Default display order is reverse chronological (newest first) — the
  // underlying stored order (import order) stays available as "original"
  // but is no longer the default the user sees on first load.
  return localStorage.getItem(`backlog_sort_${view}`) || "chrono-rev";
}
function setSortMode(view, mode) {
  localStorage.setItem(`backlog_sort_${view}`, mode);
}

function renderChronoArrow(view) {
  const el = document.getElementById(`chrono-arrow-${view}`);
  if (!el) return;
  el.innerHTML = `<div class="arrow-line"></div><div class="arrow-label">${t("chronoArrowLabel")}</div><div class="arrow-head"></div>`;
}

async function populateYearFilter() {
  const years = await api.get("/api/games/years");
  const sel = document.getElementById("filter-year");
  sel.innerHTML = `<option value="" data-i18n="filterAllYears">${t("filterAllYears")}</option>` +
    years.map(y => `<option value="${y}">${y}</option>`).join("");
}

// ============================================================ Dashboard: movable/resizable widgets
const DEFAULT_WIDGET_ORDER = ["overview", "pace", "highlights", "year-progress", "month-trend", "rating-distribution", "worth-it", "ownership"];
const WIDGET_TITLES = {
  overview: "widgetOverview", pace: "widgetPace", highlights: "widgetHighlights", "year-progress": "widgetYearProgress",
  "month-trend": "widgetMonthTrend", "rating-distribution": "widgetRatingDist",
  "worth-it": "widgetWorthIt", ownership: "widgetOwnership",
};
const WIDGET_DEFAULT_SIZE = {
  overview: "wide", pace: "normal", "year-progress": "wide", highlights: "wide",
  "month-trend": "normal", "rating-distribution": "normal", "worth-it": "normal", ownership: "normal",
};
const WIDGET_RENDERERS = {
  overview: renderOverviewWidget, pace: renderPaceWidget, highlights: renderHighlightsWidget, "year-progress": renderYearProgressWidget,
  "month-trend": renderMonthTrendWidget, "rating-distribution": renderRatingDistWidget,
  "worth-it": renderWorthItWidget, ownership: renderOwnershipWidget,
};

function getWidgetConfig() {
  let saved;
  try { saved = JSON.parse(localStorage.getItem("backlog_widgets") || "null"); } catch { saved = null; }
  if (!Array.isArray(saved)) saved = [];
  const existingIds = new Set(saved.map(w => w.id));
  DEFAULT_WIDGET_ORDER.forEach(id => {
    if (!existingIds.has(id)) saved.push({ id, size: WIDGET_DEFAULT_SIZE[id], visible: true });
  });
  return saved.filter(w => DEFAULT_WIDGET_ORDER.includes(w.id));
}
function saveWidgetConfig(cfg) { localStorage.setItem("backlog_widgets", JSON.stringify(cfg)); }

function statCard(icon, value, labelKey) {
  return `<div class="stat-card"><div class="stat-icon">${icon}</div>
    <div class="stat-value">${value}</div><div class="stat-label">${t(labelKey)}</div></div>`;
}

function spotlightHtml(icon, titleKey, game, unit) {
  if (!game) {
    return `<div class="spotlight-panel"><div class="spotlight-icon">${icon}</div>
      <div><div class="spotlight-title">${t(titleKey)}</div><div class="hint">${t("noDataYet")}</div></div></div>`;
  }
  const metric = unit === "rating" ? `★ ${game.rating}` : `${game.hours_played ?? game.hours ?? 0} h`;
  return `<div class="spotlight-panel"><div class="spotlight-icon">${icon}</div>
    <div><div class="spotlight-title">${t(titleKey)}</div>
    <div class="spotlight-game">${escapeHtml(game.title)}</div>
    <div class="spotlight-hours">${metric}</div></div></div>`;
}

function renderPaceWidget(el, stats) {
  const avg = stats.pace.avg_hours_per_month;
  const months = stats.pace.months_to_clear_backlog;
  el.innerHTML = `<div class="stat-grid">${[
    statCard("📆", avg ?? "—", "statAvgHoursPerMonth"),
    statCard("🏁", months ?? "—", "statMonthsToClearBacklog"),
    statCard("🧩", stats.dlc.nb_dlc, "statDlcCompleted"),
    statCard("📦", stats.dlc.nb_dlc_backlog, "statDlcBacklog"),
  ].join("")}</div>`;
}

function renderOverviewWidget(el, stats) {
  el.innerHTML = `<div class="stat-grid">${[
    statCard("⏱️", stats.total_hours_played, "statTotalHours"),
    statCard("🏆", stats.nb_completed, "statCompleted"),
    statCard("📊", stats.avg_hours_per_game, "statAvgHours"),
    statCard("⭐", stats.avg_rating ?? "—", "statAvgRating"),
    statCard("📦", stats.backlog.nb_games, "statRemaining"),
    statCard("⌛", stats.backlog.estimated_hours, "statBacklogHours"),
  ].join("")}</div>`;
}

function renderHighlightsWidget(el, stats) {
  el.innerHTML = `<div class="panels-row" style="margin-bottom:0;">
    ${spotlightHtml("🏔️", "longestGameTitle", stats.longest_game, "hours")}
    ${spotlightHtml("⚡", "shortestGameTitle", stats.shortest_game, "hours")}
    ${spotlightHtml("👑", "bestRatedGameTitle", stats.best_rated_game, "rating")}
    ${spotlightHtml("💔", "worstRatedGameTitle", stats.worst_rated_game, "rating")}
  </div>`;
}

function renderSparklineHtml(points) {
  if (!points.length) return "";
  const w = 560, h = 60, pad = 6;
  const maxVal = Math.max(1, ...points.map(p => p.cumulative));
  const stepX = points.length > 1 ? (w - pad * 2) / (points.length - 1) : 0;
  const coords = points.map((p, i) => [pad + i * stepX, h - pad - (p.cumulative / maxVal) * (h - pad * 2)]);
  const path = coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const areaPath = `${path} L${coords[coords.length - 1][0].toFixed(1)},${h} L${coords[0][0].toFixed(1)},${h} Z`;
  const dots = coords.map(([x, y], i) => `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="2.5" fill="var(--accent-2)"><title>${points[i].year}: ${points[i].cumulative}</title></circle>`).join("");
  return `
    <div class="sparkline-wrap">
      <div class="sparkline-label">${t("cumulativeLabel")}</div>
      <svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none">
        <path d="${areaPath}" fill="var(--accent)" opacity="0.12"></path>
        <path d="${path}" fill="none" stroke="var(--accent)" stroke-width="2"></path>
        ${dots}
      </svg>
    </div>`;
}

function renderYearProgressWidget(el, stats) {
  const maxYearHours = Math.max(1, ...stats.by_year.map(y => y.hours));
  const bars = stats.by_year.map(y => `
    <div class="bar-row">
      <span class="label">${y.year}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${(y.hours / maxYearHours) * 100}%"></div></div>
      <span class="val">${y.nb}j</span>
    </div>`).join("") || `<p class="hint">${t("noDataYet")}</p>`;
  el.innerHTML = `<div class="bar-chart">${bars}</div>${renderSparklineHtml(stats.by_year.filter(y => y.year !== "Inconnu"))}`;
}

function yearFilterSelectHtml(selectClass) {
  const years = state.availableYears || [];
  const current = state.chartsYearFilter || "";
  return `<select class="widget-mini-select ${selectClass}">
    <option value="" ${current === "" ? "selected" : ""}>${t("filterAllYears")}</option>
    ${years.map(y => `<option value="${y}" ${String(y) === String(current) ? "selected" : ""}>${y}</option>`).join("")}
  </select>`;
}

function bindYearFilterSelect(el, cls) {
  const sel = el.querySelector(`.${cls}`);
  if (sel) sel.addEventListener("change", () => {
    state.chartsYearFilter = sel.value || null;
    loadDashboard();
  });
}

function renderMonthTrendWidget(el, stats) {
  const maxMonthNb = Math.max(1, ...stats.by_month.map(m => m.nb));
  const bars = stats.by_month.map(m => `
    <div class="bar-row">
      <span class="label">${m.month.slice(0, 3)}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${(m.nb / maxMonthNb) * 100}%"></div></div>
      <span class="val">${m.nb}</span>
    </div>`).join("") || `<p class="hint">${t("noDataYet")}</p>`;
  el.innerHTML = `<div style="display:flex;justify-content:flex-end;margin-bottom:10px;">${yearFilterSelectHtml("month-year-filter")}</div><div class="bar-chart">${bars}</div>`;
  bindYearFilterSelect(el, "month-year-filter");
}

function renderRatingDistWidget(el, stats) {
  const maxRatingNb = Math.max(1, ...stats.rating_histogram.map(r => r.nb));
  const bars = stats.rating_histogram.map(r => `
    <div class="bar-row">
      <span class="label">★ ${r.rating}/10</span>
      <div class="bar-track"><div class="bar-fill" style="width:${(r.nb / maxRatingNb) * 100}%"></div></div>
      <span class="val">${r.nb}</span>
    </div>`).join("");
  el.innerHTML = `<div style="display:flex;justify-content:flex-end;margin-bottom:10px;">${yearFilterSelectHtml("rating-year-filter")}</div><div class="bar-chart">${bars}</div>`;
  bindYearFilterSelect(el, "rating-year-filter");
}

function renderWorthItWidget(el, stats) {
  const worthEntries = Object.entries(stats.worth_it_distribution);
  el.innerHTML = `<div class="pill-chart">${
    worthEntries.map(([label, n]) => `<div class="pill"><span class="n">${n}</span> ${label}</div>`).join("")
    + `<div class="pill"><span class="n">${stats.dlc.nb_dlc}</span> DLC</div>`
  }</div>`;
}

function renderOwnershipBarHtml(groupTitleKey, ownership) {
  const total = ownership.owned + ownership.not_owned + ownership.unknown;
  if (!total) return `<div class="dual-bar-group"><div class="dual-bar-title">${t(groupTitleKey)}</div><p class="hint">${t("noDataYet")}</p></div>`;
  const pct = (n) => (n / total) * 100;
  return `
    <div class="dual-bar-group">
      <div class="dual-bar-title">${t(groupTitleKey)} (${total})</div>
      <div class="dual-bar-track">
        <div class="dual-bar-seg-owned" style="width:${pct(ownership.owned)}%"></div>
        <div class="dual-bar-seg-not" style="width:${pct(ownership.not_owned)}%"></div>
        <div class="dual-bar-seg-unknown" style="width:${pct(ownership.unknown)}%"></div>
      </div>
      <div class="dual-bar-legend">
        <span class="legend-owned">${t("legendOwned")} ${ownership.owned}</span>
        <span class="legend-not">${t("legendNotOwned")} ${ownership.not_owned}</span>
        <span class="legend-unknown">${t("legendUnknown")} ${ownership.unknown}</span>
      </div>
    </div>`;
}
function renderOwnershipWidget(el, stats) {
  el.innerHTML = `<div class="dual-bar-chart">${renderOwnershipBarHtml("ownershipBacklogLabel", stats.ownership.backlog)}</div>`;
}

function renderWidgetsGrid() {
  const container = document.getElementById("widgets-grid");
  const cfg = getWidgetConfig();
  const editing = state.dashboardEditMode;
  const visibleCfg = editing ? cfg : cfg.filter(w => w.visible);

  container.innerHTML = visibleCfg.map(w => `
    <div class="widget-card ${w.size === "wide" ? "size-wide" : ""} ${editing ? "editing" : ""} ${editing && !w.visible ? "dimmed" : ""}"
         data-widget-id="${w.id}" ${editing ? 'draggable="true"' : ""} style="${editing && !w.visible ? "opacity:.4;" : ""}">
      <div class="widget-header">
        <h3>${editing ? '<span class="widget-drag-handle">☰</span> ' : ""}${t(WIDGET_TITLES[w.id])}</h3>
        ${editing ? `
          <div class="widget-controls">
            <button class="widget-size-btn" title="${t("widgetSizeWide")}">${w.size === "wide" ? "⇱" : "⇲"}</button>
            <button class="widget-hide-btn" title="${t("widgetHide")}">${w.visible ? "✕" : "↺"}</button>
          </div>` : ""}
      </div>
      <div class="widget-body" id="widget-body-${w.id}"></div>
    </div>`).join("");

  visibleCfg.forEach(w => {
    const bodyEl = document.getElementById(`widget-body-${w.id}`);
    if (bodyEl && state.lastStats) WIDGET_RENDERERS[w.id](bodyEl, state.lastStats);
  });

  if (editing) bindWidgetEditEvents();
}

function bindWidgetEditEvents() {
  const container = document.getElementById("widgets-grid");
  let dragSrcId = null;

  container.querySelectorAll(".widget-card").forEach(card => {
    card.addEventListener("dragstart", () => {
      dragSrcId = card.dataset.widgetId;
      card.classList.add("dragging");
    });
    card.addEventListener("dragend", () => card.classList.remove("dragging"));
    card.addEventListener("dragover", (e) => { e.preventDefault(); card.classList.add("drag-over"); });
    card.addEventListener("dragleave", () => card.classList.remove("drag-over"));
    card.addEventListener("drop", (e) => {
      e.preventDefault();
      card.classList.remove("drag-over");
      const targetId = card.dataset.widgetId;
      if (!dragSrcId || dragSrcId === targetId) return;
      const cfg = getWidgetConfig();
      const srcIdx = cfg.findIndex(w => w.id === dragSrcId);
      const tgtIdx = cfg.findIndex(w => w.id === targetId);
      const [moved] = cfg.splice(srcIdx, 1);
      cfg.splice(tgtIdx, 0, moved);
      saveWidgetConfig(cfg);
      renderWidgetsGrid();
    });

    const sizeBtn = card.querySelector(".widget-size-btn");
    if (sizeBtn) sizeBtn.addEventListener("click", () => {
      const cfg = getWidgetConfig();
      const w = cfg.find(x => x.id === card.dataset.widgetId);
      w.size = w.size === "wide" ? "normal" : "wide";
      saveWidgetConfig(cfg);
      renderWidgetsGrid();
    });
    const hideBtn = card.querySelector(".widget-hide-btn");
    if (hideBtn) hideBtn.addEventListener("click", () => {
      const cfg = getWidgetConfig();
      const w = cfg.find(x => x.id === card.dataset.widgetId);
      w.visible = !w.visible;
      saveWidgetConfig(cfg);
      renderWidgetsGrid();
    });
  });
}

function toggleDashboardEditMode() {
  state.dashboardEditMode = !state.dashboardEditMode;
  document.getElementById("dashboard-edit-btn").textContent = state.dashboardEditMode ? t("editDashboardDone") : t("editDashboard");
  renderWidgetsGrid();
}

async function loadDashboard() {
  if (!state.availableYears) {
    state.availableYears = await api.get("/api/games/years");
  }
  const url = "/api/stats" + (state.chartsYearFilter ? `?year=${state.chartsYearFilter}` : "");
  state.lastStats = await api.get(url);
  renderWidgetsGrid();
}

// ============================================================ Grid views
async function renderGrid(status, query, availableFilter, yearFilter, dlcFilter, abandonedFilter) {
  let url = `/api/games?status=${status}`;
  if (query) url += `&q=${encodeURIComponent(query)}`;
  if (availableFilter) url += `&available=${availableFilter}`;
  if (yearFilter) url += `&year=${yearFilter}`;
  if (dlcFilter) url += `&dlc=${dlcFilter}`;
  if (abandonedFilter) url += `&abandoned=${abandonedFilter}`;
  const games = await api.get(url);
  state.gamesCache[status] = games;
  const gridEl = document.getElementById(`${status}-grid`);
  const prefs = getUiPrefs();
  const sortMode = getSortMode(status);
  const sortedGames = sortGamesForDisplay(games, sortMode);
  renderChronoArrow(status);

  const addTileHtml = `
    <div class="tile tile-add" id="add-tile">
      <span class="plus">+</span><span>${t("addTile")}</span>
    </div>`;

  // Year bands only make sense if the display follows a chronological
  // order (the file's original order naturally is, for finished games); an
  // alphabetical sort disables them.
  const chronoModes = ["original", "chrono", "chrono-rev"];
  const showYearBands = status === "completed" && prefs.showYearBands && !yearFilter && chronoModes.includes(sortMode);
  let gamesHtml;
  if (showYearBands) {
    let lastYear = undefined;
    gamesHtml = sortedGames.map(g => {
      let band = "";
      if (g.year_finished !== lastYear) {
        lastYear = g.year_finished;
        band = `<div class="year-band"><span>${g.year_finished ? g.year_finished : "—"}</span></div>`;
      }
      return band + renderTile(g);
    }).join("");
  } else {
    gamesHtml = sortedGames.map(g => renderTile(g)).join("");
  }

  const specialStart = prefs.addButtonPos === "start" ? addTileHtml : "";
  const specialEnd = prefs.addButtonPos === "end" ? addTileHtml : "";

  gridEl.innerHTML = specialStart + gamesHtml + specialEnd;

  document.getElementById("add-tile").addEventListener("click", () => openGameModal(null, status));

  gridEl.querySelectorAll(".tile[data-id]").forEach(tile => {
    tile.addEventListener("click", () => {
      const game = state.gamesCache[status].find(g => g.id == tile.dataset.id);
      openGameModal(game, status);
    });
  });
}

function renderTile(g) {
  const coverStyle = g.cover_path ? `background-image:url('${escapeHtml(g.cover_path)}')` : "";
  const spineColor = g.rating ? "var(--accent-2)" : "var(--border)";
  const ownedColor = g.available === 1 ? "var(--accent-2)" : (g.available === 0 ? "var(--danger)" : "transparent");
  const prefs = getUiPrefs();
  const isAbandoned = !!g.abandoned;
  const showTag = isAbandoned && prefs.abandonedTag;
  const showGrey = isAbandoned && prefs.abandonedGrey;
  const showStrike = isAbandoned && prefs.abandonedStrike;
  return `
    <div class="tile" data-id="${g.id}" style="--tile-gradient:${gradientFor(g.title)}">
      <div class="tile-spine" style="background:${spineColor}"></div>
      ${showTag ? `<div class="tile-abandoned-badge">${t("abandonedBadge")}</div>` : ""}
      ${g.dlc ? `<div class="tile-dlc-badge ${showTag ? "stacked" : ""}">DLC</div>` : ""}
      ${g.available !== null && g.available !== undefined ? `<div class="tile-owned-dot" style="background:${ownedColor}"></div>` : ""}
      <div class="tile-cover ${g.cover_path ? "" : "tile-cover-fallback"} ${showGrey ? "tile-cover-greyed" : ""}" style="${coverStyle}">
        <div class="tile-info">
          <div class="tile-title ${showStrike ? "tile-title-strike" : ""}">${escapeHtml(g.title)}</div>
        </div>
      </div>
      ${g.rating ? `<div class="tile-badge">★ ${g.rating}</div>` : ""}
    </div>`;
}

// ============================================================ Modal: game details / edit
function closeModal() {
  document.getElementById("game-modal").classList.add("hidden");
}

function openGameModal(game, status) {
  const isNew = !game;
  const g = game || {
    title: "", status, hours_estimated: null, hours_played: null, rating: 0, review: "",
    notes: "", available: status === "completed" ? 1 : null, worth_it: "", date_completed: "", dlc: 0, abandoned: 0,
  };
  const body = document.getElementById("modal-body");
  const isCompleted = (g.status || status) === "completed";

  const coverHtml = !isNew ? `
    <div class="modal-cover-small" style="background:${g.cover_path ? `url('${escapeHtml(g.cover_path)}') center/cover` : gradientFor(g.title || "?")}">
      ${g.dlc ? `<div class="tile-dlc-badge">DLC</div>` : ""}
    </div>
    <div class="modal-cover-actions">
      <button class="btn btn-outline btn-sm" id="cover-search-btn" style="margin-bottom:0;">${t("modalCoverSearch")}</button>
      <label class="btn btn-outline btn-sm" style="margin-bottom:0;text-align:center;">
        ${t("modalCoverUpload")}<input type="file" id="cover-upload-input" accept="image/*" style="display:none;">
      </label>
      ${g.cover_path ? `<button class="btn btn-outline btn-sm" id="cover-edit-btn" style="margin-bottom:0;">${t("coverEditorEditBtn")}</button>` : ""}
    </div>` : "";

  const commonFields = `
    <div class="field">
      <label>${t("modalTitle")}</label>
      <input type="text" id="f-title" value="${escapeHtml(g.title || "")}">
    </div>
    <div class="field-row">
      <div class="field">
        <label>${t("modalHoursEst")}</label>
        <input type="number" step="0.5" id="f-hours-est" value="${g.hours_estimated ?? ""}">
      </div>
      <div class="field">
        <label>${t("modalHoursPlayed")}</label>
        <input type="number" step="0.5" id="f-hours-played" value="${g.hours_played ?? ""}">
      </div>
    </div>
    ${!isNew ? `
    <div class="field hltb-fetch-row ${g.hours_estimated ? "hidden" : ""}">
      <label>${t("modalHltbLabel")}</label>
      <div style="display:flex; gap:8px; align-items:center;">
        <select id="hltb-mode-select" class="filter-select">
          <option value="main">${t("hltbModeMain")}</option>
          <option value="main_extra">${t("hltbModeMainExtra")}</option>
          <option value="completionist">${t("hltbModeCompletionist")}</option>
        </select>
        <button class="btn btn-outline btn-sm" id="hltb-fetch-btn" style="margin-bottom:0;">${t("modalHltbFetchBtn")}</button>
      </div>
      <p id="hltb-status" class="hint"></p>
    </div>` : ""}
    <div class="field-row">
      <div class="field">
        <label>${t("modalAvailable")}</label>
        <select id="f-available">
          <option value="">—</option>
          <option value="1" ${g.available === 1 ? "selected" : ""}>${t("yes")}</option>
          <option value="0" ${g.available === 0 ? "selected" : ""}>${t("no")}</option>
        </select>
      </div>
      ${isCompleted ? `
      <div class="field">
        <label>${t("modalWorthIt")}</label>
        <select id="f-worthit">
          ${["Yes", "No", "Meh", "PEAK"].map(v => `<option value="${v}" ${g.worth_it === v ? "selected" : ""}>${v}</option>`).join("")}
        </select>
      </div>` : `
      <div class="field">
        <label>${t("modalStatus")}</label>
        <input type="text" id="f-notes" value="${escapeHtml(g.notes || "")}">
      </div>`}
    </div>`;

  let extraHtml = "";
  if (isCompleted) {
    extraHtml = `
    <div class="checkbox-field">
      <input type="checkbox" id="f-dlc" ${g.dlc ? "checked" : ""}>
      <label for="f-dlc">${t("modalDlc")}</label>
    </div>
    <div class="checkbox-field">
      <input type="checkbox" id="f-abandoned" ${g.abandoned ? "checked" : ""}>
      <label for="f-abandoned">${t("abandonedLabel")}</label>
    </div>
    <div class="field">
      <label>${t("modalRating")}</label>
      <div class="rating-stars-row">
        <div class="rating-stars-10" id="f-rating" data-value="${g.rating || 0}">${ratingStarsHtml(g.rating || 0)}</div>
        <span class="rating-value-display" id="rating-value-display">${g.rating || "—"}/10</span>
      </div>
    </div>
    <div class="field">
      <label>${t("modalDateCompleted")}</label>
      <div class="date-quick-row">
        <button type="button" class="chip" data-days="0">${t("chipToday")}</button>
        <button type="button" class="chip" data-days="1">${t("chipYesterday")}</button>
        <button type="button" class="chip" data-days="7">${t("chip7d")}</button>
        <button type="button" class="chip" data-days="30">${t("chip1m")}</button>
        <button type="button" class="chip" data-days="90">${t("chip3m")}</button>
        <button type="button" class="chip" data-days="365">${t("chip1y")}</button>
      </div>
      <input type="date" id="f-date-picker" value="${g.date_completed || ""}" min="1970-01-01" max="2100-12-31">
      <button type="button" class="link-btn" id="f-partial-date-toggle">${t("dateNoExactDay")}</button>
      <div class="date-select-row ${(g.month_finished && !g.date_completed) ? "" : "hidden"}" id="f-partial-date-row">
        <div class="field" style="margin-bottom:0;">
          <label>${t("dateYear")} *</label>
          <input type="number" id="f-year" min="1970" max="2100" value="${g.year_finished || ""}">
        </div>
        <div class="field" style="margin-bottom:0;">
          <label>${t("dateMonth")} *</label>
          <select id="f-month">
            <option value="">${t("dateSelectMonth")}</option>
            ${MONTHS_FR.map(m => `<option value="${m}" ${g.month_finished === m ? "selected" : ""}>${m}</option>`).join("")}
          </select>
        </div>
      </div>
      <div class="date-custom-row" style="margin-top:10px;">
        <span class="date-sep">${t("modalAgoLabel")}</span>
        <input type="number" id="f-ago-value" min="0" placeholder="0">
        <select id="f-ago-unit">
          <option value="days">${t("modalAgoDays")}</option>
          <option value="months">${t("modalAgoMonths")}</option>
          <option value="years">${t("modalAgoYears")}</option>
        </select>
        <button type="button" class="btn btn-outline btn-sm" id="f-ago-apply" style="width:auto;margin:0;">${t("modalAgoApply")}</button>
      </div>
    </div>`;
  }

  const reviewHtml = isCompleted && !isNew ? `
    <div class="review-section">
      <label style="display:block; font-size:12px; color:var(--text-muted); margin-bottom:8px; text-transform:uppercase; letter-spacing:.03em;">${t("modalReview")}</label>
      <div id="review-display" class="review-display">${g.review ? mdToHtml(g.review) : `<p class="hint">${t("modalReviewEmpty")}</p>`}</div>
      <textarea id="review-edit" class="review-edit-clean hidden" spellcheck="true" placeholder="${t('modalReviewPlaceholder')}">${escapeHtml(g.review || "")}</textarea>
      <div style="margin-top:10px;display:flex;gap:8px;">
        <button class="btn btn-outline btn-sm" id="review-toggle-btn" style="width:auto;margin:0;">${g.review ? t("modalReviewEdit") : t("modalReviewAdd")}</button>
        <button class="btn btn-primary btn-sm hidden" id="review-save-btn" style="width:auto;margin:0;">${t("modalReviewSave")}</button>
        <button class="btn btn-ghost btn-sm hidden" id="review-cancel-btn" style="width:auto;margin:0;">${t("modalReviewCancel")}</button>
      </div>
    </div>` : "";

  const actionsHtml = `
    <div class="modal-actions">
      <button class="btn btn-primary" id="save-btn">${t("modalSave")}</button>
      ${!isNew ? `<button class="btn btn-danger" id="delete-btn">${t("modalDelete")}</button>` : ""}
    </div>
    ${!isNew ? `<button class="btn btn-ghost btn-sm" id="switch-status-btn" style="margin-top:6px;">${isCompleted ? t("modalMoveToBacklog") : t("modalMoveToCompleted")}</button>` : ""}`;

  if (isNew) {
    body.innerHTML = `<h3>${t("modalNewGameTitle")}</h3>` + commonFields + extraHtml + actionsHtml;
  } else {
    body.innerHTML = `
      <h3>${escapeHtml(g.title)}</h3>
      <div class="modal-top">
        <div>${coverHtml}</div>
        <div class="modal-fields-compact">${commonFields}${extraHtml}</div>
      </div>
      ${reviewHtml}
      ${actionsHtml}`;
  }

  document.getElementById("game-modal").classList.remove("hidden");
  bindModalEvents(g, status, isNew, isCompleted);
}

// ============================================================ Date picker helper (input[type=date] uses local YYYY-MM-DD, no manual typing needed)
function setDatePickerValue(dateObj) {
  const iso = `${dateObj.getFullYear()}-${String(dateObj.getMonth() + 1).padStart(2, "0")}-${String(dateObj.getDate()).padStart(2, "0")}`;
  const input = document.getElementById("f-date-picker");
  if (input) input.value = iso;
  // also hide the manual month/year fallback — an exact date is now set
  const fallback = document.getElementById("f-partial-date-row");
  if (fallback) fallback.classList.add("hidden");
}

function bindModalEvents(g, status, isNew, isCompleted) {
  if (isCompleted) {
    bindRatingStars();

    document.querySelectorAll(".chip").forEach(chip => {
      chip.addEventListener("click", () => {
        document.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
        chip.classList.add("active");
        const d = new Date();
        d.setDate(d.getDate() - parseInt(chip.dataset.days, 10));
        setDatePickerValue(d);
      });
    });
    document.getElementById("f-ago-apply").addEventListener("click", () => {
      const val = parseInt(document.getElementById("f-ago-value").value, 10) || 0;
      const unit = document.getElementById("f-ago-unit").value;
      const d = new Date();
      if (unit === "days") d.setDate(d.getDate() - val);
      else if (unit === "months") d.setMonth(d.getMonth() - val);
      else if (unit === "years") d.setFullYear(d.getFullYear() - val);
      setDatePickerValue(d);
      document.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
    });
    document.getElementById("f-date-picker").addEventListener("change", (e) => {
      document.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
      if (e.target.value) document.getElementById("f-partial-date-row").classList.add("hidden");
    });
    const partialToggle = document.getElementById("f-partial-date-toggle");
    partialToggle.addEventListener("click", () => {
      const row = document.getElementById("f-partial-date-row");
      const willShow = row.classList.contains("hidden");
      row.classList.toggle("hidden");
      if (willShow) {
        // "I don't know the exact day" — clear the precise date picker so
        // there's no ambiguity about which one wins on save.
        document.getElementById("f-date-picker").value = "";
      }
    });

    if (!isNew) {
      const toggleBtn = document.getElementById("review-toggle-btn");
      const saveBtn = document.getElementById("review-save-btn");
      const cancelBtn = document.getElementById("review-cancel-btn");
      const display = document.getElementById("review-display");
      const editArea = document.getElementById("review-edit");

      toggleBtn.addEventListener("click", () => {
        display.classList.add("hidden");
        editArea.classList.remove("hidden");
        toggleBtn.classList.add("hidden");
        saveBtn.classList.remove("hidden");
        cancelBtn.classList.remove("hidden");
        editArea.focus();
      });
      cancelBtn.addEventListener("click", () => {
        editArea.value = g.review || "";
        display.classList.remove("hidden");
        editArea.classList.add("hidden");
        toggleBtn.classList.remove("hidden");
        saveBtn.classList.add("hidden");
        cancelBtn.classList.add("hidden");
      });
      saveBtn.addEventListener("click", async () => {
        const newReview = editArea.value;
        const updated = await api.put(`/api/games/${g.id}`, { review: newReview });
        g.review = updated.review;
        display.innerHTML = g.review ? mdToHtml(g.review) : `<p class="hint">${t("modalReviewEmpty")}</p>`;
        display.classList.remove("hidden");
        editArea.classList.add("hidden");
        toggleBtn.textContent = g.review ? t("modalReviewEdit") : t("modalReviewAdd");
        toggleBtn.classList.remove("hidden");
        saveBtn.classList.add("hidden");
        cancelBtn.classList.add("hidden");
        refreshCurrentView();
      });
    }
  }

  const coverSearchBtn = document.getElementById("cover-search-btn");
  if (coverSearchBtn) coverSearchBtn.addEventListener("click", async () => {
    const consented = await ensureInternetConsent();
    if (consented) openCoverSearchModal(g);
  });
  const coverUploadInput = document.getElementById("cover-upload-input");
  if (coverUploadInput) coverUploadInput.addEventListener("change", (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const objectUrl = URL.createObjectURL(f);
    openCoverEditor(objectUrl, async (blob) => {
      URL.revokeObjectURL(objectUrl);
      const res = await uploadCoverBlob(g.id, blob);
      if (res.cover_path) {
        g.cover_path = res.cover_path;
        showToast(t("coverUpdatedToast"), "success");
        document.querySelector(".modal-cover-small").style.background = `url('${res.cover_path}') center/cover`;
        refreshCurrentView();
      } else {
        showToast(res.error || t("coverSearchFailedToast"), "warning");
      }
    });
    coverUploadInput.value = ""; // allow re-selecting the same file later
  });
  const coverEditBtn = document.getElementById("cover-edit-btn");
  if (coverEditBtn) coverEditBtn.addEventListener("click", () => {
    // g.cover_path is already same-origin (served by our own app), so no
    // proxy needed here — only third-party URLs require that.
    openCoverEditor(g.cover_path, async (blob) => {
      const res = await uploadCoverBlob(g.id, blob);
      if (res.cover_path) {
        g.cover_path = res.cover_path;
        showToast(t("coverUpdatedToast"), "success");
        document.querySelector(".modal-cover-small").style.background = `url('${res.cover_path}') center/cover`;
        refreshCurrentView();
      } else {
        showToast(res.error || t("coverSearchFailedToast"), "warning");
      }
    });
  });

  const hltbFetchBtn = document.getElementById("hltb-fetch-btn");
  const hltbRow = document.querySelector(".hltb-fetch-row");
  const hoursEstInput = document.getElementById("f-hours-est");
  if (hoursEstInput && hltbRow) {
    // Purely client-side visibility toggle — no request is made here, only
    // when the user actually clicks "Fetch HowLongToBeat" below. This lets
    // the prompt reappear the moment the estimate is cleared, without
    // requiring a Save first and without any auto-save happening.
    hoursEstInput.addEventListener("input", () => {
      const isEmpty = hoursEstInput.value.trim() === "";
      hltbRow.classList.toggle("hidden", !isEmpty);
      if (isEmpty) {
        document.getElementById("hltb-status").textContent = "";
        if (hltbFetchBtn) hltbFetchBtn.disabled = false;
      }
    });
  }
  if (hltbFetchBtn) hltbFetchBtn.addEventListener("click", async () => {
    const mode = document.getElementById("hltb-mode-select").value;
    const statusEl = document.getElementById("hltb-status");
    hltbFetchBtn.disabled = true;
    const stopLoading = startLoadingDots(statusEl);
    const res = await api.post(`/api/games/${g.id}/fetch-hltb`, { mode });
    stopLoading();
    if (res.error) {
      statusEl.textContent = res.code === "no_match" ? t("hltbNoMatch") : res.error;
      hltbFetchBtn.disabled = false;
      return;
    }
    document.getElementById("f-hours-est").value = res.hours_estimated;
    document.querySelector(".hltb-fetch-row").classList.add("hidden");
    showToast(t("hltbFetchSuccess").replace("{hours}", res.hours_estimated), "success");
  });

  document.getElementById("save-btn").addEventListener("click", () => saveGame(g, status, isNew, isCompleted));

  const switchBtn = document.getElementById("switch-status-btn");
  if (switchBtn) switchBtn.addEventListener("click", async () => {
    if (isCompleted) {
      if (g.review && g.review.trim()) {
        showToast(t("moveToBacklogBlocked"), "warning");
        return;
      }
      const ok = await showConfirm({
        message: t("confirmMoveToBacklogMsg"), okLabel: t("modalMoveToBacklog"),
        cancelLabel: t("confirmCancel"), danger: false,
      });
      if (!ok) return;
      await api.put(`/api/games/${g.id}`, { status: "backlog" });
      closeModal();
      refreshCurrentView();
    } else {
      // mark as finished: reopen the sheet in "completed" mode with today's
      // date pre-filled, to choose/adjust before confirming via Save.
      // "I own it" defaults to Yes (you played it, by definition); the user
      // can switch it back to No before saving.
      const today = new Date();
      openGameModal({
        ...g, status: "completed", available: 1,
        year_finished: g.year_finished || today.getFullYear(),
        month_finished: g.month_finished || MONTHS_FR[today.getMonth()],
        date_completed: g.date_completed || today.toISOString().slice(0, 10),
      }, "completed");
    }
  });

  const deleteBtn = document.getElementById("delete-btn");
  if (deleteBtn) deleteBtn.addEventListener("click", async () => {
    const ok = await showConfirm({
      message: t("confirmDeleteMsg").replace("{title}", g.title),
      okLabel: t("confirmDelete"), cancelLabel: t("confirmCancel"), danger: true,
    });
    if (ok) {
      await api.del(`/api/games/${g.id}`);
      closeModal();
      refreshCurrentView();
    }
  });
}

async function saveGame(g, status, isNew, isCompleted, forceDuplicate) {
  const data = {
    title: document.getElementById("f-title").value.trim(),
    hours_estimated: parseFloat(document.getElementById("f-hours-est").value) || null,
    hours_played: parseFloat(document.getElementById("f-hours-played").value) || null,
    status: isCompleted ? "completed" : "backlog",
  };
  if (!data.title) { showToast(t("titleRequired"), "warning"); return; }
  const avail = document.getElementById("f-available").value;
  data.available = avail === "" ? null : parseInt(avail, 10);
  if (forceDuplicate) data.force_duplicate = true;

  if (isCompleted) {
    data.worth_it = document.getElementById("f-worthit").value;
    data.rating = parseFloat(document.getElementById("f-rating").dataset.value) || 0;
    data.dlc = document.getElementById("f-dlc").checked ? 1 : 0;
    data.abandoned = document.getElementById("f-abandoned").checked ? 1 : 0;

    const datePicked = document.getElementById("f-date-picker").value;
    const fallbackVisible = !document.getElementById("f-partial-date-row").classList.contains("hidden");
    if (datePicked && !fallbackVisible) {
      const [year, month, day] = datePicked.split("-");
      data.year_finished = parseInt(year, 10);
      data.month_finished = MONTHS_FR[parseInt(month, 10) - 1];
      data.date_completed = datePicked;
    } else {
      const year = document.getElementById("f-year").value;
      const month = document.getElementById("f-month").value;
      if (!year || !month) {
        showToast(t("dateYearMonthRequired"), "warning");
        return;
      }
      data.year_finished = parseInt(year, 10);
      data.month_finished = month;
      data.date_completed = null;
    }
  } else {
    data.notes = document.getElementById("f-notes").value;
  }

  const res = isNew ? await api.post("/api/games", data) : await api.put(`/api/games/${g.id}`, data);

  if (res.error === "duplicate" && !forceDuplicate) {
    const conflict = res.conflict;
    const otherListLabel = conflict.status === "completed" ? t("navCompleted") : t("navBacklog");
    const wantsProceed = await showConfirm({
      message: t("duplicateConflictMsg")
        .replace("{title}", `« ${conflict.title} »`)
        .replace("{list}", otherListLabel),
      okLabel: t("duplicateKeepBoth"), cancelLabel: t("confirmCancel"), danger: false,
    });
    if (!wantsProceed) return;

    if (conflict.status === "backlog" && data.status === "completed") {
      const wantsDelete = await showConfirm({
        message: t("duplicateDeleteBacklogMsg").replace("{title}", `« ${conflict.title} »`),
        okLabel: t("duplicateDeleteBacklogBtn"), cancelLabel: t("duplicateKeepBoth"), danger: true,
      });
      if (wantsDelete) await api.del(`/api/games/${conflict.id}`);
    }
    return saveGame(g, status, isNew, isCompleted, true);
  }

  closeModal();
  refreshCurrentView();
}

function refreshCurrentView() {
  if (state.view === "dashboard") loadDashboard();
  else renderCurrentGrid();
}

// ============================================================ Bulk cover fill ("recherche rapide")
async function startBulkCoverFill() {
  const noticeShown = await maybeShowFirstScanNotice();
  if (!noticeShown) return; // user cancelled from the notice
  const consented = await ensureInternetConsent();
  if (!consented) return;
  const ok = await showConfirm({
    message: t("fillCoversConfirm"), okLabel: t("fillCoversBtn"),
    cancelLabel: t("confirmCancel"), danger: false,
  });
  if (!ok) return;
  const res = await api.post("/api/covers/bulk-fill");
  if (!res.started && !res.status.running) {
    showToast(t("fillCoversAlreadyRunning"), "warning");
    return;
  }
  pollBulkCoverStatus();
}

async function maybeShowFirstScanNotice() {
  const settings = await api.get("/api/settings");
  if (settings.cover_scan_notice_dismissed) return true;
  return new Promise((resolve) => {
    const overlay = document.getElementById("first-scan-notice-modal");
    const body = document.getElementById("first-scan-notice-body");
    body.innerHTML = `
      <h3>${t("firstScanNoticeTitle")}</h3>
      <p>${t("firstScanNoticeBody")}</p>
      <div class="modal-actions">
        <button class="btn btn-outline" id="first-scan-notice-skip">${t("firstScanNoticeSkip")}</button>
        <button class="btn btn-primary" id="first-scan-notice-sanitize">${t("firstScanNoticeSanitize")}</button>
      </div>`;
    overlay.classList.remove("hidden");
    const dismiss = async (proceedWithScan) => {
      overlay.classList.add("hidden");
      await api.post("/api/sanitize/dismiss-first-scan-notice");
      resolve(proceedWithScan);
    };
    document.getElementById("first-scan-notice-skip").addEventListener("click", () => dismiss(true));
    document.getElementById("first-scan-notice-sanitize").addEventListener("click", async () => {
      overlay.classList.add("hidden");
      await api.post("/api/sanitize/dismiss-first-scan-notice");
      openSanitizeModal();
      resolve(false); // don't proceed with the cover scan right now
    });
  });
}

function pollBulkCoverStatus() {
  document.getElementById("bulk-cover-progress").classList.remove("hidden");
  document.getElementById("bulk-cover-btn").classList.add("hidden");

  const tick = async () => {
    let status;
    try {
      status = await api.get("/api/covers/bulk-fill/status");
    } catch (e) {
      setTimeout(tick, 1500);
      return;
    }
    const pct = status.total ? Math.round((status.done / status.total) * 100) : 100;
    document.getElementById("bulk-progress-fill").style.width = pct + "%";
    document.getElementById("bulk-progress-text").textContent = status.running
      ? `${status.done}/${status.total} — ${status.current || ""}`
      : `${t("fillCoversDone")} (${status.found}/${status.total})`;

    if (status.running) {
      setTimeout(tick, 1000);
    } else {
      document.getElementById("bulk-cover-progress").classList.add("hidden");
      document.getElementById("bulk-cover-btn").classList.remove("hidden");
      refreshCurrentView();
    }
  };
  tick();
}

// ============================================================ Animated loading indicator ("Loading ." / ".." / "...", looped)
function startLoadingDots(el, labelKey = "loadingLabel") {
  if (!el) return () => {};
  let n = 0;
  const render = () => {
    n = (n % 3) + 1;
    el.textContent = `${t(labelKey)} ${".".repeat(n)}`;
  };
  render();
  const timer = setInterval(render, 450);
  return () => clearInterval(timer);
}

// ============================================================ Cover search (style SteamGridDB, + correspondance locale)
function openCoverSearchModal(g) {
  const body = document.getElementById("modal-body");
  body.innerHTML = `
    <h3>${t("coverSearchTitle")}</h3>
    <div id="local-match-slot"></div>
    <div class="field-row" style="margin-bottom:16px;">
      <input type="text" id="cover-query" value="${escapeHtml(g.title)}" placeholder="${t('coverSearchPlaceholder')}">
      <button class="btn btn-primary" id="cover-query-btn">${t("coverSearchGo")}</button>
    </div>
    <div id="cover-results" class="grid" style="grid-template-columns:repeat(auto-fill,minmax(110px,1fr));"></div>
    <button class="btn btn-ghost btn-block" id="cover-back-btn">← ${t("modalReviewCancel")}</button>
  `;
  const editCoverFromSearch = (payload) => {
    // Both sources get resolved to a same-origin URL before opening the
    // editor: local matches are already served by our own app; online
    // results go through /api/cover-proxy first (a canvas fed directly
    // from a cross-origin, non-CORS image can't be exported afterwards).
    const sourceUrl = payload.local_filename
      ? `/api/cover-art-preview/${encodeURIComponent(payload.local_filename)}`
      : `/api/cover-proxy?url=${encodeURIComponent(payload.url)}`;
    openCoverEditor(sourceUrl, async (blob) => {
      const res = await uploadCoverBlob(g.id, blob);
      if (res.cover_path) {
        g.cover_path = res.cover_path;
        showToast(t("coverUpdatedToast"), "success");
        openGameModal(g, g.status);
        refreshCurrentView();
      } else {
        showToast(res.error || t("coverSearchFailedToast"), "warning");
      }
    });
  };
  const runSearch = async () => {
    const query = document.getElementById("cover-query").value;
    const resultsEl = document.getElementById("cover-results");
    const localSlot = document.getElementById("local-match-slot");
    resultsEl.innerHTML = `<p class="hint" id="cover-search-loading"></p>`;
    const stopLoading = startLoadingDots(document.getElementById("cover-search-loading"));
    localSlot.innerHTML = "";
    const data = await api.get(`/api/cover-search?title=${encodeURIComponent(query)}`);
    stopLoading();

    if (data.local_match) {
      localSlot.innerHTML = `
        <div class="local-match-card">
          <img src="${data.local_match.preview_url}" alt="">
          <div class="local-match-info">
            <strong>${t("localCoverFound")}</strong>
            ${data.local_match.filename}
            ${data.online && data.online.length ? `<div style="margin-top:6px;">${t("localCoverOr")}</div>` : ""}
          </div>
          <div class="local-match-actions">
            <button class="btn btn-primary btn-sm" id="use-local-cover-btn" style="width:auto;margin:0;">${t("localCoverUse")}</button>
          </div>
        </div>`;
      document.getElementById("use-local-cover-btn").addEventListener("click", () => editCoverFromSearch({ local_filename: data.local_match.filename }));
    }

    const results = data.online || [];
    if (!results.length) {
      resultsEl.innerHTML = `<p class="hint">${t("coverSearchEmpty")}</p>`;
      return;
    }
    resultsEl.innerHTML = results.map((r, i) => `
      <div class="tile" data-url="${r.cover_url}" data-idx="${i}" style="aspect-ratio:2/3;">
        <img data-src="${r.cover_url}" data-fallback="${r.fallback_url || ""}" loading="lazy" style="width:100%;height:100%;object-fit:cover;">
      </div>`).join("");

    // Bounded error handling (never a loop): if the image fails, try at
    // most once with a possible distinct 2nd URL, then remove the thumbnail
    // entirely rather than leaving a broken/flickering image on screen. If
    // everything fails, show the "no results" message.
    let remaining = results.length;
    let loadedCount = 0;
    const checkAllFailed = () => {
      if (remaining <= 0 && loadedCount === 0) {
        resultsEl.innerHTML = `<p class="hint">${t("coverSearchEmpty")}</p>`;
      }
    };
    resultsEl.querySelectorAll(".tile img").forEach(img => {
      img.addEventListener("load", () => { loadedCount++; }, { once: true });
      img.addEventListener("error", function onError() {
        const fallback = img.dataset.fallback;
        if (fallback && fallback !== img.dataset.src) {
          img.dataset.fallback = ""; // won't retry again after this, no matter what
          img.src = fallback;
        } else {
          img.removeEventListener("error", onError);
          const tile = img.closest(".tile");
          if (tile) tile.remove();
          remaining--;
          checkAllFailed();
        }
      });
      img.src = img.dataset.src;
    });
    resultsEl.querySelectorAll(".tile").forEach(tile => {
      tile.addEventListener("click", () => editCoverFromSearch({ url: tile.dataset.url }));
    });
  };
  document.getElementById("cover-query-btn").addEventListener("click", runSearch);
  document.getElementById("cover-back-btn").addEventListener("click", () => openGameModal(g, g.status));
  runSearch();
}

// ============================================================ Interface options (top-right button)
function closeOptionsModal() {
  document.getElementById("options-modal").classList.add("hidden");
}

async function openOptionsModal() {
  const prefs = getUiPrefs();
  const settings = await api.get("/api/settings");
  const body = document.getElementById("options-body");

  body.innerHTML = `
    <h3>${t("optionsTitle")}</h3>
    <div class="settings-section">
      <h4>${t("optionsPersonalization")}</h4>
      <div class="field">
        <label>${t("optionsPlayerName")}</label>
        <input type="text" id="opt-player-name" value="${escapeHtml(settings.player_name || "")}" placeholder="${t('optionsPlayerNamePlaceholder')}">
        <p class="hint">${t("optionsPlayerNameHint")}</p>
      </div>
      <div class="field">
        <label>${t("optionsAddButtonPos")}</label>
        <select id="opt-add-pos">
          <option value="start" ${prefs.addButtonPos === "start" ? "selected" : ""}>${t("posStart")}</option>
          <option value="end" ${prefs.addButtonPos === "end" ? "selected" : ""}>${t("posEnd")}</option>
        </select>
      </div>
    </div>
    <div class="settings-section">
      <h4>${t("optionsTabs")}</h4>
      <div class="field">
        <label>${t("optionsTabBacklog")}</label>
        <input type="text" id="opt-tab-backlog" value="${escapeHtml(prefs.tabBacklog)}" placeholder="${t('navBacklog')}">
      </div>
      <div class="field">
        <label>${t("optionsTabCompleted")}</label>
        <input type="text" id="opt-tab-completed" value="${escapeHtml(prefs.tabCompleted)}" placeholder="${t('navCompleted')}">
      </div>
    </div>
    <div class="settings-section">
      <h4>${t("abandonedDisplayTitle")}</h4>
      <div class="checkbox-field">
        <input type="checkbox" id="opt-abandoned-tag" ${prefs.abandonedTag ? "checked" : ""}>
        <label for="opt-abandoned-tag">${t("abandonedDisplayTag")}</label>
      </div>
      <div class="checkbox-field">
        <input type="checkbox" id="opt-abandoned-grey" ${prefs.abandonedGrey ? "checked" : ""}>
        <label for="opt-abandoned-grey">${t("abandonedDisplayGrey")}</label>
      </div>
      <div class="checkbox-field">
        <input type="checkbox" id="opt-abandoned-strike" ${prefs.abandonedStrike ? "checked" : ""}>
        <label for="opt-abandoned-strike">${t("abandonedDisplayStrike")}</label>
      </div>
    </div>
    <button class="btn btn-primary btn-block" id="opt-save-btn">${t("modalSave")}</button>
    <p class="hint" id="opt-saved-msg" style="text-align:center;"></p>
  `;

  document.getElementById("options-modal").classList.remove("hidden");

  document.getElementById("opt-save-btn").addEventListener("click", async () => {
    const playerName = document.getElementById("opt-player-name").value.trim();
    saveUiPrefs({
      addButtonPos: document.getElementById("opt-add-pos").value,
      tabBacklog: document.getElementById("opt-tab-backlog").value.trim(),
      tabCompleted: document.getElementById("opt-tab-completed").value.trim(),
      abandonedTag: document.getElementById("opt-abandoned-tag").checked,
      abandonedGrey: document.getElementById("opt-abandoned-grey").checked,
      abandonedStrike: document.getElementById("opt-abandoned-strike").checked,
    });
    await api.post("/api/settings", { player_name: playerName });
    setCachedPlayerName(playerName);
    renderPlayerNameTag();
    applyTabLabels();
    document.getElementById("view-title").textContent = tabLabel(state.view);
    document.getElementById("opt-saved-msg").textContent = "✅ " + t("optionsSaved");
    refreshCurrentView();
  });
}

// ============================================================ My Year Review
function closeYearReviewModal() {
  document.getElementById("year-review-modal").classList.add("hidden");
}

// ============================================================ Sanitize Game Names
async function startSanitizeScan() {
  const settings = await api.get("/api/settings");
  const allowExternal = !!settings.internet_search_consent || await ensureInternetConsent();
  const ok = await showConfirm({
    message: t("sanitizeScanConfirm"), okLabel: t("sanitizeNamesBtn"),
    cancelLabel: t("confirmCancel"), danger: false,
  });
  if (!ok) return;
  const res = await api.post("/api/sanitize/scan", { allow_external: allowExternal });
  if (res.error) {
    showToast(res.error, "warning");
    return;
  }
  pollSanitizeStatus();
}

function pollSanitizeStatus() {
  document.getElementById("sanitize-progress").classList.remove("hidden");
  document.getElementById("sanitize-names-btn").classList.add("hidden");

  const tick = async () => {
    let status;
    try {
      status = await api.get("/api/sanitize/status");
    } catch (e) {
      // Never let a transient network hiccup leave the button permanently
      // hidden behind a stuck progress bar — retry rather than freeze.
      setTimeout(tick, 1500);
      return;
    }
    const pct = status.total ? Math.round((status.done / status.total) * 100) : 100;
    document.getElementById("sanitize-progress-fill").style.width = pct + "%";
    document.getElementById("sanitize-progress-text").textContent = status.running
      ? `${status.done}/${status.total} — ${status.current || ""}`
      : `${t("sanitizeScanDone")} (${status.suggested})`;

    if (status.running) {
      setTimeout(tick, 800);
    } else {
      document.getElementById("sanitize-progress").classList.add("hidden");
      document.getElementById("sanitize-names-btn").classList.remove("hidden");
      if (status.suggested > 0) {
        showToast(t("sanitizeScanSuggestionsToast").replace("{n}", status.suggested), "success");
        openSanitizeModal();
      } else {
        // Previously silent here — a completed scan with zero suggestions
        // looked identical to the button doing nothing at all.
        showToast(t("sanitizeScanNothingToast"), "info");
      }
    }
  };
  tick();
}

function closeSanitizeModal() {
  document.getElementById("sanitize-modal").classList.add("hidden");
}

async function openSanitizeModal() {
  document.getElementById("sanitize-modal").classList.remove("hidden");
  await renderSanitizeList();
}

async function renderSanitizeList() {
  const body = document.getElementById("sanitize-modal-body");
  const pending = await api.get("/api/sanitize/pending");
  if (!pending.length) {
    body.innerHTML = `<h3>${t("sanitizeModalTitle")}</h3><p class="hint">${t("sanitizeNothingPending")}</p>`;
    return;
  }
  body.innerHTML = `
    <h3>${t("sanitizeModalTitle")}</h3>
    <p class="hint">${t("sanitizeModalHint")}</p>
    <div class="orphan-suggestions-list" id="sanitize-list">
      ${pending.map(p => `
        <div class="orphan-item" data-game-id="${p.game_id}">
          <div class="orphan-item-text">${t("sanitizeItemText")
            .replace("{current}", `« ${escapeHtml(p.current_title)} »`)
            .replace("{suggested}", `« ${escapeHtml(p.suggested_name)} »`)}</div>
          <div class="orphan-item-actions">
            <button class="btn btn-primary btn-sm sanitize-accept-btn" data-id="${p.game_id}">${t("sanitizeAcceptBtn")}</button>
            <button class="btn btn-outline btn-sm sanitize-reject-btn" data-id="${p.game_id}">${t("orphanDismissBtn")}</button>
          </div>
        </div>`).join("")}
    </div>`;
  document.querySelectorAll(".sanitize-accept-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      await api.post(`/api/sanitize/${btn.dataset.id}/accept`);
      showToast(t("sanitizeAcceptedToast"), "success");
      await renderSanitizeList();
      refreshCurrentView();
    });
  });
  document.querySelectorAll(".sanitize-reject-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      await api.post(`/api/sanitize/${btn.dataset.id}/reject`);
      await renderSanitizeList();
    });
  });
}


// ============================================================ Cover art editor (Discord/GitHub-style crop, position, zoom)
const COVER_EXPORT_W = 600, COVER_EXPORT_H = 900; // matches the app's placeholder-cover dimensions
const coverEditorState = {
  img: null, fit: "crop", zoom: 1, offsetX: 0, offsetY: 0,
  dragging: false, dragStartX: 0, dragStartY: 0, dragOrigOffsetX: 0, dragOrigOffsetY: 0,
  onConfirm: null,
};

function openCoverEditor(imageUrl, onConfirm) {
  const modal = document.getElementById("cover-editor-modal");
  const hint = document.getElementById("cover-editor-hint");
  hint.textContent = t("coverEditorLoading");
  modal.classList.remove("hidden");
  coverEditorState.onConfirm = onConfirm;
  coverEditorState.img = null;

  const img = new Image();
  img.onload = () => {
    coverEditorState.img = img;
    hint.textContent = "";
    setCoverEditorFit("crop");
  };
  img.onerror = () => { hint.textContent = t("coverEditorLoadError"); };
  img.src = imageUrl;
}

function closeCoverEditor() {
  document.getElementById("cover-editor-modal").classList.add("hidden");
  coverEditorState.img = null;
  coverEditorState.onConfirm = null;
}

function setCoverEditorFit(fit) {
  coverEditorState.fit = fit;
  coverEditorState.zoom = 1;
  coverEditorState.offsetX = 0;
  coverEditorState.offsetY = 0;
  document.querySelectorAll(".cover-editor-fit-tab").forEach(tab => {
    tab.classList.toggle("active", tab.dataset.fit === fit);
  });
  document.getElementById("cover-editor-zoom-field").classList.toggle("disabled", fit === "stretch");
  document.getElementById("cover-editor-zoom").value = 100;
  drawCoverEditor();
}

function coverEditorBaseScale() {
  const { img, fit } = coverEditorState;
  if (!img) return { sx: 1, sy: 1 };
  if (fit === "stretch") {
    return { sx: COVER_EXPORT_W / img.naturalWidth, sy: COVER_EXPORT_H / img.naturalHeight };
  }
  // Crop & Fill/Cover both preserve aspect ratio, scaling uniformly until
  // the frame is fully covered — the difference is purely interactive
  // (Crop invites drag/zoom; Fill is the same math applied automatically,
  // centered, as a one-click reset).
  const s = Math.max(COVER_EXPORT_W / img.naturalWidth, COVER_EXPORT_H / img.naturalHeight);
  return { sx: s, sy: s };
}

function clampCoverEditorOffsets() {
  const { img, zoom, fit } = coverEditorState;
  if (!img || fit === "stretch") { coverEditorState.offsetX = 0; coverEditorState.offsetY = 0; return; }
  const base = coverEditorBaseScale();
  const drawW = img.naturalWidth * base.sx * zoom;
  const drawH = img.naturalHeight * base.sy * zoom;
  const maxOffsetX = Math.max(0, (drawW - COVER_EXPORT_W) / 2);
  const maxOffsetY = Math.max(0, (drawH - COVER_EXPORT_H) / 2);
  coverEditorState.offsetX = Math.min(maxOffsetX, Math.max(-maxOffsetX, coverEditorState.offsetX));
  coverEditorState.offsetY = Math.min(maxOffsetY, Math.max(-maxOffsetY, coverEditorState.offsetY));
}

function drawCoverEditor() {
  const canvas = document.getElementById("cover-editor-canvas");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, COVER_EXPORT_W, COVER_EXPORT_H);
  const { img, zoom, fit } = coverEditorState;
  if (!img) return;
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  const base = coverEditorBaseScale();
  const z = fit === "stretch" ? 1 : zoom;
  const drawW = img.naturalWidth * base.sx * z;
  const drawH = img.naturalHeight * base.sy * z;
  const x = (COVER_EXPORT_W - drawW) / 2 + coverEditorState.offsetX;
  const y = (COVER_EXPORT_H - drawH) / 2 + coverEditorState.offsetY;
  ctx.drawImage(img, x, y, drawW, drawH);
}

function bindCoverEditorDrag() {
  const canvas = document.getElementById("cover-editor-canvas");
  const pxToCanvas = () => COVER_EXPORT_W / canvas.clientWidth;

  const start = (clientX, clientY) => {
    if (!coverEditorState.img || coverEditorState.fit === "stretch") return;
    coverEditorState.dragging = true;
    coverEditorState.dragStartX = clientX;
    coverEditorState.dragStartY = clientY;
    coverEditorState.dragOrigOffsetX = coverEditorState.offsetX;
    coverEditorState.dragOrigOffsetY = coverEditorState.offsetY;
  };
  const move = (clientX, clientY) => {
    if (!coverEditorState.dragging) return;
    const f = pxToCanvas();
    coverEditorState.offsetX = coverEditorState.dragOrigOffsetX + (clientX - coverEditorState.dragStartX) * f;
    coverEditorState.offsetY = coverEditorState.dragOrigOffsetY + (clientY - coverEditorState.dragStartY) * f;
    clampCoverEditorOffsets();
    drawCoverEditor();
  };
  const end = () => { coverEditorState.dragging = false; };

  canvas.addEventListener("mousedown", (e) => start(e.clientX, e.clientY));
  window.addEventListener("mousemove", (e) => move(e.clientX, e.clientY));
  window.addEventListener("mouseup", end);
  canvas.addEventListener("touchstart", (e) => {
    if (e.touches.length === 1) start(e.touches[0].clientX, e.touches[0].clientY);
  }, { passive: true });
  canvas.addEventListener("touchmove", (e) => {
    if (e.touches.length === 1) { move(e.touches[0].clientX, e.touches[0].clientY); e.preventDefault(); }
  }, { passive: false });
  canvas.addEventListener("touchend", end);
  canvas.addEventListener("wheel", (e) => {
    if (!coverEditorState.img || coverEditorState.fit === "stretch") return;
    e.preventDefault();
    const slider = document.getElementById("cover-editor-zoom");
    const val = Math.min(400, Math.max(100, parseInt(slider.value, 10) + (e.deltaY < 0 ? 10 : -10)));
    slider.value = val;
    coverEditorState.zoom = val / 100;
    clampCoverEditorOffsets();
    drawCoverEditor();
  }, { passive: false });
}

function initCoverEditor() {
  document.querySelectorAll(".cover-editor-fit-tab").forEach(tab => {
    tab.addEventListener("click", () => setCoverEditorFit(tab.dataset.fit));
  });
  document.getElementById("cover-editor-zoom").addEventListener("input", (e) => {
    coverEditorState.zoom = parseInt(e.target.value, 10) / 100;
    clampCoverEditorOffsets();
    drawCoverEditor();
  });
  document.getElementById("cover-editor-reset-btn").addEventListener("click", () => {
    setCoverEditorFit(coverEditorState.fit);
  });
  document.getElementById("cover-editor-cancel-btn").addEventListener("click", closeCoverEditor);
  document.getElementById("cover-editor-close").addEventListener("click", closeCoverEditor);
  document.getElementById("cover-editor-confirm-btn").addEventListener("click", () => {
    if (!coverEditorState.img) return;
    const canvas = document.getElementById("cover-editor-canvas");
    canvas.toBlob((blob) => {
      if (blob && coverEditorState.onConfirm) coverEditorState.onConfirm(blob);
      closeCoverEditor();
    }, "image/png", 1.0);
  });
  bindCoverEditorDrag();
}

// Uploads an edited-cover blob via the same endpoint as a manual file
// upload, since a canvas export IS just an image file at that point.
async function uploadCoverBlob(gameId, blob) {
  const fd = new FormData();
  fd.append("cover", blob, "cover.png");
  return api.upload(`/api/games/${gameId}/cover`, fd);
}


function closeRandomPickerModal() {
  document.getElementById("random-picker-modal").classList.add("hidden");
}

async function openRandomPickerModal() {
  const modal = document.getElementById("random-picker-modal");
  const body = document.getElementById("random-picker-body");
  modal.classList.remove("hidden");
  body.innerHTML = `<h3>${t("randomPickTitle")}</h3><p class="hint">${t("randomPickLoading")}</p>`;

  // Pull the current backlog pool respecting whatever filters are already
  // active (available/DLC/abandoned/search), so the pick stays relevant to
  // what's actually being browsed rather than the entire backlog.
  const availableFilter = document.getElementById("filter-available").value;
  const dlcFilter = document.getElementById("filter-dlc").value;
  const abandonedFilter = document.getElementById("filter-abandoned").value;
  const query = document.getElementById("search-input").value;
  let url = "/api/games?status=backlog";
  if (query) url += `&q=${encodeURIComponent(query)}`;
  if (availableFilter) url += `&available=${availableFilter}`;
  if (dlcFilter) url += `&dlc=${dlcFilter}`;
  if (abandonedFilter) url += `&abandoned=${abandonedFilter}`;
  const games = await api.get(url);

  if (!games.length) {
    body.innerHTML = `<h3>${t("randomPickTitle")}</h3><p class="hint">${t("randomPickEmpty")}</p>`;
    return;
  }

  body.innerHTML = `
    <h3>${t("randomPickTitle")}</h3>
    <div class="random-picker-stage">
      <div class="random-picker-cover" id="random-picker-cover"></div>
      <div class="random-picker-name" id="random-picker-name"></div>
    </div>
    <div class="random-picker-actions hidden" id="random-picker-actions">
      <button class="btn btn-primary btn-sm" id="random-picker-open-btn">${t("randomPickOpenGame")}</button>
      <button class="btn btn-outline btn-sm" id="random-picker-reroll-btn">${t("randomPickReroll")}</button>
    </div>`;

  runRandomPickAnimation(games);
}

function runRandomPickAnimation(games) {
  const coverEl = document.getElementById("random-picker-cover");
  const nameEl = document.getElementById("random-picker-name");
  const actionsEl = document.getElementById("random-picker-actions");
  actionsEl.classList.add("hidden");
  coverEl.classList.remove("random-picker-winner");

  const finalIndex = Math.floor(Math.random() * games.length);
  // Cycles fast at first (short delays between tiles), slowing down toward
  // the end (ease-out), landing exactly on finalIndex on the last step —
  // decided up front, not just "wherever it happens to stop".
  const totalSteps = Math.max(18, Math.min(34, games.length * 3));
  let step = 0;

  const renderTile = (game) => {
    if (game.cover_path) {
      coverEl.style.background = `url('${game.cover_path}') center/cover`;
    } else {
      coverEl.style.background = gradientFor(game.title);
    }
    nameEl.textContent = game.title;
  };

  function tick() {
    step++;
    const progress = step / totalSteps;
    const delay = 40 + Math.pow(progress, 2.2) * 420; // ~40ms -> ~460ms

    const idx = step >= totalSteps ? finalIndex : Math.floor(Math.random() * games.length);
    renderTile(games[idx]);
    coverEl.classList.add("random-picker-pulse");
    setTimeout(() => coverEl.classList.remove("random-picker-pulse"), Math.min(delay * 0.8, 150));

    if (step >= totalSteps) {
      coverEl.classList.add("random-picker-winner");
      const openBtn = document.getElementById("random-picker-open-btn");
      const rerollBtn = document.getElementById("random-picker-reroll-btn");
      openBtn.onclick = async () => {
        const fullGame = await api.get(`/api/games/${games[finalIndex].id}`);
        closeRandomPickerModal();
        openGameModal(fullGame, "backlog");
      };
      rerollBtn.onclick = () => runRandomPickAnimation(games);
      actionsEl.classList.remove("hidden");
      return;
    }
    setTimeout(tick, delay);
  }
  tick();
}

async function openYearReviewModal() {
  const years = await api.get("/api/year-review/years");
  document.getElementById("year-review-modal").classList.remove("hidden");
  if (!years.length) {
    document.getElementById("year-review-body").innerHTML = `<h3>${t("yearReviewTitle")}</h3><p class="hint">${t("yearReviewNoData")}</p>`;
    return;
  }
  await renderYearReview(years[0], years);
}

async function renderYearReview(year, years) {
  const body = document.getElementById("year-review-body");
  const review = await api.get(`/api/year-review?year=${year}`);
  if (review.error) {
    body.innerHTML = `<h3>${t("yearReviewTitle")}</h3>${yearReviewNav(year, years)}<p class="hint">${t("yearReviewNoData")}</p>`;
    bindYearReviewNav(years);
    return;
  }

  const heroGame = review.best_rated_game || review.most_played_game;
  const heroCover = heroGame && heroGame.cover_path
    ? `url('${escapeHtml(heroGame.cover_path)}') center/cover`
    : gradientFor(heroGame ? heroGame.title : "?");

  const highlight = (icon, titleKey, game, metric) => {
    if (!game) return "";
    const coverStyle = game.cover_path ? `background-image:url('${escapeHtml(game.cover_path)}')` : `background:${gradientFor(game.title)}`;
    return `
      <div class="year-review-highlight">
        <div class="yr-cover" style="${coverStyle}"></div>
        <div>
          <div class="year-review-highlight-title">${icon} ${t(titleKey)}</div>
          <div class="year-review-highlight-game">${escapeHtml(game.title)}</div>
          <div class="year-review-highlight-meta">${metric}</div>
        </div>
      </div>`;
  };

  body.innerHTML = `
    <h3>${t("yearReviewTitle")} — ${year}</h3>
    ${yearReviewNav(year, years)}
    <div class="year-review-hero">
      <div class="year-review-hero-cover" style="background:${heroCover}"></div>
      <div class="year-review-stats-grid" style="flex:1;">
        ${statCard("🏆", review.nb_completed, "yearReviewNbCompleted")}
        ${statCard("⏱️", review.total_hours, "yearReviewTotalHours")}
        ${statCard("⭐", review.avg_rating ?? "—", "yearReviewAvgRating")}
      </div>
    </div>
    ${highlight("👑", "yearReviewBestRated", review.best_rated_game, review.best_rated_game ? `★ ${review.best_rated_game.rating}` : "")}
    ${highlight("🎮", "yearReviewMostPlayed", review.most_played_game, review.most_played_game ? `${review.most_played_game.hours_played} h` : "")}
    ${highlight("⚡", "yearReviewQuickest", review.quickest_game, review.quickest_game ? `${review.quickest_game.hours_played} h` : "")}
    ${review.longest_review_game ? `
      <div class="year-review-highlight">
        <div class="yr-cover" style="${review.longest_review_game.cover_path ? `background-image:url('${escapeHtml(review.longest_review_game.cover_path)}')` : `background:${gradientFor(review.longest_review_game.title)}`}"></div>
        <div>
          <div class="year-review-highlight-title">📝 ${t("yearReviewLongestReview")}</div>
          <div class="year-review-highlight-game">${escapeHtml(review.longest_review_game.title)}</div>
          <div class="year-review-excerpt">${mdToHtml(review.longest_review_game.review_excerpt)}…</div>
        </div>
      </div>` : ""}
  `;
  bindYearReviewNav(years);
}

function yearReviewNav(currentYear, years) {
  return `<div class="year-review-nav">${years.map(y =>
    `<button data-year="${y}" class="${y === currentYear ? "active" : ""}">${y}</button>`).join("")}</div>`;
}
function bindYearReviewNav(years) {
  document.querySelectorAll(".year-review-nav button").forEach(btn => {
    btn.addEventListener("click", () => renderYearReview(parseInt(btn.dataset.year, 10), years));
  });
}

// ============================================================ Settings (theme, language, backups)
function closeSettingsModal() {
  document.getElementById("settings-modal").classList.add("hidden");
}

async function openSettingsModal() {
  const lang = localStorage.getItem("backlog_lang") || "fr";
  const theme = currentTheme();
  const customColors = getCustomColors();
  const bgCfg = getBgMediaConfig();
  const settings = await api.get("/api/settings");
  const body = document.getElementById("settings-body");

  const a11yPrefs = getA11yPrefs();

  body.innerHTML = `
    <h3>${t("settingsTitle")}</h3>
    <div class="settings-section">
      <h4>${t("settingsAppearance")}</h4>
      <div class="theme-group-label">${t("themeGroupDark")}</div>
      <div class="theme-grid" id="theme-grid-dark">
        ${THEME_GROUPS.dark.map(key => themeSwatchHtml(key, theme)).join("")}
      </div>
      <div class="theme-group-label">${t("themeGroupLight")}</div>
      <div class="theme-grid" id="theme-grid-light">
        ${THEME_GROUPS.light.map(key => themeSwatchHtml(key, theme)).join("")}
      </div>
      <div class="theme-group-label">${t("themeGroupA11y")}</div>
      <div class="theme-grid" id="theme-grid-a11y">
        ${THEME_GROUPS.a11y.map(key => themeSwatchHtml(key, theme)).join("")}
        <div class="theme-swatch ${theme === "custom" ? "active" : ""}" data-theme="custom" id="custom-theme-swatch">
          <div class="theme-swatch-colors">
            <span style="background:${customColors.bg}"></span>
            <span style="background:${customColors.accent}"></span>
            <span style="background:${customColors.text}"></span>
          </div>
          <div class="theme-swatch-label">${t("themeCustom")}</div>
        </div>
      </div>
      <div class="field custom-theme-editor" id="custom-theme-editor" style="margin-top:14px;">
        <label>${t("settingsCustomColors")}</label>
        <div class="custom-color-grid">
          <div class="custom-color-field">
            <input type="color" id="custom-accent-input" value="${customColors.accent}">
            <span>${t("customColorAccent")}</span>
          </div>
          <div class="custom-color-field">
            <input type="color" id="custom-bg-input" value="${customColors.bg}">
            <span>${t("customColorBg")}</span>
          </div>
          <div class="custom-color-field">
            <input type="color" id="custom-card-input" value="${customColors.card}">
            <span>${t("customColorCard")}</span>
          </div>
          <div class="custom-color-field">
            <input type="color" id="custom-border-input" value="${customColors.border}">
            <span>${t("customColorBorder")}</span>
          </div>
          <div class="custom-color-field">
            <input type="color" id="custom-text-input" value="${customColors.text}">
            <span>${t("customColorText")}</span>
          </div>
        </div>
        <div class="checkbox-field" style="margin-top:8px;">
          <input type="checkbox" id="custom-mode-light" ${customColors.mode === "light" ? "checked" : ""}>
          <label for="custom-mode-light">${t("customColorLightMode")}</label>
        </div>
        <p class="hint">${t("settingsCustomColorsHint")}</p>
      </div>
      <div class="field" style="margin-top:14px;">
        <label>${t("settingsBgMedia")}</label>
        <div class="bg-media-row">
          <label class="btn btn-outline btn-sm" style="width:auto;margin:0;">
            ${t("settingsBgMediaChoose")}<input type="file" id="bg-media-input" accept="image/*,video/*" style="display:none;">
          </label>
          <button class="btn btn-ghost btn-sm" id="bg-media-clear-btn" style="width:auto;margin:0;">${t("settingsBgMediaClear")}</button>
        </div>
        <div class="opacity-row" style="margin-top:10px;">
          <span class="hint" style="margin:0;">${t("settingsBgOpacity")}</span>
          <input type="range" id="bg-opacity-slider" min="0" max="100" value="${Math.round((bgCfg?.opacity ?? 0.25) * 100)}">
          <span class="opacity-val" id="bg-opacity-val">${Math.round((bgCfg?.opacity ?? 0.25) * 100)}%</span>
        </div>
      </div>
      <div style="margin-top:18px;">
        <div class="settings-row" style="border:none; padding-bottom:8px;"><span>${t("settingsLanguage")}</span></div>
        <div class="lang-switch">
          <button data-lang="fr" class="${lang === "fr" ? "active" : ""}">Français</button>
          <button data-lang="en" class="${lang === "en" ? "active" : ""}">English</button>
        </div>
      </div>
    </div>
    <div class="settings-section">
      <h4>${t("settingsAccessibility")}</h4>
      <div class="checkbox-field">
        <input type="checkbox" id="a11y-dyslexia-font" ${a11yPrefs.dyslexiaFont ? "checked" : ""}>
        <label for="a11y-dyslexia-font">${t("a11yDyslexiaFont")}</label>
      </div>
      <div class="field" style="margin-top:12px;">
        <label>${t("a11yTextSize")}</label>
        <div class="opacity-row">
          <input type="range" id="a11y-text-scale" min="90" max="130" step="5" value="${Math.round(a11yPrefs.textScale * 100)}">
          <span class="opacity-val" id="a11y-text-scale-val">${Math.round(a11yPrefs.textScale * 100)}%</span>
        </div>
      </div>
      <p class="hint" style="margin-top:8px;">${t("a11yThemesHint")}</p>
    </div>
    <div class="settings-section">
      <h4>${t("settingsRawgKey")}</h4>
      <div class="field">
        <input type="text" id="rawg-key-input" value="${settings.rawg_api_key || ""}" placeholder="rawg.io/apidocs">
        <p class="hint">${t("settingsRawgKeyHint")}</p>
      </div>
    </div>
    <div class="settings-section">
      <h4>${t("settingsGiantbomb")}</h4>
      <div class="field">
        <input type="text" id="giantbomb-key-input" value="${settings.giantbomb_api_key || ""}" placeholder="giantbomb.com/api">
        <p class="hint">${t("settingsGiantbombHint")}</p>
      </div>
    </div>
    <div class="settings-section">
      <h4>${t("settingsData")}</h4>
      <p class="hint">${t("settingsDataHint")}</p>
      <div class="field" style="margin-top:10px;">
        <label>${t("settingsImportSession")}</label>
        <input type="text" id="session-import-path" placeholder="${t("settingsImportPathPlaceholder")}">
        <button class="btn btn-outline btn-sm" id="session-import-btn" style="margin-top:8px;">${t("settingsImportBtn")}</button>
        <p id="session-import-status" class="hint"></p>
      </div>
    </div>
    <div class="settings-section">
      <h4>${t("settingsBackups")}</h4>
      <div class="settings-row"><span>${t("settingsDataLocation")}</span><span class="settings-val">${settings.backup_dir}</span></div>
      <div class="settings-row"><span>${t("settingsNbBackups")}</span><span class="settings-val">${settings.nb_backups}</span></div>
      <button class="btn btn-outline btn-sm" id="backup-now-btn" style="margin-top:12px;">${t("settingsBackupNow")}</button>
      <div class="backup-list" id="backup-list" style="margin-top:10px;"></div>
    </div>`;

  document.getElementById("settings-modal").classList.remove("hidden");

  document.querySelectorAll(".theme-swatch[data-theme]:not(#custom-theme-swatch)").forEach(sw => {
    sw.addEventListener("click", () => {
      applyTheme(sw.dataset.theme);
      document.querySelectorAll(".theme-swatch").forEach(s => s.classList.remove("active"));
      sw.classList.add("active");
    });
  });

  const refreshCustomSwatch = () => {
    const c = getCustomColors();
    const spans = document.querySelectorAll("#custom-theme-swatch .theme-swatch-colors span");
    if (spans[0]) spans[0].style.background = c.bg;
    if (spans[1]) spans[1].style.background = c.accent;
    if (spans[2]) spans[2].style.background = c.text;
  };
  const applyCustomFromInputs = () => {
    const colors = {
      accent: document.getElementById("custom-accent-input").value,
      bg: document.getElementById("custom-bg-input").value,
      card: document.getElementById("custom-card-input").value,
      border: document.getElementById("custom-border-input").value,
      text: document.getElementById("custom-text-input").value,
      mode: document.getElementById("custom-mode-light").checked ? "light" : "dark",
    };
    saveCustomColors(colors);
    applyCustomColors(colors);
    document.querySelectorAll(".theme-swatch").forEach(s => s.classList.remove("active"));
    document.getElementById("custom-theme-swatch").classList.add("active");
    refreshCustomSwatch();
  };
  ["custom-accent-input", "custom-bg-input", "custom-card-input", "custom-border-input", "custom-text-input"].forEach(id => {
    document.getElementById(id).addEventListener("input", applyCustomFromInputs);
  });
  document.getElementById("custom-mode-light").addEventListener("change", applyCustomFromInputs);
  document.getElementById("custom-theme-swatch").addEventListener("click", () => {
    applyTheme("custom");
    document.querySelectorAll(".theme-swatch").forEach(s => s.classList.remove("active"));
    document.getElementById("custom-theme-swatch").classList.add("active");
  });

  document.getElementById("a11y-dyslexia-font").addEventListener("change", (e) => {
    saveA11yPrefs({ dyslexiaFont: e.target.checked });
    applyA11yPrefs();
  });
  document.getElementById("a11y-text-scale").addEventListener("input", (e) => {
    const scale = parseInt(e.target.value, 10) / 100;
    document.getElementById("a11y-text-scale-val").textContent = e.target.value + "%";
    saveA11yPrefs({ textScale: scale });
    applyA11yPrefs();
  });

  document.getElementById("bg-media-input").addEventListener("change", (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => {
      const cfg = { dataUrl: reader.result, mime: f.type, opacity: (getBgMediaConfig()?.opacity ?? 0.25) };
      localStorage.setItem("backlog_bg_media", JSON.stringify(cfg));
      applyBgMedia();
    };
    reader.readAsDataURL(f);
  });
  document.getElementById("bg-media-clear-btn").addEventListener("click", () => {
    localStorage.removeItem("backlog_bg_media");
    applyBgMedia();
  });
  document.getElementById("bg-opacity-slider").addEventListener("input", (e) => {
    const val = parseInt(e.target.value, 10) / 100;
    document.getElementById("bg-opacity-val").textContent = `${e.target.value}%`;
    const cfg = getBgMediaConfig() || {};
    cfg.opacity = val;
    localStorage.setItem("backlog_bg_media", JSON.stringify(cfg));
    applyBgMedia();
  });

  document.querySelectorAll(".lang-switch button").forEach(btn => {
    btn.addEventListener("click", () => {
      localStorage.setItem("backlog_lang", btn.dataset.lang);
      location.reload();
    });
  });

  document.getElementById("rawg-key-input").addEventListener("change", async (e) => {
    await api.post("/api/settings", { rawg_api_key: e.target.value.trim() });
  });
  document.getElementById("giantbomb-key-input").addEventListener("change", async (e) => {
    await api.post("/api/settings", { giantbomb_api_key: e.target.value.trim() });
  });

  document.getElementById("backup-now-btn").addEventListener("click", async () => {
    await api.post("/api/backups");
    loadBackupInfo();
  });

  document.getElementById("session-import-btn").addEventListener("click", async () => {
    const pathInput = document.getElementById("session-import-path");
    const statusEl = document.getElementById("session-import-status");
    const path = pathInput.value.trim();
    if (!path) return;
    const ok = await showConfirm({
      message: `${t("sessionImportConfirmTitle")} ${t("sessionImportConfirmMsg")}`,
      okLabel: t("settingsImportBtn"), cancelLabel: t("confirmCancel"), danger: true,
    });
    if (!ok) return;
    statusEl.textContent = "…";
    const res = await api.post("/api/session/import", { path });
    if (res.error) {
      statusEl.textContent = t("sessionImportError").replace("{error}", res.error);
      return;
    }
    statusEl.textContent = t("sessionImportSuccess")
      .replace("{completed}", res.summary.completed_imported)
      .replace("{backlog}", res.summary.backlog_imported)
      .replace("{matched}", res.summary.reviews_matched);
    setTimeout(() => location.reload(), 1400);
  });

  loadBackupInfo();
}

async function loadBackupInfo() {
  const backups = await api.get("/api/backups");
  const listEl = document.getElementById("backup-list");
  listEl.innerHTML = backups.slice(0, 10).map(b => `
    <div class="backup-row">
      <span class="backup-name">${b.name}</span>
      <button data-name="${b.name}">${t("settingsRestore")}</button>
    </div>`).join("");
  listEl.querySelectorAll("button[data-name]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const ok = await showConfirm({
        message: t("settingsRestoreConfirm"), okLabel: t("settingsRestore"),
        cancelLabel: t("confirmCancel"), danger: true,
      });
      if (!ok) return;
      await api.post(`/api/backups/${encodeURIComponent(btn.dataset.name)}/restore`);
      location.reload();
    });
  });
}

// ============================================================ i18n
function applyTranslations() {
  document.title = t("appName");
  document.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
  document.querySelectorAll("[data-i18n-title]").forEach(el => {
    el.title = t(el.dataset.i18nTitle);
  });
}

// ============================================================ Boot
document.addEventListener("DOMContentLoaded", () => {
  detectAndSetInitialLanguage();
  applyTheme(currentTheme());
  applyA11yPrefs();
  applyBgMedia();
  initCoverEditor();
  checkSetup();
});

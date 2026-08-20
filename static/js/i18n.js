/* i18n loader. The actual strings live in static/js/translations/<locale>.js
 * (a dedicated folder so new locales can be added without touching this
 * file) — this just merges them and exposes the t() helper used everywhere
 * else in the app. */
const I18N = window.I18N_TRANSLATIONS || {};
const I18N_LOCALES = window.I18N_LOCALES || { fr: "Français", en: "English" };
const I18N_FALLBACK = "en";

// Before the user has picked a language explicitly (or on first run), fall
// back to the browser's own language if we support it, rather than always
// defaulting to French — a French default meant every non-French visitor
// saw a flash of untranslated-feeling UI (and error strings that hadn't
// been localized at all) until they found the language switcher.
function _detectDefaultLocale() {
  const supported = Object.keys(I18N_LOCALES);
  const navLangs = (navigator.languages && navigator.languages.length)
    ? navigator.languages
    : [navigator.language || navigator.userLanguage || I18N_FALLBACK];
  for (const lang of navLangs) {
    const short = (lang || "").slice(0, 2).toLowerCase();
    if (supported.includes(short)) return short;
  }
  return I18N_FALLBACK;
}

function t(key) {
  const lang = localStorage.getItem("backlog_lang") || _detectDefaultLocale();
  const table = I18N[lang] || I18N[I18N_FALLBACK] || {};
  if (key in table) return table[key];
  const fallback = I18N[I18N_FALLBACK] || {};
  return fallback[key] || key;
}

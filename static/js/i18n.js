/* i18n loader. The actual strings live in static/js/translations/<locale>.js
 * (a dedicated folder so new locales can be added without touching this
 * file) — this just merges them and exposes the t() helper used everywhere
 * else in the app. */
const I18N = window.I18N_TRANSLATIONS || {};
const I18N_LOCALES = window.I18N_LOCALES || { fr: "Français", en: "English" };
const I18N_FALLBACK = "en";

function t(key) {
  const lang = localStorage.getItem("backlog_lang") || "fr";
  const table = I18N[lang] || I18N[I18N_FALLBACK] || {};
  if (key in table) return table[key];
  const fallback = I18N[I18N_FALLBACK] || {};
  return fallback[key] || key;
}

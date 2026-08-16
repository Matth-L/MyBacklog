/* List of installed locales: code -> display name.
 * To add a new locale:
 *   1. Copy translations/fr.js to translations/<code>.js, translate the values.
 *   2. Add an entry here.
 *   3. Add <script src="/static/js/translations/<code>.js"></script> in index.html,
 *      right before translations/index.js.
 * That's it — the language switch in Settings and the fallback logic in i18n.js
 * pick it up automatically. */
window.I18N_LOCALES = {
  fr: "Français",
  en: "English",
};

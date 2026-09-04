(function () {
  'use strict';
  const STORAGE_KEY = 'alphafoundry.research.appearance.v1';
  const normalize = value => ['light', 'dark', 'system'].includes(value) ? value : 'system';

  function createThemeController({ root, storage, systemDark = false, log = () => {} }) {
    let preference = 'system';
    let osDark = Boolean(systemDark);
    try { preference = normalize(storage?.getItem(STORAGE_KEY)); }
    catch { log('theme_storage_read_failed'); }
    function apply() {
      const resolved = preference === 'system' ? (osDark ? 'dark' : 'light') : preference;
      root.dataset.theme = resolved;
      root.dataset.themePreference = preference;
      root.style.colorScheme = resolved;
      return resolved;
    }
    apply();
    return {
      get preference() { return preference; },
      get resolved() { return root.dataset.theme; },
      setPreference(value, { persist = true } = {}) {
        preference = normalize(value);
        if (persist) {
          try { storage?.setItem(STORAGE_KEY, preference); }
          catch { log('theme_storage_write_failed'); }
        }
        const resolved = apply();
        log('theme_changed');
        return resolved;
      },
      setSystemDark(value) { osDark = Boolean(value); if (preference === 'system') apply(); },
    };
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { createThemeController, STORAGE_KEY };
    return;
  }
  // Fixed event names only: no storage contents, document text or exception bodies.
  const log = event => console.info('[research-web]', event);
  let storage, system;
  try { storage = window.localStorage; } catch { log('theme_storage_unavailable'); }
  try { system = window.matchMedia('(prefers-color-scheme: dark)'); }
  catch { log('theme_system_preference_unavailable'); }
  const controller = createThemeController({ root: document.documentElement, storage, systemDark: system?.matches, log });
  const syncControls = () => {
    document.querySelectorAll('[data-theme-option]').forEach(input => {
      input.checked = input.value === controller.preference;
    });
  };
  window.AlphaFoundryTheme = { controller, syncControls };
  document.addEventListener('DOMContentLoaded', syncControls, { once: true });
  document.addEventListener('change', event => {
    if (!event.target.matches('[data-theme-option]')) return;
    controller.setPreference(event.target.value); syncControls();
  });
  const onSystemChange = event => { controller.setSystemDark(event.matches); syncControls(); };
  if (system?.addEventListener) system.addEventListener('change', onSystemChange);
  else if (system?.addListener) system.addListener(onSystemChange);
  window.addEventListener('storage', event => {
    if (event.storageArea !== storage || ![STORAGE_KEY, null].includes(event.key)) return;
    controller.setPreference(event.newValue, { persist: false }); syncControls();
  });
})();

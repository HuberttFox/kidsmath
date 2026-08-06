(function () {
  var UI = {};
  var uiEl = document.getElementById('ui-json');
  if (uiEl) {
    try { UI = JSON.parse(uiEl.textContent); } catch (e) { UI = {}; }
  }
  var LANG_KEYS = ['zh', 'en'];
  var THEMES = ['auto', 'light', 'dark'];

  function cookie(name) {
    var m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
    return m ? decodeURIComponent(m[1]) : '';
  }

  function setCookie(name, value) {
    document.cookie = name + '=' + encodeURIComponent(value) + '; path=/; max-age=31536000';
  }

  function currentLang() {
    var c = cookie('mathgen_lang');
    if (LANG_KEYS.indexOf(c) !== -1) return c;
    return document.documentElement.lang === 'en' ? 'en' : 'zh';
  }

  function tr(key, lang) {
    var table = UI[lang] || {};
    return table[key] || (UI.zh && UI.zh[key]) || key;
  }

  function applyLang(lang) {
    document.documentElement.lang = lang;
    document.querySelectorAll('[data-i18n]').forEach(function (el) {
      el.textContent = tr(el.getAttribute('data-i18n'), lang);
    });
    var label = document.getElementById('langLabel');
    if (label) label.textContent = lang === 'zh' ? 'EN' : '中';
    var hint = document.getElementById('preset-hint');
    if (hint) hint.dispatchEvent(new Event('langchange'));
    document.dispatchEvent(new CustomEvent('langchange', { detail: { lang: lang } }));
  }

  function currentTheme() {
    var t = cookie('mathgen_theme');
    return THEMES.indexOf(t) !== -1 ? t : 'auto';
  }

  function applyTheme(theme) {
    document.documentElement.removeAttribute('data-theme');
    if (theme !== 'auto') document.documentElement.setAttribute('data-theme', theme);
    setCookie('mathgen_theme', theme);
    var label = document.getElementById('themeLabel');
    if (label) label.textContent = theme === 'auto' ? '🌓' : theme === 'light' ? '☀️' : '🌙';
  }

  var langBtn = document.getElementById('langToggle');
  if (langBtn) {
    langBtn.addEventListener('click', function () {
      var next = currentLang() === 'zh' ? 'en' : 'zh';
      setCookie('mathgen_lang', next);
      applyLang(next);
    });
  }
  var themeBtn = document.getElementById('themeToggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', function () {
      var idx = THEMES.indexOf(currentTheme());
      applyTheme(THEMES[(idx + 1) % THEMES.length]);
    });
  }
  applyLang(currentLang());
  applyTheme(currentTheme());
})();

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

  function fmt(tmpl, params) {
    if (!params) return tmpl;
    Object.keys(params).forEach(function (k) {
      tmpl = tmpl.split('{' + k + '}').join(String(params[k]));
    });
    return tmpl;
  }

  function applyLang(lang) {
    document.documentElement.lang = lang;
    document.querySelectorAll('[data-i18n]').forEach(function (el) {
      var text = tr(el.getAttribute('data-i18n'), lang);
      var params = el.getAttribute('data-i18n-params');
      if (params) {
        try { text = fmt(text, JSON.parse(params)); } catch (e) { /* keep raw */ }
      }
      el.textContent = text;
    });
    document.querySelectorAll('[data-i18n-tip]').forEach(function (el) {
      el.setAttribute('data-tip', tr(el.getAttribute('data-i18n-tip'), lang));
    });
    document.querySelectorAll('[data-summary]').forEach(function (el) {
      var d = {};
      try { d = JSON.parse(el.getAttribute('data-summary')); } catch (e) { return; }
      var g = d.grade ? tr('grade.x', lang).split('{g}').join(String(d.grade)) : tr('grade.custom', lang);
      var topic = tr('topic.' + d.topic, lang) || d.topic;
      el.textContent = fmt(tr('preview.summary', lang), {
        grade: g, topic: topic, count: String(d.count)
      });
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
    document.dispatchEvent(new CustomEvent('themechange', { detail: { theme: theme } }));
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
  // 响应父壳转发（工作台内 iframe 不重载切换主题/语言，避免清空表单）
  function appliedTheme() {
    return document.documentElement.getAttribute('data-theme') || 'auto';
  }
  document.addEventListener('themechange', function (e) {
    var t = e && e.detail && e.detail.theme;
    if (!t || t === appliedTheme()) return;
    applyTheme(t);
  });
  document.addEventListener('langchange', function (e) {
    var l = e && e.detail && e.detail.lang;
    if (!l || l === document.documentElement.lang) return;
    applyLang(l);
  });
  applyLang(currentLang());
  applyTheme(currentTheme());
})();

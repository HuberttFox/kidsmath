const CACHE = 'kidsmath-v6';
const ASSETS = [
  '/', '/static/style.css', '/static/lang.js', '/static/timer.js', '/static/audio.js', '/static/sound.js', '/static/math-icon.svg',
  '/static/icons/settings.svg', '/static/icons/calculator.svg',
  '/static/icons/layout.svg', '/static/icons/batch.svg',
  '/static/fonts/yozai-400.woff2', '/static/fonts/yozai-700.woff2'
];
self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
// 白名单：仅缓存首页、产品页与静态资源；/user/*、/login、/api/* 等一律走网络
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  const allow = url.pathname === '/' || url.pathname === '/product' ||
                 url.pathname.startsWith('/static/');
  if (e.request.method !== 'GET' || url.origin !== location.origin || !allow) return;
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
      if (res.ok) {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
      }
      return res;
    }))
  );
});

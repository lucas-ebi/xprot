// Service worker: makes the app installable/offline. Not to be confused with worker.js, the
// dedicated Web Worker that runs Pyodide -- this file only ever runs in the service-worker
// global scope and never touches Python at all.
//
// __APP_VERSION__ is substituted by the GitHub Actions Pages workflow at deploy time (see
// .github/workflows/pages.yml); a local checkout keeps the literal placeholder, so the shell
// cache's key never rolls over locally. Since main.js (below) never registers this worker on a
// local-dev host in the first place, the only way it can be running there at all is a
// registration left over from before that guard existed -- self-destruct in that case instead of
// silently freezing index.html/main.js/renderers.js/styles.css/worker.js at whatever they were
// when it first installed. Keep in sync with main.js's own IS_LOCAL_DEV list.
const IS_LOCAL_DEV = [
  'localhost', '127.0.0.1', '::1', '::',
].includes(self.location.hostname);

const APP_VERSION = '__APP_VERSION__';
const SHELL_CACHE = `xprot-shell-${APP_VERSION}`;
const RUNTIME_CACHE = 'xprot-runtime-v1';

const SHELL_FILES = [
  './',
  './index.html',
  './main.js',
  './renderers.js',
  './styles.css',
  './worker.js',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-512-maskable.png',
];

// Everything worker.js pulls in at runtime to run a design: the Pyodide runtime itself, the
// Python packages micropip installs, and xprot's own source (fetched from raw.githubusercontent.com
// in production). Cached on first use so a design can run fully offline afterward.
const RUNTIME_HOSTS = [
  'cdn.jsdelivr.net',
  'raw.githubusercontent.com',
  'pypi.org',
  'files.pythonhosted.org',
];

self.addEventListener('install', event => {
  if (IS_LOCAL_DEV) {
    event.waitUntil(self.skipWaiting());
    return;
  }
  event.waitUntil(caches.open(SHELL_CACHE).then(cache => cache.addAll(SHELL_FILES)));
});

self.addEventListener('activate', event => {
  if (IS_LOCAL_DEV) {
    event.waitUntil(
      caches.keys()
        .then(keys => Promise.all(keys.map(key => caches.delete(key))))
        .then(() => self.registration.unregister())
        .then(() => self.clients.matchAll())
        .then(clients => clients.forEach(client => client.navigate(client.url)))
    );
    return;
  }
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys
          .filter(key => key.startsWith('xprot-shell-') && key !== SHELL_CACHE)
          .map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

// Never grabs control on its own -- main.js prompts the user to reload instead, so a new
// deploy can't swap code out from under a design that's mid-run.
self.addEventListener('message', event => {
  if (event.data?.type === 'SKIP_WAITING') self.skipWaiting();
});

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) cache.put(request, response.clone());
  return response;
}

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);

  if (RUNTIME_HOSTS.includes(url.hostname)) {
    event.respondWith(cacheFirst(event.request, RUNTIME_CACHE));
    return;
  }

  if (url.origin === self.location.origin) {
    event.respondWith(
      caches.match(event.request).then(cached => cached || fetch(event.request))
    );
  }
});

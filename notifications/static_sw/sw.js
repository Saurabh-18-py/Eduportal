// EduPortal service worker — push notifications + light offline support.

var CACHE_NAME = 'eduportal-static-v1';
var PRECACHE_URLS = [
    '/static/css/style.css',
    '/static/js/push.js',
    '/static/images/logo-icon.png',
    '/static/images/icon-192.png',
    '/offline/'
];

self.addEventListener('install', function (event) {
    event.waitUntil(
        caches.open(CACHE_NAME).then(function (cache) {
            return cache.addAll(PRECACHE_URLS).catch(function () { /* fine if one 404s */ });
        }).then(function () { return self.skipWaiting(); })
    );
});

self.addEventListener('activate', function (event) {
    event.waitUntil(
        caches.keys().then(function (keys) {
            return Promise.all(keys.filter(function (k) { return k !== CACHE_NAME; }).map(function (k) { return caches.delete(k); }));
        }).then(function () { return self.clients.claim(); })
    );
});

self.addEventListener('fetch', function (event) {
    var req = event.request;
    if (req.method !== 'GET') return; // never intercept POSTs (subscribe, ask-doubt, forms, etc.)
    var url = new URL(req.url);
    if (url.origin !== self.location.origin) return;

    // Static assets: cache-first, so they load instantly and still work offline.
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(req).then(function (cached) {
                return cached || fetch(req).then(function (res) {
                    if (res.ok) {
                        var copy = res.clone();
                        caches.open(CACHE_NAME).then(function (c) { c.put(req, copy); });
                    }
                    return res;
                });
            })
        );
        return;
    }

    // Page navigations: network-first (always show live content when online),
    // fall back to a friendly offline page only when the network truly fails.
    if (req.mode === 'navigate') {
        event.respondWith(
            fetch(req).catch(function () {
                return caches.match('/offline/').then(function (cached) {
                    return cached || Response.error();
                });
            })
        );
    }
});

self.addEventListener('push', function (event) {
    var data = { title: 'EduPortal', body: 'You have a new notification.', url: '/' };
    if (event.data) {
        try { data = event.data.json(); } catch (err) { data.body = event.data.text(); }
    }

    var options = {
        body: data.body,
        icon: '/static/images/logo-icon.png',
        badge: '/static/images/logo-icon.png',
        data: { url: data.url || '/' }
    };

    event.waitUntil(self.registration.showNotification(data.title || 'EduPortal', options));
});

self.addEventListener('notificationclick', function (event) {
    event.notification.close();
    var url = (event.notification.data && event.notification.data.url) || '/';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (windowClients) {
            for (var i = 0; i < windowClients.length; i++) {
                var client = windowClients[i];
                if (client.url === url && 'focus' in client) return client.focus();
            }
            if (clients.openWindow) return clients.openWindow(url);
        })
    );
});

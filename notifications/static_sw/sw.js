// EduPortal service worker — handles incoming push notifications only.
// (No offline caching here on purpose, so it never interferes with normal
// page loads or the animations already on the site.)

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

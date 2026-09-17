// EduPortal — push notification bell button
(function () {
    var btn = document.getElementById('push-bell');
    if (!btn) return;

    var vapidKey = btn.dataset.vapidKey;
    if (!vapidKey || !('serviceWorker' in navigator) || !('PushManager' in window)) {
        btn.style.display = 'none';
        return;
    }

    function getCookie(name) {
        var match = document.cookie.match('(?:^|; )' + name + '=([^;]*)');
        return match ? decodeURIComponent(match[1]) : '';
    }

    function urlBase64ToUint8Array(base64String) {
        var padding = '='.repeat((4 - (base64String.length % 4)) % 4);
        var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
        var rawData = window.atob(base64);
        var outputArray = new Uint8Array(rawData.length);
        for (var i = 0; i < rawData.length; ++i) outputArray[i] = rawData.charCodeAt(i);
        return outputArray;
    }

    function setState(subscribed) {
        btn.classList.toggle('is-subscribed', subscribed);
        btn.textContent = subscribed ? '🔔' : '🔕';
        btn.title = subscribed ? 'Notifications on — tap to turn off' : 'Turn on notifications';
    }

    function postJSON(url, body) {
        return fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
            body: JSON.stringify(body)
        });
    }

    var swReady = navigator.serviceWorker.register('/sw.js').then(function (reg) {
        return reg.pushManager.getSubscription().then(function (sub) {
            setState(!!sub);
            return reg;
        });
    }).catch(function () { btn.style.display = 'none'; });

    btn.addEventListener('click', function () {
        swReady.then(function (reg) {
            if (!reg) return;
            reg.pushManager.getSubscription().then(function (existing) {
                if (existing) {
                    existing.unsubscribe().then(function () {
                        postJSON('/notifications/unsubscribe/', { endpoint: existing.endpoint });
                        setState(false);
                    });
                    return;
                }
                if (Notification.permission === 'denied') {
                    alert('Notifications are blocked for this site in your browser settings.');
                    return;
                }
                reg.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: urlBase64ToUint8Array(vapidKey)
                }).then(function (sub) {
                    var raw = sub.toJSON();
                    postJSON('/notifications/subscribe/', raw).then(function (res) {
                        if (res.ok) setState(true);
                    });
                }).catch(function () { /* permission denied or blocked */ });
            });
        });
    });
})();

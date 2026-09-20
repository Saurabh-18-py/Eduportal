// EduPortal — "Install app" banner
(function () {
    var DISMISS_KEY = 'eduportal_install_dismissed_at';
    var DISMISS_DAYS = 14;

    // Already installed / running as an app? Nothing to prompt.
    var isStandalone = window.matchMedia('(display-mode: standalone)').matches
        || window.navigator.standalone === true;
    if (isStandalone) return;

    // Respect a recent dismissal.
    try {
        var dismissedAt = localStorage.getItem(DISMISS_KEY);
        if (dismissedAt && (Date.now() - parseInt(dismissedAt, 10)) < DISMISS_DAYS * 86400000) return;
    } catch (err) { /* localStorage unavailable, just proceed */ }

    var isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;
    var deferredPrompt = null;

    function buildBanner(bodyText, showInstallButton) {
        var banner = document.createElement('div');
        banner.className = 'install-banner';
        banner.innerHTML =
            '<img src="/static/images/icon-192.png" alt="" class="install-banner-icon">' +
            '<div class="install-banner-text">' +
                '<strong>Install EduPortal</strong>' +
                '<span>' + bodyText + '</span>' +
            '</div>' +
            (showInstallButton ? '<button type="button" class="install-banner-btn">Install</button>' : '') +
            '<button type="button" class="install-banner-close" aria-label="Dismiss">&times;</button>';
        document.body.appendChild(banner);
        requestAnimationFrame(function () { banner.classList.add('is-visible'); });

        function dismiss() {
            banner.classList.remove('is-visible');
            setTimeout(function () { banner.remove(); }, 300);
            try { localStorage.setItem(DISMISS_KEY, String(Date.now())); } catch (err) {}
        }
        banner.querySelector('.install-banner-close').addEventListener('click', dismiss);
        return { banner: banner, dismiss: dismiss };
    }

    if (isIOS) {
        // Safari gives no programmatic install trigger — show instructions instead.
        buildBanner('Tap the Share button, then "Add to Home Screen".', false);
        return;
    }

    // Android/Chrome/Brave: wait for the browser to say installation is possible.
    window.addEventListener('beforeinstallprompt', function (e) {
        e.preventDefault();
        deferredPrompt = e;
        var ui = buildBanner('Add it to your home screen for quick, full-screen access.', true);
        ui.banner.querySelector('.install-banner-btn').addEventListener('click', function () {
            ui.banner.classList.remove('is-visible');
            deferredPrompt.prompt();
            deferredPrompt.userChoice.finally(function () {
                deferredPrompt = null;
                setTimeout(function () { ui.banner.remove(); }, 300);
            });
        });
    });

    window.addEventListener('appinstalled', function () {
        try { localStorage.setItem(DISMISS_KEY, String(Date.now())); } catch (err) {}
    });
})();

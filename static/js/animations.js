// EduPortal — site-wide entrance & interaction animations
(function () {
    var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // ---- Header drop-in ----
    var header = document.querySelector('.ticket-header');
    if (header) header.classList.add(reduced ? '' : 'anim-header-in');

    // ---- Hero: reveal (whole block handles its own cinematic zoom-in via CSS) ----
    var hero = document.querySelector('.hero');
    if (hero && !reduced) hero.classList.add('anim-hero-in');

    // ---- Scroll reveal for cards / list items / banners / question blocks ----
    var revealTargets = document.querySelectorAll(
        '.hall-ticket, .list-item, .pyq-banner, .question-block, .stats-grid > *'
    );
    if (revealTargets.length) {
        if (reduced) {
            revealTargets.forEach(function (el) { el.classList.add('reveal-in'); });
        } else {
            revealTargets.forEach(function (el, i) {
                el.classList.add('reveal');
                el.style.setProperty('--stagger', (i % 10) * 55 + 'ms');
            });
            if ('IntersectionObserver' in window) {
                var io = new IntersectionObserver(function (entries) {
                    entries.forEach(function (entry) {
                        if (entry.isIntersecting) {
                            entry.target.classList.add('reveal-in');
                            io.unobserve(entry.target);
                        }
                    });
                }, { threshold: 0.12 });
                revealTargets.forEach(function (el) { io.observe(el); });
            } else {
                revealTargets.forEach(function (el) { el.classList.add('reveal-in'); });
            }
        }
    }

    // ---- 3D tilt on hall-ticket cards, following the cursor ----
    if (!reduced) {
        document.querySelectorAll('.hall-ticket').forEach(function (card) {
            card.addEventListener('mousemove', function (e) {
                var r = card.getBoundingClientRect();
                var x = (e.clientX - r.left) / r.width - 0.5;
                var y = (e.clientY - r.top) / r.height - 0.5;
                card.style.transform =
                    'perspective(700px) rotateY(' + (x * 14).toFixed(2) + 'deg) ' +
                    'rotateX(' + (-y * 14).toFixed(2) + 'deg) translateY(-6px)';
            });
            card.addEventListener('mouseleave', function () {
                card.style.transform = '';
            });
        });
    }

    // ---- Button ripple on click ----
    document.addEventListener('click', function (e) {
        if (reduced) return;
        var btn = e.target.closest('button, .nav-cta, .btn-ghost');
        if (!btn) return;
        var circle = document.createElement('span');
        circle.className = 'ripple';
        var r = btn.getBoundingClientRect();
        var size = Math.max(r.width, r.height) * 2;
        circle.style.width = circle.style.height = size + 'px';
        circle.style.left = (e.clientX - r.left - size / 2) + 'px';
        circle.style.top = (e.clientY - r.top - size / 2) + 'px';
        btn.appendChild(circle);
        circle.addEventListener('animationend', function () { circle.remove(); });
    });

    // ---- Alerts slide down, staggered ----
    document.querySelectorAll('.alert').forEach(function (el, i) {
        el.style.setProperty('--stagger', i * 90 + 'ms');
        if (!reduced) el.classList.add('anim-alert-in');
    });

    // ---- Neon glow on key elements ----
    document.querySelectorAll('.hall-ticket, .nav-cta').forEach(function (el) {
        el.classList.add('neon-glow');
    });

    if (reduced) return;

    // ---- Cinematic curtain intro (only on first visit this session) ----
    var curtainShown = false;
    try { curtainShown = sessionStorage.getItem('eduportal_curtain_shown') === '1'; } catch (err) {}

    if (!curtainShown) {
        var curtain = document.createElement('div');
        curtain.className = 'page-curtain';
        curtain.innerHTML =
            '<div class="page-curtain-half left"><span class="page-curtain-logo">EDUPORTAL</span></div>' +
            '<div class="page-curtain-half right"><span class="page-curtain-logo"></span></div>';
        document.body.appendChild(curtain);
        requestAnimationFrame(function () {
            curtain.classList.add('opening');
        });
        setTimeout(function () { curtain.remove(); }, 1500);
        try { sessionStorage.setItem('eduportal_curtain_shown', '1'); } catch (err) {}
    }

    // ---- Cursor / touch sparkle trail ----
    var lastSparkle = 0;
    function dropSparkle(x, y) {
        var now = Date.now();
        if (now - lastSparkle < 45) return;
        lastSparkle = now;
        var s = document.createElement('span');
        s.className = 'sparkle';
        s.style.left = (x - 3) + 'px';
        s.style.top = (y - 3) + 'px';
        document.body.appendChild(s);
        s.addEventListener('animationend', function () { s.remove(); });
    }
    window.addEventListener('mousemove', function (e) { dropSparkle(e.clientX, e.clientY); });
    window.addEventListener('touchmove', function (e) {
        if (e.touches[0]) dropSparkle(e.touches[0].clientX, e.touches[0].clientY);
    }, { passive: true });
})();

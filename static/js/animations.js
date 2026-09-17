// EduPortal — site-wide entrance & interaction animations
(function () {
    var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // ---- Header drop-in ----
    var header = document.querySelector('.ticket-header');
    if (header) header.classList.add(reduced ? '' : 'anim-header-in');

    // ---- Hero: split h1 into lines for stagger, then reveal ----
    var hero = document.querySelector('.hero');
    if (hero) {
        var h1 = hero.querySelector('h1');
        if (h1 && !h1.dataset.split) {
            var parts = h1.innerHTML.split(/<br\s*\/?>/i);
            h1.innerHTML = parts
                .map(function (line) { return '<span class="hero-line">' + line + '</span>'; })
                .join('<br>');
            h1.dataset.split = 'true';
        }
        if (!reduced) hero.classList.add('anim-hero-in');
    }

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

    // ---- Cinematic curtain intro ----
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

    // ---- Particle background canvas ----
    var canvas = document.createElement('canvas');
    canvas.id = 'particle-canvas';
    document.body.prepend(canvas);
    var ctx = canvas.getContext('2d');
    var particles = [];
    var colors = ['#c1443c', '#c99a2e', '#1f7a6c'];

    function resizeCanvas() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    var particleCount = Math.min(55, Math.floor(window.innerWidth / 16));
    for (var p = 0; p < particleCount; p++) {
        particles.push({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            r: 3 + Math.random() * 4.5,
            vx: (Math.random() - 0.5) * 0.5,
            vy: -0.3 - Math.random() * 0.6,
            color: colors[p % colors.length],
            alpha: 0.55 + Math.random() * 0.4
        });
    }

    function tickParticles() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        particles.forEach(function (pt) {
            pt.x += pt.vx; pt.y += pt.vy;
            if (pt.y < -10) { pt.y = canvas.height + 10; pt.x = Math.random() * canvas.width; }
            if (pt.x < -10) pt.x = canvas.width + 10;
            if (pt.x > canvas.width + 10) pt.x = -10;
            ctx.save();
            ctx.globalAlpha = pt.alpha;
            ctx.shadowBlur = 12;
            ctx.shadowColor = pt.color;
            ctx.beginPath();
            ctx.arc(pt.x, pt.y, pt.r, 0, Math.PI * 2);
            ctx.fillStyle = pt.color;
            ctx.fill();
            ctx.restore();
        });
        requestAnimationFrame(tickParticles);
    }
    tickParticles();

    // ---- Confetti burst helper ----
    function burstConfetti(x, y) {
        for (var i = 0; i < 22; i++) {
            var piece = document.createElement('span');
            piece.className = 'confetti-piece';
            piece.style.left = x + 'px';
            piece.style.top = y + 'px';
            piece.style.background = colors[i % colors.length];
            var angle = Math.random() * Math.PI * 2;
            var dist = 60 + Math.random() * 90;
            var ex = Math.cos(angle) * dist;
            var ey = Math.sin(angle) * dist - 40;
            piece.style.setProperty('--confetti-end',
                'translate(' + ex + 'px,' + ey + 'px) rotate(' + (Math.random() * 720 - 360) + 'deg)');
            document.body.appendChild(piece);
            piece.addEventListener('animationend', function () { this.remove(); });
        }
    }

    document.addEventListener('click', function (e) {
        var target = e.target.closest('.hall-ticket, .nav-cta, button');
        if (!target) return;
        burstConfetti(e.clientX, e.clientY);
    });

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

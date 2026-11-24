/* theme.js — theme, navigation and live UI behaviour */
(function () {
    var root = document.documentElement;
    var KEY = 'bhoomiai-theme';

    function readSaved() {
        try { return localStorage.getItem(KEY); } catch (e) { return null; }
    }

    function apply(theme, persist) {
        var value = theme === 'dark' ? 'dark' : 'light';
        root.setAttribute('data-theme', value);
        if (persist) {
            try { localStorage.setItem(KEY, value); } catch (e) {}
        }
        try {
            document.dispatchEvent(new CustomEvent('bhoomiai:themechange', { detail: { theme: value } }));
        } catch (e) {}
    }

    var saved = readSaved();
    if (saved) apply(saved, false);

    window.toggleTheme = function () {
        apply(root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark', true);
    };

    document.addEventListener('click', function (event) {
        var toggle = event.target.closest('[data-theme-toggle]');
        if (toggle) {
            event.preventDefault();
            window.toggleTheme();
            return;
        }

        var burger = event.target.closest('[data-menu-toggle]');
        if (burger) {
            event.preventDefault();
            openMenu(!document.body.classList.contains('menu-open'));
            return;
        }

        if (event.target.closest('[data-menu-close]') || event.target.classList.contains('mobile-backdrop')) {
            openMenu(false);
        }

        var avatar = document.querySelector('.avatar-menu');
        if (avatar && avatar.open && !event.target.closest('.avatar-menu')) {
            avatar.open = false;
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            openMenu(false);
            var avatar = document.querySelector('.avatar-menu');
            if (avatar) avatar.open = false;
        }
    });

    function openMenu(open) {
        var panel = document.getElementById('mobile-nav');
        var backdrop = document.querySelector('.mobile-backdrop');
        if (!panel) return;
        panel.classList.toggle('is-open', open);
        if (backdrop) backdrop.classList.toggle('is-open', open);
        document.body.classList.toggle('no-scroll', open);
        var burger = document.querySelector('[data-menu-toggle]');
        if (burger) burger.setAttribute('aria-expanded', String(open));
    }

    // Live notification counter (no page reload).
    function refreshLiveCounters() {
        var badge = document.getElementById('notification-badge');
        var url = document.body.getAttribute('data-live-url');
        if (!url || !badge) return;
        if (window.location.search) {
            url += (url.indexOf('?') === -1 ? '?' : '&') + window.location.search.slice(1);
        }
        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (response) { return response.ok ? response.json() : null; })
            .then(function (data) {
                if (!data) return;
                if (typeof data.unread === 'number') {
                    badge.textContent = data.unread > 99 ? '99+' : String(data.unread);
                    badge.classList.toggle('is-empty', data.unread === 0);
                }
                var map = {
                    'live-total': data.total,
                    'live-validated': data.validated,
                    'live-pending': data.pending,
                    'live-duplicates': data.duplicates
                };
                Object.keys(map).forEach(function (id) {
                    var el = document.getElementById(id);
                    if (el && typeof map[id] === 'number') el.textContent = map[id];
                });
            })
            .catch(function () {});
    }

    if (document.body && document.body.hasAttribute('data-live-url')) {
        refreshLiveCounters();
        setInterval(refreshLiveCounters, 20000);
    }

    // Auto-dismiss success alerts after a while.
    document.querySelectorAll('.alert-success').forEach(function (alert) {
        setTimeout(function () {
            alert.style.transition = 'opacity .4s ease, transform .4s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-6px)';
            setTimeout(function () { alert.remove(); }, 420);
        }, 6000);
    });
})();

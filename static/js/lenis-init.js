/* lenis-init.js — smooth scrolling via Lenis, with reduced-motion support. */
(function () {
    'use strict';

    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        return; // respect user preference; native scrolling stays
    }

    if (typeof Lenis === 'undefined') {
        return; // Lenis failed to load; fall back to native smooth scroll
    }

    var lenis = new Lenis({
        duration: 1.1,
        easing: function (t) { return Math.min(1, 1.001 - Math.pow(2, -10 * t)); },
        orientation: 'vertical',
        gestureOrientation: 'vertical',
        smoothWheel: true,
        wheelMultiplier: 1,
        touchMultiplier: 2,
        infinite: false,
    });

    function raf(time) {
        lenis.raf(time);
        requestAnimationFrame(raf);
    }
    requestAnimationFrame(raf);

    // Expose for other scripts that may want to stop/start scrolling.
    window.lenis = lenis;

    // Anchor link smooth scrolling.
    document.addEventListener('click', function (event) {
        var link = event.target && event.target.closest ? event.target.closest('a[href^="#"]') : null;
        if (!link) return;
        var hash = link.getAttribute('href');
        if (!hash || hash === '#') return;
        var target = document.querySelector(hash);
        if (!target) return;
        event.preventDefault();
        lenis.scrollTo(target, { offset: -72 });
        if (history && history.pushState) {
            history.pushState(null, '', hash);
        }
    });

    // Keep Lenis in sync when the theme changes (layout shifts).
    document.addEventListener('bhoomiai:themechange', function () {
        lenis.resize();
    });

    // Resize on window resize.
    window.addEventListener('resize', function () {
        lenis.resize();
    });
})();
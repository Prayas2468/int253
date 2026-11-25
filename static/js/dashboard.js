/* dashboard.js — Chart.js + Leaflet rendering with responsive, theme-aware output */
(function () {
    var chartInstances = [];
    var mapState = { map: null, stateLayer: null, markers: [], tiles: null, counts: {}, maxCount: 0 };

    function cssVar(name, fallback) {
        var value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        return value || fallback;
    }

    function showEmpty(canvas, message) {
        var body = canvas.parentNode;
        if (!body || body.querySelector('.chart-empty')) return;
        canvas.style.display = 'none';
        var note = document.createElement('div');
        note.className = 'chart-empty';
        note.textContent = message;
        body.appendChild(note);
    }

    function clearEmpty(canvas) {
        var body = canvas.parentNode;
        if (!body) return;
        var note = body.querySelector('.chart-empty');
        if (note) note.remove();
        canvas.style.display = '';
    }

    function readData() {
        var el = document.getElementById('dashboard-data');
        if (!el) return null;
        try { return JSON.parse(el.textContent); } catch (e) { return null; }
    }

    function palette() {
        return {
            primary: cssVar('--primary', '#3B82F6'),
            accent: cssVar('--accent', '#06B6D4'),
            success: cssVar('--success', '#10B981'),
            warning: cssVar('--warning', '#F59E0B'),
            info: cssVar('--info', '#3B82F6'),
            text: cssVar('--text', '#0F172A'),
            muted: cssVar('--muted', '#64748B'),
            border: cssVar('--border', 'rgba(15,23,42,.1)'),
            card: cssVar('--card', '#FFFFFF')
        };
    }

    function baseOptions(colors) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            resizeDelay: 120,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: colors.card,
                    titleColor: colors.text,
                    bodyColor: colors.text,
                    borderColor: colors.border,
                    borderWidth: 1,
                    padding: 10,
                    displayColors: false
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: colors.muted, font: { size: 10 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: colors.border, drawBorder: false },
                    ticks: { color: colors.muted, font: { size: 10 }, precision: 0 }
                }
            }
        };
    }

    function destroyCharts() {
        chartInstances.forEach(function (chart) {
            try { chart.destroy(); } catch (e) {}
        });
        chartInstances = [];
    }

    function addChart(chart) {
        chartInstances.push(chart);
        return chart;
    }

    function renderSparklines(colors) {
        document.querySelectorAll('.sparkline').forEach(function (canvas) {
            clearEmpty(canvas);
            var wrap = canvas.parentNode;
            if (!wrap || !wrap.clientWidth) return;
            var raw = canvas.getAttribute('data-values') || '';
            var values = raw.split(',').map(function (value) {
                return Number(value.trim()) || 0;
            }).filter(function (value) { return Number.isFinite(value); });
            if (!values.length) return;

            addChart(new Chart(canvas, {
                type: 'line',
                data: {
                    labels: values.map(function (_, index) { return index + 1; }),
                    datasets: [{
                        data: values,
                        borderColor: colors.primary,
                        backgroundColor: colors.primary + '1F',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    resizeDelay: 100,
                    events: [],
                    layout: { padding: { top: 4, right: 1, bottom: 2, left: 1 } },
                    plugins: { legend: { display: false }, tooltip: { enabled: false } },
                    scales: {
                        x: { display: false },
                        y: { display: false, beginAtZero: true }
                    },
                    animation: { duration: 600 }
                }
            }));
        });
    }

    function mapColors() {
        return {
            primary: cssVar('--primary', '#3B82F6'),
            primarySoft: cssVar('--primary-soft', 'rgba(59,130,246,.16)'),
            accent: cssVar('--accent', '#06B6D4'),
            dark: document.documentElement.getAttribute('data-theme') === 'dark'
        };
    }

    /* Theme-aware key-free basemaps. CARTO's tile CDN now returns an
       "API KEY REQUIRED" placeholder, so Esri's grayscale canvas is used:
       dark for the dark theme, light for the light theme. */
    function tileUrl() {
        var dark = document.documentElement.getAttribute('data-theme') === 'dark';
        var layer = dark ? 'World_Dark_Gray_Base' : 'World_Light_Gray_Base';
        return 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/' + layer + '/MapServer/tile/{z}/{y}/{x}';
    }

    function escapeHtml(value) {
        return String(value).replace(/[&<>"']/g, function (char) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char];
        });
    }

    function useStateFallback(container, message) {
        container.style.display = 'none';
        var fallback = document.getElementById('india-map-fallback');
        if (!fallback) return;
        var note = fallback.querySelector('p');
        if (note && message) note.textContent = message;
        fallback.hidden = false;
    }

    function stateStyle(colors, count) {
        var max = mapState.maxCount || 1;
        if (count && count > 0) {
            var ratio = Math.max(0.2, Math.min(1, count / max));
            return {
                color: colors.accent,
                weight: 1.3,
                opacity: 0.9,
                fillColor: colors.accent,
                fillOpacity: 0.16 + ratio * 0.4
            };
        }
        return {
            color: colors.primary,
            weight: 1,
            opacity: colors.dark ? 0.4 : 0.5,
            fillColor: colors.primary,
            fillOpacity: colors.dark ? 0.08 : 0.1
        };
    }

    function initMap() {
        var container = document.getElementById('india-map');
        if (!container) return;
        var dataEl = document.getElementById('map-data');
        if (!dataEl) return;

        if (typeof window.L === 'undefined') {
            useStateFallback(container, 'Interactive map unavailable offline — showing the static India state map.');
            return;
        }

        var points = [];
        try { points = JSON.parse(dataEl.textContent) || []; } catch (e) { points = []; }

        var countByName = {};
        points.forEach(function (point) { countByName[point.state] = point.count; });
        mapState.counts = countByName;
        mapState.maxCount = points.reduce(function (acc, point) { return Math.max(acc, point.count); }, 1);

        var map = L.map(container, {
            center: [22.8, 79.5],
            zoom: 4,
            minZoom: 3,
            maxZoom: 10,
            zoomSnap: 0.5,
            zoomDelta: 0.5,
            scrollWheelZoom: false,
            zoomControl: true,
            attributionControl: true
        });

        var colors = mapColors();
        mapState.map = map;
        mapState.markers = [];
        mapState.stateLayer = null;

        mapState.tiles = L.tileLayer(tileUrl(), {
            maxZoom: 19,
            attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, HERE'
        }).addTo(map);
        mapState.tiles.on('tileerror', function () {
            container.classList.add('tiles-offline');
        });

        function addMarkers() {
            if (!points.length) {
                var fallback = L.circleMarker([22.8, 79.5], {
                    radius: 9,
                    color: colors.primary,
                    weight: 2,
                    fillColor: colors.accent,
                    fillOpacity: 0.6,
                    className: 'glow-marker'
                }).addTo(map);
                fallback.bindPopup('<div class="map-popup"><strong>No state data yet</strong><span>Upload records to populate the map.</span></div>');
                mapState.markers.push(fallback);
                return;
            }

            var max = points.reduce(function (acc, point) { return Math.max(acc, point.count); }, 1);

            points.forEach(function (point) {
                var radius = 8 + Math.sqrt(point.count / max) * 20;
                var marker = L.circleMarker([point.lat, point.lng], {
                    radius: radius,
                    color: colors.accent,
                    weight: 2,
                    opacity: 0.95,
                    fillColor: colors.primary,
                    fillOpacity: 0.55,
                    className: 'glow-marker'
                }).addTo(map);

                marker.bindPopup(
                    '<div class="map-popup"><strong>' + escapeHtml(point.state) + '</strong>' +
                    '<span>' + point.count + ' document' + (point.count === 1 ? '' : 's') + '</span><br>' +
                    '<a href="?state=' + encodeURIComponent(point.state) + '">Filter dashboard</a></div>'
                );
                marker.bindTooltip(escapeHtml(point.state) + ' · ' + point.count, { direction: 'top', offset: [0, -4] });
                mapState.markers.push(marker);
            });
        }

        function fit() {
            if (mapState.stateLayer) {
                map.fitBounds(mapState.stateLayer.getBounds(), { padding: [10, 10] });
                // Keep India prominent instead of zooming out to the whole continent.
                if (map.getZoom() < 3.5) {
                    map.setView([22.8, 79.5], 3.5, { animate: false });
                }
            } else if (mapState.markers.length) {
                var group = L.featureGroup(mapState.markers);
                map.fitBounds(group.getBounds(), { padding: [36, 36], maxZoom: 5 });
            }
        }

        function resize() {
            map.invalidateSize();
        }

        var geojsonUrl = container.getAttribute('data-geojson-url');
        if (!geojsonUrl) {
            addMarkers();
            fit();
            return;
        }

        fetch(geojsonUrl)
            .then(function (response) {
                if (!response.ok) throw new Error('map data unavailable');
                return response.json();
            })
            .then(function (geojson) {
                var stateLayer = L.geoJSON(geojson, {
                    style: function (feature) {
                        var name = feature.properties && feature.properties.name ? feature.properties.name : '';
                        return stateStyle(mapColors(), countByName[name] || 0);
                    },
                    onEachFeature: function (feature, layer) {
                        var name = feature.properties && feature.properties.name ? feature.properties.name : 'State';
                        var count = countByName[name] || 0;
                        layer.bindTooltip(
                            escapeHtml(name) + (count ? ' · ' + count + ' doc' + (count === 1 ? '' : 's') : ''),
                            { sticky: true, direction: 'top', className: 'state-tooltip' }
                        );
                        layer.on('mouseover', function () {
                            layer.setStyle({ weight: 2.2, opacity: 0.95, fillOpacity: 0.82 });
                        });
                        layer.on('mouseout', function () {
                            layer.setStyle(stateStyle(mapColors(), count));
                        });
                        layer.on('click', function () {
                            window.location.href = '?state=' + encodeURIComponent(name);
                        });
                    }
                }).addTo(map);

                mapState.stateLayer = stateLayer;
                colors = mapColors();
                addMarkers();
                fit();
                setTimeout(resize, 120);
                setTimeout(fit, 180);
            })
            .catch(function () {
                useStateFallback(container, 'Interactive map unavailable — showing the static India state map.');
            });

        window.addEventListener('resize', resize);
    }

    function refreshMapTheme() {
        var colors = mapColors();
        if (mapState.tiles) {
            mapState.tiles.setUrl(tileUrl());
        }
        mapState.markers.forEach(function (marker) {
            marker.setStyle({ color: colors.accent, fillColor: colors.primary });
        });
        if (mapState.stateLayer) {
            var counts = mapState.counts || {};
            mapState.stateLayer.eachLayer(function (layer) {
                if (!layer.setStyle || !layer.feature) return;
                var props = layer.feature.properties || {};
                layer.setStyle(stateStyle(colors, counts[props.name] || 0));
            });
        }
    }

    function renderCharts() {
        destroyCharts();

        if (typeof window.Chart === 'undefined') {
            document.querySelectorAll('.chart-body canvas').forEach(function (canvas) {
                showEmpty(canvas, 'Charts need an internet connection to load Chart.js.');
            });
            return;
        }

        var colors = palette();
        Chart.defaults.font.family = "'Inter', 'Segoe UI', sans-serif";
        Chart.defaults.color = colors.muted;

        var data = readData();
        document.querySelectorAll('.chart-body canvas').forEach(clearEmpty);
        renderSparklines(colors);

        var uploads = document.getElementById('uploadsLineChart');
        if (uploads) {
            var uploadsData = data && data.uploads;
            if (uploadsData && uploadsData.labels && uploadsData.labels.length) {
                var options = baseOptions(colors);
                options.plugins.legend = { display: false };
                addChart(new Chart(uploads, {
                    type: 'line',
                    data: {
                        labels: uploadsData.labels,
                        datasets: [{
                            label: 'Uploads',
                            data: uploadsData.values,
                            borderColor: colors.primary,
                            backgroundColor: colors.primary + '1F',
                            borderWidth: 2.5,
                            fill: true,
                            tension: 0.4,
                            pointRadius: 0,
                            pointHoverRadius: 5,
                            pointHoverBackgroundColor: colors.primary
                        }]
                    },
                    options: options
                }));
            } else {
                showEmpty(uploads, 'No upload activity in the last 30 days.');
            }
        }

        var status = document.getElementById('statusDoughnutChart');
        if (status) {
            var statusData = data && data.status;
            var total = statusData ? statusData.values.reduce(function (a, b) { return a + b; }, 0) : 0;
            if (total > 0) {
                addChart(new Chart(status, {
                    type: 'doughnut',
                    data: {
                        labels: statusData.labels,
                        datasets: [{
                            data: statusData.values,
                            backgroundColor: [colors.warning, colors.info, colors.success, colors.accent],
                            borderWidth: 0,
                            hoverOffset: 6
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        resizeDelay: 120,
                        cutout: '66%',
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: { color: colors.muted, boxWidth: 10, boxHeight: 10, padding: 14, font: { size: 11 } }
                            },
                            tooltip: {
                                backgroundColor: colors.card,
                                titleColor: colors.text,
                                bodyColor: colors.text,
                                borderColor: colors.border,
                                borderWidth: 1,
                                padding: 10
                            }
                        }
                    }
                }));
            } else {
                showEmpty(status, 'No documents to summarise yet.');
            }
        }

        var district = document.getElementById('districtBarChart');
        if (district) {
            var districtData = data && data.districts;
            var hasDistrict = districtData && districtData.values.some(function (value) { return value > 0; });
            if (hasDistrict) {
                var districtOptions = baseOptions(colors);
                districtOptions.plugins.legend = { display: false };
                addChart(new Chart(district, {
                    type: 'bar',
                    data: {
                        labels: districtData.labels,
                        datasets: [{
                            label: 'Documents',
                            data: districtData.values,
                            backgroundColor: colors.primary,
                            hoverBackgroundColor: colors.accent,
                            borderRadius: 7,
                            maxBarThickness: 38
                        }]
                    },
                    options: districtOptions
                }));
            } else {
                showEmpty(district, 'No district data yet. Upload records to populate this chart.');
            }
        }
    }

    function init() {
        initMap();
        renderCharts();
    }

    // Rebuild charts with theme-aware colors; restyle map bubbles without rebuilding the map.
    document.addEventListener('bhoomiai:themechange', function () {
        setTimeout(function () {
            renderCharts();
            refreshMapTheme();
            if (mapState.map) mapState.map.invalidateSize();
        }, 90);
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

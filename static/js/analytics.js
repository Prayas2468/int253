/* analytics.js — theme-aware Chart.js rendering for the predictive analytics pages.
   Every value comes from the JSON payload rendered by Django; nothing is hardcoded. */
(function () {
    var chartInstances = [];

    function cssVar(name, fallback) {
        var value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        return value || fallback;
    }

    function readData() {
        var el = document.getElementById('analytics-data');
        if (!el) return {};
        try { return JSON.parse(el.textContent) || {}; } catch (e) { return {}; }
    }

    function palette() {
        var dark = document.documentElement.getAttribute('data-theme') === 'dark';
        return {
            primary: cssVar('--primary', '#3B82F6'),
            primaryStrong: cssVar('--primary-strong', '#2563EB'),
            accent: cssVar('--accent', '#06B6D4'),
            success: cssVar('--success', '#10B981'),
            warning: cssVar('--warning', '#F59E0B'),
            danger: cssVar('--danger', '#EF4444'),
            text: cssVar('--text', '#0F172A'),
            muted: cssVar('--muted', '#64748B'),
            border: cssVar('--border', 'rgba(15,23,42,.1)'),
            card: cssVar('--card', '#FFFFFF'),
            soft: cssVar('--card-2', '#F1F5F9'),
            dark: dark
        };
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

    function addChart(chart) {
        chartInstances.push(chart);
        return chart;
    }

    function destroyCharts() {
        chartInstances.forEach(function (chart) {
            try { chart.destroy(); } catch (e) {}
        });
        chartInstances = [];
    }

    function tooltipStyle(colors) {
        return {
            backgroundColor: colors.card,
            titleColor: colors.text,
            bodyColor: colors.text,
            borderColor: colors.border,
            borderWidth: 1,
            padding: 10,
            cornerRadius: 8
        };
    }

    function baseOptions(colors, opts) {
        opts = opts || {};
        return {
            responsive: true,
            maintainAspectRatio: false,
            resizeDelay: 110,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: !!opts.legend, labels: { color: colors.muted, boxWidth: 10, boxHeight: 10, padding: 14, font: { size: 11 } } },
                tooltip: tooltipStyle(colors)
            },
            scales: {
                x: {
                    stacked: !!opts.stacked,
                    grid: { display: false },
                    ticks: { color: colors.muted, font: { size: 10 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 10 }
                },
                y: {
                    stacked: !!opts.stacked,
                    beginAtZero: true,
                    grid: { color: colors.border },
                    ticks: { color: colors.muted, font: { size: 10 }, precision: 0 }
                }
            }
        };
    }

    function horizontalOptions(colors, labelSuffix) {
        var options = baseOptions(colors);
        options.indexAxis = 'y';
        options.scales = {
            x: {
                beginAtZero: true,
                grid: { color: colors.border },
                ticks: { color: colors.muted, font: { size: 10 }, precision: 0, callback: labelSuffix ? function (v) { return v + labelSuffix; } : undefined }
            },
            y: { grid: { display: false }, ticks: { color: colors.muted, font: { size: 10 }, autoSkip: false } }
        };
        return options;
    }

    function renderSparklines(colors, data) {
        document.querySelectorAll('.sparkline').forEach(function (canvas) {
            clearEmpty(canvas);
            var wrap = canvas.parentNode;
            if (!wrap || !wrap.clientWidth) return;
            var raw = canvas.getAttribute('data-values') || '';
            var values = raw.split(',').map(function (value) {
                return Number(value.trim()) || 0;
            }).filter(function (value) { return Number.isFinite(value); });
            if (!values.length) return;

            var height = wrap.clientHeight || 56;
            var gradient = canvas.getContext('2d').createLinearGradient(0, 0, 0, height);
            gradient.addColorStop(0, colors.primary + '59');
            gradient.addColorStop(1, colors.primary + '05');
            addChart(new Chart(canvas, {
                type: 'line',
                data: {
                    labels: values.map(function (_, index) { return index + 1; }),
                    datasets: [{
                        data: values,
                        borderColor: colors.primary,
                        backgroundColor: gradient,
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    events: [],
                    layout: { padding: { top: 4, right: 1, bottom: 2, left: 1 } },
                    plugins: { legend: { display: false }, tooltip: { enabled: false } },
                    scales: { x: { display: false }, y: { display: false, beginAtZero: true } },
                    animation: { duration: 500 }
                }
            }));
        });
    }

    function lineChart(canvas, labels, series, colors, opts) {
        opts = opts || {};
        var options = baseOptions(colors, { legend: series.length > 1 });
        if (opts.suffix) {
            options.scales.y.ticks.callback = function (value) { return value + opts.suffix; };
        }
        addChart(new Chart(canvas, {
            type: 'line',
            data: {
                labels: labels,
                datasets: series.map(function (item) {
                    return {
                        label: item.label,
                        data: item.data,
                        borderColor: item.color,
                        backgroundColor: item.fill ? item.color + '22' : 'transparent',
                        borderWidth: 2.4,
                        fill: !!item.fill,
                        tension: 0.35,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        borderDash: item.dashed ? [5, 4] : []
                    };
                })
            },
            options: options
        }));
    }

    function barChart(canvas, labels, series, colors, opts) {
        opts = opts || {};
        var options = opts.horizontal ? horizontalOptions(colors, opts.suffix || '') : baseOptions(colors, { legend: series.length > 1, stacked: !!opts.stacked });
        if (!opts.horizontal && opts.suffix) {
            options.scales.y.ticks.callback = function (value) { return value + opts.suffix; };
        }
        addChart(new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: series.map(function (item) {
                    return {
                        label: item.label,
                        data: item.data,
                        backgroundColor: item.color,
                        hoverBackgroundColor: item.hover || item.color,
                        borderRadius: 6,
                        maxBarThickness: opts.thin ? 22 : 38,
                        stack: item.stack
                    };
                })
            },
            options: options
        }));
    }

    function doughnutChart(canvas, labels, values, colours, colors, opts) {
        opts = opts || {};
        addChart(new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: colours,
                    borderWidth: 0,
                    hoverOffset: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                resizeDelay: 110,
                cutout: opts.cutout || '66%',
                plugins: {
                    legend: {
                        position: opts.legendPosition || 'bottom',
                        labels: { color: colors.muted, boxWidth: 10, boxHeight: 10, padding: 13, font: { size: 11 } }
                    },
                    tooltip: tooltipStyle(colors)
                }
            }
        }));
    }

    function render() {
        destroyCharts();
        if (typeof window.Chart === 'undefined') {
            document.querySelectorAll('.chart-shell canvas').forEach(function (canvas) {
                showEmpty(canvas, 'Charts need an internet connection to load Chart.js.');
            });
            return;
        }

        var colors = palette();
        Chart.defaults.font.family = "'Inter', 'Segoe UI', sans-serif";
        Chart.defaults.color = colors.muted;

        var data = readData();
        document.querySelectorAll('.chart-shell canvas').forEach(clearEmpty);
        renderSparklines(colors, data);

        /* Planned vs actual progress ------------------------------------ */
        var progress = document.getElementById('progressChart');
        if (progress) {
            var series = data.progress || {};
            if (series.labels && series.labels.length) {
                lineChart(progress, series.labels, [
                    { label: 'Planned progress', data: series.planned || [], color: colors.primary, dashed: true },
                    { label: 'Actual progress', data: series.actual || [], color: colors.accent, fill: true }
                ], colors, { suffix: '%' });
            } else {
                showEmpty(progress, 'No acquisition progress data available yet.');
            }
        }

        /* Risk distribution -------------------------------------------- */
        var risk = document.getElementById('riskChart');
        if (risk) {
            var riskRows = data.risk || [];
            var riskTotal = riskRows.reduce(function (a, row) { return a + row.value; }, 0);
            if (riskTotal) {
                doughnutChart(risk, riskRows.map(function (r) { return r.label; }), riskRows.map(function (r) { return r.value; }),
                    [colors.danger, colors.warning, colors.success], colors);
            } else {
                showEmpty(risk, 'No risk predictions stored yet.');
            }
        }

        /* Phase distribution ------------------------------------------- */
        var phases = document.getElementById('phaseChart');
        if (phases) {
            var phaseRows = data.phases || [];
            if (phaseRows.length) {
                barChart(phases, phaseRows.map(function (r) { return r.phase; }), [
                    { label: 'Projects', data: phaseRows.map(function (r) { return r.count; }), color: colors.primary, hover: colors.accent }
                ], colors, { horizontal: true, thin: true });
            } else {
                showEmpty(phases, 'No phase data available.');
            }
        }

        /* State-wise risk ---------------------------------------------- */
        var state = document.getElementById('stateRiskChart');
        if (state) {
            var stateRows = (data.stateRisk || []).slice(0, 10);
            if (stateRows.length) {
                barChart(state, stateRows.map(function (r) { return r.state; }), [
                    { label: 'High', data: stateRows.map(function (r) { return r.high; }), color: colors.danger, stack: 'risk' },
                    { label: 'Medium', data: stateRows.map(function (r) { return r.medium; }), color: colors.warning, stack: 'risk' },
                    { label: 'Low', data: stateRows.map(function (r) { return r.low; }), color: colors.success, stack: 'risk' }
                ], colors, { horizontal: true, stacked: true });
            } else {
                showEmpty(state, 'No state-level risk data available.');
            }
        }

        /* District analysis -------------------------------------------- */
        var district = document.getElementById('districtChart');
        if (district) {
            var districtRows = (data.districtRisk || []).slice(0, 10);
            if (districtRows.length) {
                barChart(district, districtRows.map(function (r) { return r.district; }), [
                    { label: 'High-risk projects', data: districtRows.map(function (r) { return r.high; }), color: colors.danger },
                    { label: 'All projects', data: districtRows.map(function (r) { return r.total; }), color: colors.primary }
                ], colors, { thin: true });
            } else {
                showEmpty(district, 'No district data available.');
            }
        }

        /* Compensation analysis ---------------------------------------- */
        var compensation = document.getElementById('compensationChart');
        if (compensation) {
            var compRows = data.compensation || [];
            if (compRows.length) {
                barChart(compensation, compRows.map(function (r) { return r.label; }), [
                    { label: 'Delay rate', data: compRows.map(function (r) { return r.delay_rate; }), color: colors.warning },
                    { label: 'High-risk share', data: compRows.map(function (r) { return r.total ? Math.round((r.high_risk / r.total) * 1000) / 10 : 0; }), color: colors.danger }
                ], colors, { suffix: '%' });
            } else {
                showEmpty(compensation, 'No compensation data available.');
            }
        }

        /* Approval analysis -------------------------------------------- */
        var approval = document.getElementById('approvalChart');
        if (approval) {
            var approvalRows = data.approval || [];
            if (approvalRows.length) {
                barChart(approval, approvalRows.map(function (r) { return r.status; }), [
                    { label: 'Average delay probability', data: approvalRows.map(function (r) { return r.avg_probability; }), color: colors.primary, hover: colors.accent }
                ], colors, { suffix: '%', thin: true });
            } else {
                showEmpty(approval, 'No approval data available.');
            }
        }

        /* Legal analysis ----------------------------------------------- */
        var legal = document.getElementById('legalChart');
        if (legal) {
            var legalRows = data.legal || [];
            if (legalRows.length) {
                barChart(legal, legalRows.map(function (r) { return r.label; }), [
                    { label: 'Predicted delay share', data: legalRows.map(function (r) { return r.delay_rate; }), color: colors.danger }
                ], colors, { suffix: '%' });
            } else {
                showEmpty(legal, 'No legal case data available.');
            }
        }

        /* Feature importance ------------------------------------------ */
        var importance = document.getElementById('importanceChart');
        if (importance) {
            var rows = (data.importance || []).slice(0, 10);
            if (rows.length) {
                var pretty = function (name) {
                    return name.replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
                };
                barChart(importance, rows.map(function (r) { return pretty(r.feature); }), [
                    { label: 'Importance', data: rows.map(function (r) { return Math.round(r.importance * 1000) / 10; }), color: colors.accent, hover: colors.primary }
                ], colors, { horizontal: true, suffix: '%', thin: true });
            } else {
                showEmpty(importance, 'Train the model to calculate feature importance.');
            }
        }

        /* ROC curves --------------------------------------------------- */
        var roc = document.getElementById('rocChart');
        if (roc) {
            var curves = data.roc || {};
            var names = Object.keys(curves);
            if (names.length) {
                var colours = [colors.primary, colors.accent, colors.warning];
                var options = baseOptions(colors, { legend: true });
                options.scales.x = {
                    min: 0, max: 1,
                    grid: { color: colors.border },
                    ticks: { color: colors.muted, font: { size: 10 } },
                    title: { display: true, text: 'False positive rate', color: colors.muted, font: { size: 10 } }
                };
                options.scales.y = {
                    min: 0, max: 1,
                    grid: { color: colors.border },
                    ticks: { color: colors.muted, font: { size: 10 } },
                    title: { display: true, text: 'True positive rate', color: colors.muted, font: { size: 10 } }
                };
                addChart(new Chart(roc, {
                    type: 'line',
                    data: {
                        labels: (curves[names[0]].fpr || []).map(function (value) { return value.toFixed(2); }),
                        datasets: names.map(function (name, index) {
                            return {
                                label: name,
                                data: (curves[name].tpr || []).map(function (value, i) {
                                    return { x: (curves[name].fpr || [])[i], y: value };
                                }),
                                borderColor: colours[index % colours.length],
                                backgroundColor: 'transparent',
                                borderWidth: 2.2,
                                tension: 0,
                                pointRadius: 0,
                                parsing: false
                            };
                        }).concat([{
                            label: 'Chance',
                            data: [{ x: 0, y: 0 }, { x: 1, y: 1 }],
                            borderColor: colors.muted,
                            borderDash: [4, 4],
                            borderWidth: 1.2,
                            pointRadius: 0,
                            parsing: false
                        }])
                    },
                    options: options
                }));
            } else {
                showEmpty(roc, 'ROC curves become available after training.');
            }
        }

        /* Prediction volume trend ------------------------------------- */
        var trend = document.getElementById('predictionTrendChart');
        if (trend) {
            var trendData = data.predictionTrend || {};
            if (trendData.labels && trendData.labels.length) {
                barChart(trend, trendData.labels, [
                    { label: 'Predictions', data: trendData.values || [], color: colors.primary, hover: colors.accent }
                ], colors, { thin: true });
            } else {
                showEmpty(trend, 'No predictions recorded yet.');
            }
        }
    }

    document.addEventListener('bhoomiai:themechange', function () {
        setTimeout(render, 90);
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', render);
    } else {
        render();
    }
})();

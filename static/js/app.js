/* app.js — upload dropzone, table search, OCR progress */
(function () {
    function formatBytes(bytes) {
        if (!bytes) return '0 KB';
        var units = ['B', 'KB', 'MB', 'GB'];
        var index = Math.floor(Math.log(bytes) / Math.log(1024));
        return (bytes / Math.pow(1024, index)).toFixed(index ? 1 : 0) + ' ' + units[index];
    }

    // Drag and drop upload zone
    document.querySelectorAll('[data-dropzone]').forEach(function (zone) {
        var input = zone.querySelector('input[type="file"]');
        var preview = document.querySelector('[data-dz-preview]');
        if (!input) return;

        ['dragenter', 'dragover'].forEach(function (name) {
            zone.addEventListener(name, function (event) {
                event.preventDefault();
                zone.classList.add('is-dragover');
            });
        });

        ['dragleave', 'drop'].forEach(function (name) {
            zone.addEventListener(name, function (event) {
                event.preventDefault();
                zone.classList.remove('is-dragover');
            });
        });

        zone.addEventListener('drop', function (event) {
            if (event.dataTransfer && event.dataTransfer.files.length) {
                input.files = event.dataTransfer.files;
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });

        input.addEventListener('change', function () {
            if (!input.files || !input.files.length) {
                if (preview) preview.classList.remove('is-visible');
                return;
            }
            var file = input.files[0];
            if (preview) {
                var name = preview.querySelector('[data-dz-name]');
                var size = preview.querySelector('[data-dz-size]');
                if (name) name.textContent = file.name;
                if (size) size.textContent = formatBytes(file.size);
                preview.classList.add('is-visible');
            }
        });
    });

    // Client-side table filtering
    document.querySelectorAll('[data-table-filter]').forEach(function (input) {
        var table = document.querySelector(input.getAttribute('data-table-filter'));
        if (!table) return;
        input.addEventListener('input', function () {
            var term = input.value.toLowerCase().trim();
            table.querySelectorAll('tbody tr').forEach(function (row) {
                row.style.display = row.textContent.toLowerCase().indexOf(term) !== -1 ? '' : 'none';
            });
        });
    });

    // Loading state for forms that trigger OCR / long actions
    document.querySelectorAll('form[data-loading]').forEach(function (form) {
        form.addEventListener('submit', function () {
            var button = form.querySelector('button[type="submit"]');
            if (button) {
                button.classList.add('is-loading');
                button.disabled = true;
            }
        });
    });

    // Copy-to-clipboard
    document.querySelectorAll('[data-copy]').forEach(function (button) {
        button.addEventListener('click', function () {
            var value = button.getAttribute('data-copy');
            if (navigator.clipboard) {
                navigator.clipboard.writeText(value).then(function () {
                    var old = button.textContent;
                    button.textContent = 'Copied';
                    setTimeout(function () { button.textContent = old; }, 1400);
                });
            }
        });
    });
})();

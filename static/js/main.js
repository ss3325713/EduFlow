// EduFlow Academy - Client Interactive Script
document.addEventListener('DOMContentLoaded', function () {
    // Sidebar toggle for mobile view
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.querySelector('.app-sidebar');

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function () {
            sidebar.classList.toggle('show');
        });
    }

    // Auto dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Attendance bulk mark helper (Mark All Present)
    const btnMarkAllPresent = document.getElementById('btnMarkAllPresent');
    if (btnMarkAllPresent) {
        btnMarkAllPresent.addEventListener('click', function () {
            const radios = document.querySelectorAll('input[type="radio"][value="present"]');
            radios.forEach(r => r.checked = true);
        });
    }

    // Dynamic filtering of Batches & Subjects based on selected Class
    setupClassCascadingFilters();
});

function setupClassCascadingFilters() {
    const classSelects = document.querySelectorAll('select[name="class_id"]');
    classSelects.forEach(function(classSelect) {
        const form = classSelect.closest('form');
        if (!form) return;

        const batchSelect = form.querySelector('select[name="batch_id"], select[name="new_batch_id"]');
        const subjectSelect = form.querySelector('select[name="subject_id"]');

        function filterDropdown(selectEl) {
            if (!selectEl) return;
            const selectedClassId = classSelect.value;
            const options = selectEl.querySelectorAll('option');

            options.forEach(function(opt) {
                if (!opt.value) {
                    opt.hidden = false;
                    return;
                }
                const optClassId = opt.getAttribute('data-class-id');
                if (!optClassId || !selectedClassId || optClassId === selectedClassId) {
                    opt.hidden = false;
                    opt.disabled = false;
                } else {
                    opt.hidden = true;
                    opt.disabled = true;
                    if (opt.selected) {
                        selectEl.value = "";
                    }
                }
            });
        }

        classSelect.addEventListener('change', function() {
            filterDropdown(batchSelect);
            filterDropdown(subjectSelect);
        });

        // Run initial filter on page load if a class is already selected
        if (classSelect.value) {
            filterDropdown(batchSelect);
            filterDropdown(subjectSelect);
        }
    });
}

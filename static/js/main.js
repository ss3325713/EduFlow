// EduFlow Academy - Client Interactive Script & Mobile Drawer Handler
document.addEventListener('DOMContentLoaded', function () {
    // Sidebar toggle for mobile view
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarCloseBtn = document.getElementById('sidebarCloseBtn');
    const sidebar = document.querySelector('.app-sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    function openSidebar() {
        if (sidebar) sidebar.classList.add('show');
        if (sidebarOverlay) sidebarOverlay.classList.add('show');
        document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
        if (sidebar) sidebar.classList.remove('show');
        if (sidebarOverlay) sidebarOverlay.classList.remove('show');
        document.body.style.overflow = '';
    }

    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function (e) {
            e.stopPropagation();
            if (sidebar && sidebar.classList.contains('show')) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });
    }

    if (sidebarCloseBtn) {
        sidebarCloseBtn.addEventListener('click', closeSidebar);
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', closeSidebar);
    }

    // Auto-close sidebar when clicking any navigation link on mobile
    const sidebarNavLinks = document.querySelectorAll('.app-sidebar .nav-link-item');
    sidebarNavLinks.forEach(link => {
        link.addEventListener('click', function() {
            if (window.innerWidth < 768) {
                closeSidebar();
            }
        });
    });

    // Close on Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && sidebar && sidebar.classList.contains('show')) {
            closeSidebar();
        }
    });

    // Reset overflow if window is resized above mobile breakpoint
    window.addEventListener('resize', function() {
        if (window.innerWidth >= 768) {
            closeSidebar();
        }
    });

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

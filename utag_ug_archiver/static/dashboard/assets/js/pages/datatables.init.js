$(document).ready(function() {
    var $datatable = $("#datatable");

    function recalc(dt) {
        if (!dt) {
            return;
        }
        dt.columns.adjust();
        if (dt.responsive) {
            dt.responsive.recalc();
        }
    }

    // Initialize once with Responsive enabled.
    // Recalculate after layout settles to prevent incorrect width measurement
    // (common with sidebars/animations) that can hide nearly all columns.
    if ($datatable.length && !$.fn.dataTable.isDataTable($datatable)) {
        var dt = $datatable.DataTable({
            responsive: {
                details: {
                    type: "inline",
                    target: "tr"
                }
            },
            autoWidth: !1
        });

        // Initial recalcs: one quick, one after layout/preloader settles.
        setTimeout(function() {
            recalc(dt);
        }, 150);
        setTimeout(function() {
            recalc(dt);
        }, 700);

        // Recalc after full load (fonts/images can change widths).
        $(window).on("load", function() {
            setTimeout(function() {
                recalc(dt);
            }, 50);
        });

        // Recalc on resize.
        $(window).on("resize", function() {
            recalc(dt);
        });

        // Recalc when sidebar toggles (width changes with animation).
        $(document).on("click", "#vertical-menu-btn", function() {
            setTimeout(function() {
                recalc(dt);
            }, 400);
        });
    }

    var $datatableButtons = $("#datatable-buttons");
    if ($datatableButtons.length && !$.fn.dataTable.isDataTable($datatableButtons)) {
        var dtButtons = $datatableButtons.DataTable({
            responsive: {
                details: {
                    type: "inline",
                    target: "tr"
                }
            },
            autoWidth: !1,
            lengthChange: !1,
            buttons: ["copy", "excel", "pdf", "colvis"]
        });
        dtButtons.buttons().container().appendTo("#datatable-buttons_wrapper .col-md-6:eq(0)");

        setTimeout(function() {
            recalc(dtButtons);
        }, 150);
        setTimeout(function() {
            recalc(dtButtons);
        }, 700);

        $(window).on("load", function() {
            setTimeout(function() {
                recalc(dtButtons);
            }, 50);
        });

        $(window).on("resize", function() {
            recalc(dtButtons);
        });

        $(document).on("click", "#vertical-menu-btn", function() {
            setTimeout(function() {
                recalc(dtButtons);
            }, 400);
        });
    }

    $(".dataTables_length select").addClass("form-select form-select-sm");
});
# Accessibility Report

Automated axe coverage passed 18/18 with no critical or serious violations across login, home, dashboards, dashboard studio/share dialog, pipelines, pipeline studio, settings, members, connections, datasets, developer, forbidden, not-found, collapsed navigation, and mobile navigation/studios.

Mobile behavioral checks passed 5/5: 320px login, Escape/focus restoration in the navigation drawer, top-bar containment, and horizontal-overflow checks for dashboard and pipeline studios. Shared component browser tests covered keyboard menus, notification focus trap, command palette focus restoration, sortable table semantics, and share-dialog naming/focus.

Limitations: axe does not replace a screen-reader audit, manual contrast review, full zoom sweep, or assistive-technology verification. Firefox share/save timing remains flaky. Therefore accessibility evidence is strong but not a complete WCAG conformance assessment.

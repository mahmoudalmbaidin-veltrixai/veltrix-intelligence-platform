# Dashboard Save Behavioral Tests

`src/modules/dashboards/DashboardStudioView.spec.ts` exercises the real view/store/router behavior with network control only where race/error timing must be deterministic.

Covered behavior:

1. edits during an in-flight save;
2. joined save requests;
3. failed create does not navigate;
4. failed update retains dirty state;
5. publish stops when prerequisite save fails;
6. leave guard blocks a real unsaved exit;
7. post-create navigation bypasses the guard exactly once;
8. cache refresh after persistence;
9. server version conflict;
10. duplicate keyboard save;
11. autosave plus manual save;
12. late response after newer local edits;
13. router navigation rejection;
14. 409/422/500 handling;
15. immediate refresh after save/live Firefox happy path.

The focused suite passed 12 test cases containing these scenario assertions; the live Firefox persistence path passed 40/40. Assertions were not weakened and no fixed sleep was added.

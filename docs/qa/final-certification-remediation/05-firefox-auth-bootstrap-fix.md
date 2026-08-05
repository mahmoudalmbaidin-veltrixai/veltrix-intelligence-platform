# Firefox Authentication and Bootstrap Fix

## Contract

`login()` is single-flight and attempt-generation scoped. A successful credential response is not considered authenticated until the browser adopts the session cookie, `/auth/me` confirms the user, required organization/workspace state loads, and one awaited `router.replace()` reaches the intended route. Stale responses cannot commit, duplicate submissions join, and bootstrap/navigation failures surface to the login view instead of leaving a silent partial session.

## Behavioral proof

Store/login tests cover success, delayed current-user, delayed organization bootstrap, failed bootstrap after login 200, duplicate submission, stale response, refresh restoration, cookie adoption, and absence of a persistent `/login` state. Browser proof exercises the live API and production frontend.

Final-tree commands:

```powershell
.\tests\e2e\run-local-certification.ps1 --project=firefox-desktop dashboard-save-reliability.spec.ts --repeat-each=20
.\tests\e2e\run-local-certification.ps1 --project=firefox-desktop dashboard-save-reliability.spec.ts --repeat-each=20
```

Results: 20/20 and 20/20, all first attempts, zero Playwright retries and zero artifact-secret findings.

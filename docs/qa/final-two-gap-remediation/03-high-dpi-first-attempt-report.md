# High-DPI First-Attempt Report

Before execution, Docker services were healthy, the host had approximately 24.3 GB of
47.48 GB memory available, Docker had 22 CPUs and approximately 23.2 GB memory, disk
space was healthy, Playwright Chromium build 1228 was installed, and no residual
Chrome, Chromium, or Playwright browser process conflicted with the run.

Command:

```powershell
.\tests\e2e\run-local-certification.ps1 --project=chrome-high-dpi
```

Result: 23/23 passed on the first and only attempt in approximately 1.5 minutes, with
zero Playwright retries. Artifact sanitation scanned the retained result, made three
structural redactions, and found zero remaining secrets.

The earlier candidate's pre-`newPage` Chromium infrastructure exit remains in prior
history; it did not recur on this stabilized host and is not represented as a VIP
application defect.

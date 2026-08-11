# WebKit collapsed nav tooltip evidence (VIP-BUG-012)

Root cause: 220ms rail float-expand remount race cleared hover tooltips under WebKit.

Fix:
- VipTooltip: pointer events + 180ms close delay
- AppSidebar: 420ms hover dwell; keep labels in DOM via `hidden` instead of `v-if`
- Accessible name retained for icon-only collapsed state; keyboard focus opens tooltip

Results (focused E2E `collapsed navigation stays discoverable...`):
- Chrome desktop: PASSED
- Firefox desktop: PASSED
- WebKit desktop: PASSED

# AI Placeholder Disposition

Disposition: hide incomplete AI Knowledge and AI Studio surfaces from production.

Production access requires all of the following: feature flag enabled, entitlement present, route capability permitted, and a production-ready implementation boundary. Development mock mode is allowed only when explicitly enabled outside production.

Enforcement applies to router discovery/direct URL navigation, desktop/mobile navigation, command palette, command/search providers, and quick actions. A direct URL fails closed. Live production mode cannot display hard-coded documents or the placeholder upload surface.

Tests cover flag off/entitlement off, flag on/entitlement off, flag off/entitlement on, flag on/entitlement on, production live mode, and explicitly permitted development mock mode. No backend authorization was relaxed; hidden UI is not treated as an API security boundary.

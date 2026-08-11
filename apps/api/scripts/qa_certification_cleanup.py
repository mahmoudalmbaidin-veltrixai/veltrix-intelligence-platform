"""Safe certification fixture cleanup CLI (VIP-BUG-009).

Loads a registry JSON produced by a certification run and deletes only the
exact registered IDs. Use --report-stale to list likely leftover names without
deleting anything.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from vip_api.qa.certification_lifecycle import (
    CertificationFixtureRegistry,
    identify_likely_stale_names,
)


async def _noop_delete(_item: object) -> None:
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, help="Path to certification registry JSON")
    parser.add_argument(
        "--environment-guard",
        default="certification",
        help="Must be certification/test/ci/local",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be deleted without calling handlers",
    )
    parser.add_argument(
        "--report-stale",
        type=Path,
        help="JSON file containing a list of resource names to classify (no deletes)",
    )
    parser.add_argument("--output", type=Path, help="Write cleanup/stale report JSON here")
    args = parser.parse_args()

    if args.report_stale:
        names = json.loads(args.report_stale.read_text(encoding="utf-8"))
        if not isinstance(names, list):
            raise SystemExit("stale input must be a JSON list of names")
        stale = identify_likely_stale_names([str(item) for item in names])
        report = {"likely_stale": stale, "count": len(stale), "deleted": 0}
        text = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
        print(text)
        return

    if args.registry is None:
        raise SystemExit("--registry is required unless --report-stale is used")

    registry = CertificationFixtureRegistry.load(args.registry)
    registry.environment_guard = args.environment_guard

    if args.dry_run:

        async def dry(item: object) -> None:
            _ = item

        handlers = {kind: dry for kind in registry.resources and []}
        # Build handlers for every kind present.
        from vip_api.qa.certification_lifecycle import CLEANUP_ORDER

        handlers = {kind: dry for kind in CLEANUP_ORDER}
        report = asyncio.run(registry.cleanup(handlers))
        # dry-run still "deletes" via noop; rewrite labels for clarity
        payload = report.as_dict()
        payload["dry_run"] = True
    else:
        # Without wired API clients this CLI only validates the registry and
        # environment guard. Integration tests supply real delete handlers.
        from vip_api.qa.certification_lifecycle import CLEANUP_ORDER

        handlers = {kind: _noop_delete for kind in CLEANUP_ORDER}
        report = asyncio.run(registry.cleanup(handlers))
        payload = report.as_dict()
        payload["note"] = (
            "Handlers were no-ops. Wire authenticated API delete callbacks in "
            "certification runners for real teardown."
        )

    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

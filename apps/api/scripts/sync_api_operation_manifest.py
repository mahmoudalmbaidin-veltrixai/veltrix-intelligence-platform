"""Write or verify the reviewed OpenAPI operation manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from vip_api.api.operation_manifest import (
    DEFAULT_MANIFEST_PATH,
    assert_manifest_matches,
    write_manifest,
)
from vip_api.main import create_application
from vip_api.core.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Reviewed manifest path",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare live OpenAPI to the reviewed manifest without rewriting it",
    )
    args = parser.parse_args()
    document = create_application(get_settings()).openapi()
    if args.check:
        actual = assert_manifest_matches(document, args.output)
        print(
            f"manifest_ok operations={actual['operation_count']} "
            f"paths={actual['path_count']} levels={actual['authentication_levels']}"
        )
        return
    manifest = write_manifest(document, args.output)
    print(
        f"wrote {args.output} operations={manifest['operation_count']} "
        f"paths={manifest['path_count']} levels={manifest['authentication_levels']}"
    )


if __name__ == "__main__":
    main()

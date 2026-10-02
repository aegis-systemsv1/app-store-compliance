#!/usr/bin/env python3
"""Validates ANY Compliance Pack file (the authored catalogue, or an exported
pack) against the same rules scripts/validate.py applies to the authored
catalogue. Independent of the export step, so a consumer -- or this repo's
CI -- can check a pack file on its own.

Usage:
    python3 scripts/validate-compliance-pack.py [PATH]

PATH defaults to data/compliance-pack-requirements.json. Pass an exported
pack path (compliance-pack/exports/compliance-pack-vX.Y.Z.json) to validate
an export instead. Exported packs are validated with strict=False, since
they have no catalogue_items_covered manifest to cross-check against (that
manifest only exists in the authored source file).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from validate import (  # noqa: E402
    COMPLIANCE_REQUIREMENTS,
    validate_compliance_requirements,
)


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else COMPLIANCE_REQUIREMENTS
    is_source_catalogue = os.path.abspath(path) == os.path.abspath(
        COMPLIANCE_REQUIREMENTS
    )

    # A pack envelope (not the authored source) must additionally have the
    # provenance/license block an actual export always stamps.
    if not is_source_catalogue and os.path.exists(path):
        try:
            data = json.load(open(path))
        except Exception as e:
            print(f"  ERROR. Failed to parse {path}: {e}")
            return 1
        source = data.get("source", {})
        for field in ("repo", "commit", "exported_at", "license", "license_origin"):
            if not source.get(field):
                print(f"  ERROR. exported pack missing source.{field}")
                return 1
        if source.get("license") != "OpenRoots Agent License 2.3":
            print(
                f"  ERROR. exported pack source.license is '{source.get('license')}', "
                "expected 'OpenRoots Agent License 2.3'"
            )
            return 1

    errors, warnings, count = validate_compliance_requirements(
        path=path, strict=is_source_catalogue
    )
    for w in warnings:
        print(f"  warn. {w}")
    for e in errors:
        print(f"  ERROR. {e}")
    if errors:
        print(f"\nvalidate-compliance-pack. FAILED with {len(errors)} error(s).")
        return 1
    print(f"validate-compliance-pack. OK. {count} requirements, 0 errors.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Exports data/compliance-pack-requirements.json as a versioned Compliance
Pack (data/compliance-pack-schema.json), stamping real git provenance
(commit, tag, export time) and the repository's licence/attribution block.

Validates the requirement catalogue with the exact same logic
scripts/validate.py uses (imported, not duplicated) before writing anything.
A malformed requirement fails the whole export -- there is no partial pack.

Usage:
    python3 scripts/export-compliance-pack.py [--pack-version X.Y.Z] [--out PATH]

The default pack_version is the catalogue's own catalogue_version field.
Output defaults to compliance-pack/exports/compliance-pack-v{version}.json.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from validate import (  # noqa: E402
    COMPLIANCE_REQUIREMENTS,
    validate_compliance_requirements,
)

PACK_SCHEMA_VERSION = "1.0.0"
LICENSE = "OpenRoots Agent License 2.3"
LICENSE_ORIGIN = (
    "Derived from app-store-compliance by Mirza Iqbal (mjmirza); "
    "this fork: aegis-systemsv1/app-store-compliance"
)
DEFAULT_OUT_DIR = os.path.join(ROOT, "compliance-pack", "exports")


def run_git(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return ""


def build_pack(pack_version: str) -> dict:
    catalogue = json.load(open(COMPLIANCE_REQUIREMENTS))
    commit = run_git("rev-parse", "HEAD")
    tag = run_git("describe", "--tags", "--exact-match") or None

    return {
        "pack_schema_version": PACK_SCHEMA_VERSION,
        "pack_version": pack_version,
        "source": {
            "repo": "aegis-systemsv1/app-store-compliance",
            "commit": commit or "unknown",
            "tag": tag,
            "exported_at": dt.datetime.now(dt.timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "exported_by": os.environ.get("USER", "unknown"),
            "license": LICENSE,
            "license_origin": LICENSE_ORIGIN,
        },
        "requirements": catalogue["requirements"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-version", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    errors, warnings, count = validate_compliance_requirements(strict=True)
    for w in warnings:
        print(f"  warn. {w}")
    if errors:
        for e in errors:
            print(f"  ERROR. {e}")
        print(
            f"\nexport-compliance-pack. FAILED with {len(errors)} error(s). "
            "No pack file was written."
        )
        return 1

    catalogue = json.load(open(COMPLIANCE_REQUIREMENTS))
    pack_version = args.pack_version or catalogue.get("catalogue_version", "0.0.0")

    pack = build_pack(pack_version)

    out_path = args.out or os.path.join(
        DEFAULT_OUT_DIR, f"compliance-pack-v{pack_version}.json"
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(pack, f, indent=2, sort_keys=False)
        f.write("\n")

    print(
        f"export-compliance-pack. OK. {count} requirements, "
        f"pack_version={pack_version}, commit={pack['source']['commit'][:12]}, "
        f"written to {os.path.relpath(out_path, ROOT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Validates patterns/recipes/deadlines/compliance-pack-requirements data files
for CI. Exit 0 on pass, 1 on error; see README.md and AGENTS.md for the check
list."""

import json
import os
import sys
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATTERNS = os.path.join(ROOT, "data", "rejection-patterns.json")
RECIPES = os.path.join(ROOT, "data", "detection-recipes.json")
DEADLINES = os.path.join(ROOT, "data", "regulatory-deadlines.json")
COMPLIANCE_REQUIREMENTS = os.environ.get(
    "COMPLIANCE_REQUIREMENTS_FILE",
    os.path.join(ROOT, "data", "compliance-pack-requirements.json"),
)

REQUIRED_PATTERN = [
    "id",
    "platform",
    "guideline",
    "title",
    "severity",
    "detection",
    "fix",
]
SEVERITIES = {"critical", "high", "medium", "low"}
PLATFORMS = {"apple", "google", "both", "web"}

REQUIRED_DEADLINE = [
    "id",
    "jurisdiction",
    "law",
    "requirement",
    "effective_date",
    "grace_period",
    "mandatory_date",
    "enforcement_date",
    "affected_repository_sections",
    "priority",
]

# Compliance Pack requirement catalogue (data/compliance-pack-requirements.json).
# See data/compliance-pack-schema.json for the full schema this mirrors.
REQUIRED_REQUIREMENT_FIELDS = [
    "requirement_id",
    "jurisdiction",
    "regulator",
    "legislation",
    "description",
    "status",
    "applicability_conditions",
    "evidence_method",
    "evidence_requirements",
    "severity",
    "release_blocking_policy",
    "requirement_version",
    "last_verified_date",
    "change_history",
]
REQUIRED_LEGISLATION_FIELDS = ["title", "source_url", "source_retrieved_date"]
REQUIRED_EVIDENCE_ITEM_FIELDS = ["evidence_id", "description", "method"]
VALID_STATUS = {
    "CURRENT_LAW",
    "ENACTED_FUTURE_COMMENCEMENT",
    "PROPOSED_CONSULTATION",
    "GUIDANCE_GOOD_PRACTICE",
}
VALID_EVIDENCE_METHOD = {"AUTOMATED", "HYBRID", "OWNER_EVIDENCE"}
VALID_EVIDENCE_ITEM_METHOD = {"AUTOMATED", "OWNER_EVIDENCE"}
VALID_BLOCKING_POLICY = {"blocking_once_current_and_effective", "advisory_only"}

errors = []
warnings = []


def validate_date(date_str, field_name, item_id):
    try:
        datetime.datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        errors.append(
            f"deadline '{item_id}' has invalid {field_name} '{date_str}', must be YYYY-MM-DD format"
        )


def validate_compliance_requirements(path=COMPLIANCE_REQUIREMENTS, strict=True):
    """Validates the Compliance Pack requirement catalogue. Returns
    (local_errors, local_warnings, requirement_count). Importable so
    export-compliance-pack.py validates with exactly this logic, never a
    second, drifting copy of the rules.

    strict=True additionally enforces the cross-field invariants that only
    matter at authoring/export time (every catalogue item covered, no
    duplicate requirement_id, effective_date required for
    ENACTED_FUTURE_COMMENCEMENT). Callers validating an already-exported pack
    file (which has no catalogue_items_covered manifest) should pass
    strict=False.
    """
    local_errors = []
    local_warnings = []

    if not os.path.exists(path):
        local_errors.append(f"File not found: {path}")
        return local_errors, local_warnings, 0

    try:
        data = json.load(open(path))
    except Exception as e:
        local_errors.append(f"Failed to parse {os.path.basename(path)}: {e}")
        return local_errors, local_warnings, 0

    requirements = data.get("requirements", [])
    if not requirements:
        local_errors.append(f"{os.path.basename(path)} has no requirements")
        return local_errors, local_warnings, 0

    seen_ids = set()
    covered_items = set()

    for r in requirements:
        rid = r.get("requirement_id", "<no id>")

        for f in REQUIRED_REQUIREMENT_FIELDS:
            if f not in r or r[f] in (None, "", []):
                local_errors.append(f"requirement '{rid}' missing required field '{f}'")

        if rid in seen_ids:
            local_errors.append(f"duplicate requirement_id '{rid}'")
        seen_ids.add(rid)

        status = r.get("status")
        if status not in VALID_STATUS:
            local_errors.append(f"requirement '{rid}' has invalid status '{status}'")

        if status == "ENACTED_FUTURE_COMMENCEMENT" and not r.get("effective_date"):
            local_errors.append(
                f"requirement '{rid}' has status ENACTED_FUTURE_COMMENCEMENT but no effective_date"
            )
        if r.get("effective_date"):
            validate_date(r["effective_date"], "effective_date", rid)

        evidence_method = r.get("evidence_method")
        if evidence_method not in VALID_EVIDENCE_METHOD:
            local_errors.append(
                f"requirement '{rid}' has invalid evidence_method '{evidence_method}'"
            )

        if r.get("severity") not in SEVERITIES:
            local_errors.append(f"requirement '{rid}' has invalid severity '{r.get('severity')}'")

        blocking_policy = r.get("release_blocking_policy")
        if blocking_policy not in VALID_BLOCKING_POLICY:
            local_errors.append(
                f"requirement '{rid}' has invalid release_blocking_policy '{blocking_policy}'"
            )
        # This field is descriptive metadata only. A requirement that is not
        # currently blocking-capable (PROPOSED_CONSULTATION, GUIDANCE_GOOD_PRACTICE,
        # or an ENACTED_FUTURE_COMMENCEMENT requirement before its own effective
        # date) asserting 'blocking_once_current_and_effective' is not itself an
        # error -- a consuming system must derive actual blocking behaviour from
        # status + effective_date + its own current date, never from this field
        # alone. See data/compliance-pack-schema.json's release_blocking_policy
        # description.

        legislation = r.get("legislation", {})
        if not isinstance(legislation, dict):
            local_errors.append(f"requirement '{rid}' has a non-object 'legislation' field")
        else:
            for f in REQUIRED_LEGISLATION_FIELDS:
                if not legislation.get(f):
                    local_errors.append(f"requirement '{rid}' legislation missing field '{f}'")
            src = legislation.get("source_url", "")
            if src and not (src.startswith("http://") or src.startswith("https://")):
                local_errors.append(f"requirement '{rid}' legislation.source_url is not a URL")

        evidence_requirements = r.get("evidence_requirements", [])
        if not isinstance(evidence_requirements, list) or not evidence_requirements:
            local_errors.append(f"requirement '{rid}' has no evidence_requirements")
        else:
            seen_evidence_ids = set()
            for ev in evidence_requirements:
                eid = ev.get("evidence_id", "<no id>")
                for f in REQUIRED_EVIDENCE_ITEM_FIELDS:
                    if not ev.get(f):
                        local_errors.append(
                            f"requirement '{rid}' evidence item '{eid}' missing field '{f}'"
                        )
                if eid in seen_evidence_ids:
                    local_errors.append(f"requirement '{rid}' has duplicate evidence_id '{eid}'")
                seen_evidence_ids.add(eid)
                if ev.get("method") not in VALID_EVIDENCE_ITEM_METHOD:
                    local_errors.append(
                        f"requirement '{rid}' evidence item '{eid}' has invalid method '{ev.get('method')}'"
                    )
                covered_items.update(ev.get("covers_catalogue_items", []))

            automated_count = sum(1 for e in evidence_requirements if e.get("method") == "AUTOMATED")
            owner_count = sum(1 for e in evidence_requirements if e.get("method") == "OWNER_EVIDENCE")
            if evidence_method == "AUTOMATED" and owner_count:
                local_errors.append(
                    f"requirement '{rid}' is classified AUTOMATED but has an OWNER_EVIDENCE evidence item"
                )
            if evidence_method == "OWNER_EVIDENCE" and automated_count:
                local_warnings.append(
                    f"requirement '{rid}' is classified OWNER_EVIDENCE but has an AUTOMATED evidence item; consider HYBRID"
                )
            if evidence_method == "HYBRID" and not (automated_count and owner_count):
                local_errors.append(
                    f"requirement '{rid}' is classified HYBRID but does not have both an AUTOMATED and an OWNER_EVIDENCE evidence item"
                )

        change_history = r.get("change_history", [])
        if not isinstance(change_history, list) or not change_history:
            local_errors.append(f"requirement '{rid}' has no change_history")

    if strict:
        declared_items = set(data.get("catalogue_items_covered", []))
        if declared_items:
            missing = declared_items - covered_items
            if missing:
                local_errors.append(
                    f"catalogue_items_covered lists items with no evidence_requirement coverage: {sorted(missing)}"
                )

    return local_errors, local_warnings, len(requirements)


def main():
    # 1. Validate rejection patterns
    if not os.path.exists(PATTERNS):
        errors.append(f"File not found: {PATTERNS}")
        return finish()

    try:
        data = json.load(open(PATTERNS))
    except Exception as e:
        errors.append(f"Failed to parse rejection-patterns.json: {e}")
        return finish()

    patterns = data.get("patterns", [])
    if not patterns:
        errors.append("rejection-patterns.json has no patterns")
    else:
        ids = set()
        for p in patterns:
            pid = p.get("id", "<no id>")
            for f in REQUIRED_PATTERN:
                if not p.get(f):
                    errors.append(f"{pid} missing required field {f}")
            if pid in ids:
                errors.append(f"duplicate pattern id {pid}")
            ids.add(pid)
            if p.get("severity") not in SEVERITIES:
                errors.append(f"{pid} has invalid severity {p.get('severity')}")
            if p.get("platform") not in PLATFORMS:
                errors.append(f"{pid} has invalid platform {p.get('platform')}")

    # 2. Validate recipes
    if os.path.exists(RECIPES):
        try:
            recipes = json.load(open(RECIPES)).get("recipes", {})
            for rid in recipes:
                if rid not in ids:
                    errors.append(
                        f"detection recipe '{rid}' has no matching pattern id, it will never surface"
                    )

            with_recipe = set(recipes.keys())
            for p in patterns:
                sig = p.get("signals")
                if sig and p["id"] not in with_recipe:
                    warnings.append(
                        f"{p['id']} has detection signals but no recipe command yet"
                    )
        except Exception as e:
            errors.append(f"Failed to parse detection-recipes.json: {e}")
    else:
        warnings.append("detection-recipes.json not found")

    # 3. Validate regulatory deadlines
    if not os.path.exists(DEADLINES):
        errors.append(f"File not found: {DEADLINES}")
    else:
        try:
            deadline_data = json.load(open(DEADLINES))
            deadlines = deadline_data.get("deadlines", [])
            if not deadlines:
                errors.append("regulatory-deadlines.json has no deadlines list")
            else:
                deadline_ids = set()
                for d in deadlines:
                    did = d.get("id", "<no id>")
                    if not did or did == "<no id>":
                        errors.append("deadline entry missing 'id' field")
                    elif did in deadline_ids:
                        errors.append(f"duplicate deadline id '{did}'")
                    deadline_ids.add(did)

                    for f in REQUIRED_DEADLINE:
                        if f not in d or d[f] is None:
                            errors.append(
                                f"deadline '{did}' missing required field '{f}'"
                            )

                    if d.get("priority") not in SEVERITIES:
                        errors.append(
                            f"deadline '{did}' has invalid priority '{d.get('priority')}'"
                        )

                    # Validate date formats
                    for date_field in [
                        "effective_date",
                        "mandatory_date",
                        "enforcement_date",
                    ]:
                        val = d.get(date_field)
                        if val and val != "none":
                            validate_date(val, date_field, did)
        except Exception as e:
            errors.append(f"Failed to parse regulatory-deadlines.json: {e}")

    # 4. Validate the Compliance Pack requirement catalogue
    comp_errors, comp_warnings, ncomp = validate_compliance_requirements()
    errors.extend(comp_errors)
    warnings.extend(comp_warnings)

    return finish(
        len(patterns),
        len(recipes) if "recipes" in locals() else 0,
        len(deadlines) if "deadlines" in locals() else 0,
        ncomp,
    )


def finish(npat=0, nrec=0, ndead=0, ncomp=0):
    for w in warnings:
        print(f"  warn. {w}")
    for e in errors:
        print(f"  ERROR. {e}")
    if errors:
        print(
            f"\nvalidate. FAILED with {len(errors)} error(s), {len(warnings)} warning(s)"
        )
        return 1
    print(
        f"validate. OK. {npat} patterns, {nrec} recipes, {ndead} deadlines, "
        f"{ncomp} compliance-pack requirements, {len(warnings)} warning(s), 0 errors"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

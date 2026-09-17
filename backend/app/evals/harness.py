"""Golden-email eval harness — score extraction against expected facts/gaps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from app.ai.gemini import HeuristicProvider
from app.ai.service import LLMService
from app.services.meeting_room import meeting_room_gaps

GOLDEN_PATH = Path(__file__).resolve().parents[2] / "evals" / "golden_meeting_room.json"


def load_golden_cases(path: Optional[Path] = None) -> list[dict[str, Any]]:
    p = path or GOLDEN_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    return list(data.get("cases") or data)


def _score_case(case: dict[str, Any], entities: dict[str, Any], gaps: list[dict[str, Any]]) -> dict[str, Any]:
    expect = case.get("expect") or {}
    expected_fields = expect.get("entities") or {}
    field_hits = 0
    field_total = 0
    mismatches: list[str] = []
    for key, want in expected_fields.items():
        field_total += 1
        got = entities.get(key)
        if want is None:
            if got in (None, "", []):
                field_hits += 1
            else:
                mismatches.append(f"{key}: expected empty got {got!r}")
        elif isinstance(want, str) and want.startswith("*"):
            needle = want[1:].lower()
            if needle in str(got or "").lower():
                field_hits += 1
            else:
                mismatches.append(f"{key}: expected contains {needle!r} got {got!r}")
        elif got == want:
            field_hits += 1
        else:
            mismatches.append(f"{key}: expected {want!r} got {got!r}")

    expected_missing = set(expect.get("missing_fields") or [])
    got_missing = {g["field"] for g in gaps}
    missing_ok = expected_missing <= got_missing if expected_missing else True
    # When expect says no_missing, gaps must be empty
    if expect.get("no_missing"):
        missing_ok = len(gaps) == 0
        if not missing_ok:
            mismatches.append(f"expected no gaps, got {sorted(got_missing)}")
    elif expected_missing and not missing_ok:
        mismatches.append(f"missing fields expected {sorted(expected_missing)} got {sorted(got_missing)}")

    ask_only = expect.get("ask_only_fields")
    ask_ok = True
    if ask_only is not None:
        ask_ok = got_missing <= set(ask_only)
        if not ask_ok:
            mismatches.append(f"extra gaps beyond {sorted(ask_only)}: {sorted(got_missing - set(ask_only))}")

    passed = field_hits == field_total and missing_ok and ask_ok and not mismatches
    return {
        "id": case.get("id"),
        "passed": passed,
        "field_score": field_hits / field_total if field_total else 1.0,
        "mismatches": mismatches,
        "gaps": sorted(got_missing),
        "path": entities.get("interpretation_path"),
    }


def run_eval(
    *,
    use_heuristic: bool = True,
    path: Optional[Path] = None,
) -> dict[str, Any]:
    """Run golden cases through LLMService (heuristic by default for CI)."""
    cases = load_golden_cases(path)
    provider = HeuristicProvider() if use_heuristic else None
    svc = LLMService(provider=provider) if provider else LLMService()
    results = []
    for case in cases:
        result = svc.extract(
            subject=case.get("subject") or "",
            body=case.get("body") or "",
            prior_facts=case.get("prior_facts") or {},
        )
        ents = dict(result.entities or {})
        gaps = meeting_room_gaps(ents)
        results.append(_score_case(case, ents, gaps))

    passed = sum(1 for r in results if r["passed"])
    return {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(passed / len(results), 3) if results else 0.0,
        "results": results,
    }

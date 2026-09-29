#!/usr/bin/env python3
"""Fail a required pytest suite when any case fails, errors, or skips."""

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def summarize(path: Path) -> tuple[int, int, int, int]:
    root = ET.parse(path).getroot()
    if root.tag not in {"testsuite", "testsuites"}:
        raise ValueError("expected a JUnit testsuite or testsuites root")
    cases = list(root.iter("testcase"))
    if not cases:
        raise ValueError("required suite contains no testcases")
    failed = sum(case.find("failure") is not None for case in cases)
    errors = sum(case.find("error") is not None for case in cases)
    skipped = sum(case.find("skipped") is not None for case in cases)
    passed = len(cases) - failed - errors - skipped
    return passed, failed, errors, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args()
    try:
        passed, failed, errors, skipped = summarize(args.junit)
    except (OSError, ET.ParseError, ValueError) as exc:
        print(f"invalid required-suite report: {exc}", file=sys.stderr)
        return 1
    print(f"passed={passed} failed={failed} errors={errors} skipped={skipped}")
    return 1 if failed or errors or skipped else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Require nonempty passing JUnit; optionally bind native Playwright or pytest discovery."""

import argparse
import importlib.util
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


def playwright_inventory(path: Path, expected_count: int, expected_files: list[str]):
    checker_path = Path(__file__).with_name("check-c61-evidence.py")
    spec = importlib.util.spec_from_file_location("required_discovery_checker", checker_path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    names = checker._built_playwright_names(path.read_bytes(), "ci-required")
    files = {name.split("::", 1)[0] for name in names}
    if expected_count <= 0 or len(names) != expected_count or files != set(expected_files):
        raise ValueError("empty, filtered or wrong required Playwright discovery")
    return names, checker


def pytest_inventory(path: Path, expected_count: int):
    checker_path = Path(__file__).with_name("check-c61-evidence.py")
    spec = importlib.util.spec_from_file_location("required_pytest_checker", checker_path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    names = checker._discovery(path.read_bytes(), "pytest")
    if expected_count <= 0 or len(names) != expected_count:
        raise ValueError("empty, filtered or wrong full pytest discovery")
    return names, checker


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path)
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--playwright-discovery", type=Path)
    sources.add_argument("--pytest-discovery", type=Path)
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--expected-file", action="append", default=[])
    parser.add_argument("--discovery-only", action="store_true")
    args = parser.parse_args()
    if args.playwright_discovery:
        if args.expected_count is None or args.expected_count <= 0 or not args.expected_file:
            parser.error("Playwright discovery requires a positive count and original spec files")
    elif args.pytest_discovery:
        if args.expected_count is None or args.expected_count <= 0 or args.expected_file:
            parser.error("pytest discovery requires a positive count and no Playwright spec files")
    elif args.discovery_only or args.expected_count is not None or args.expected_file:
        parser.error("discovery options require a native discovery source")
    if not args.discovery_only and not args.junit:
        parser.error("--junit is required for execution verification")
    if args.discovery_only and args.junit:
        parser.error("discovery-only cannot claim execution")
    try:
        if args.playwright_discovery:
            names, checker = playwright_inventory(args.playwright_discovery, args.expected_count, args.expected_file)
            print(f"discovered={len(names)}")
            if args.discovery_only:
                return 0
            if checker._junit(args.junit.read_bytes()) != names:
                raise ValueError("required Playwright discovery and JUnit names differ")
        if args.pytest_discovery:
            names, checker = pytest_inventory(args.pytest_discovery, args.expected_count)
            print(f"discovered={len(names)}")
            if args.discovery_only:
                return 0
            if args.junit.stat().st_mtime_ns < args.pytest_discovery.stat().st_mtime_ns:
                raise ValueError("required pytest JUnit predates native collection")
            if checker._junit(args.junit.read_bytes()) != names:
                raise ValueError("required pytest discovery and JUnit names differ")
        passed, failed, errors, skipped = summarize(args.junit)
    except (OSError, ET.ParseError, ValueError) as exc:
        print(f"invalid required-suite report: {exc}", file=sys.stderr)
        return 1
    print(f"passed={passed} failed={failed} errors={errors} skipped={skipped}")
    return 1 if failed or errors or skipped else 0


if __name__ == "__main__":
    raise SystemExit(main())

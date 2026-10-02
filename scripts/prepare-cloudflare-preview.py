"""Render an auditable temporary overlay; no deployment, credentials or resource changes.

Use only after actual isolated project/branch/hostname readback and specific
preview authorization. Apply these files to a git archive of source_sha, never
the user's checkout. The resulting preview is not the unchanged release RC.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DURATION_SECONDS = 61
ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = "scripts/cloudflare-preview/runtime_probe.py"


def render_overlay(root, target):
    config = json.loads((root / "vercel.json").read_text(encoding="utf-8"))
    api = config["services"]["api"]
    assert api["root"] == "services/api" and api["framework"] == "fastapi"
    assert api["entrypoint"] == "buyeros_api.api.vercel:app"
    api["entrypoint"] = "buyeros_api.api.preview_vercel:app"
    api["functions"] = {"buyeros_api/api/preview_vercel.py": {"maxDuration": 90}}
    route = (root / "app/v1/[...path]/route.ts").read_text(encoding="utf-8")
    needle = "const internalWorkerPaths = new Set(["
    assert route.count(needle) == 1, "gateway shape changed; review overlay before preparation"
    route = route.replace(needle, needle + "\n  '/v1/internal/runtime-probe',", 1)
    runtime = (root / TEMPLATE).read_text(encoding="utf-8") + (
        '\n# Vercel discovers the ASGI handler as a module-level assignment.\n'
        '# The guarded native-child entrypoint above exits before these lines.\n'
        'manifest = Path(__file__).with_name("preview_target.json")\n'
        'app = create_preview_app(json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {})\n'
    )
    return {"vercel.json": json.dumps(config, indent=2) + "\n",
            "app/v1/[...path]/route.ts": route,
            "services/api/buyeros_api/api/preview_vercel.py": runtime,
            "services/api/buyeros_api/api/preview_target.json": json.dumps(target, indent=2) + "\n"}


def prepare_overlay(target_path, output):
    target = json.loads(target_path.read_text(encoding="utf-8"))
    # Read the source-controlled guard without depending on the API environment.
    spec = importlib.util.spec_from_file_location("preview_overlay_guard", ROOT / TEMPLATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_target(target, datetime.now(timezone.utc))
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if target["source_sha"] != head:
        raise ValueError("overlay must use the exact current committed source SHA")
    for relative in (TEMPLATE, "scripts/prepare-cloudflare-preview.py", "vercel.json", "app/v1/[...path]/route.ts"):
        committed = subprocess.check_output(["git", "show", f"{head}:{relative}"], cwd=ROOT)
        # Windows checkout CRLF is normalized when rendering these UTF-8 files.
        # Compare their full text, retaining every substantive character.
        if committed.decode("utf-8") != (ROOT / relative).read_text(encoding="utf-8"):
            raise ValueError("commit and review the preview source before rendering")
    destination = output.resolve()
    parent = (ROOT / ".sites-runtime").resolve()
    if (parent.parent != ROOT.resolve() or destination.parent != parent
            or not destination.name.startswith("cf-preview-") or destination.exists()):
        raise ValueError("use a new owned .sites-runtime/cf-preview-* overlay directory")
    files = render_overlay(ROOT, target)
    destination.mkdir(parents=True)
    for relative, value in files.items():
        file = destination / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(value, encoding="utf-8", newline="\n")
    manifest = {"kind": "temporary_overlay_only", "source_sha": head,
                "expires_at": target["expires_at"], "hosted_verified": False,
                "files_sha256": {relative: hashlib.sha256((destination / relative).read_bytes()).hexdigest()
                                 for relative in files}}
    (destination / "overlay-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = prepare_overlay(args.target_json, args.output)
    except (ValueError, AssertionError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

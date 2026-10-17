"""Reviewed authority administration, default dry-run; never a permit importer.

The existing DB-owner operator verifies designation and approval evidence through
the approved secure process. Matching hashes here proves binding, not consent.
No client API or application runtime role can use this authority write path.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--target-contract", type=Path, required=True)
    parser.add_argument("--mode", choices=("dry-run", "apply", "revoke", "reconcile"), default="dry-run")
    parser.add_argument("--reason")
    args = parser.parse_args()
    dsn = os.environ.get("BUYEROS_DATABASE_MIGRATION_URL")
    if not dsn:
        print(json.dumps({"code": "MIGRATION_URL_REQUIRED", "mode": args.mode}))
        return 2

    from pydantic import Field
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool
    from buyeros_api.api.errors import ApiError
    from buyeros_api.api.policy_activation_schemas import ActivationStrict
    from buyeros_api.db.session import tenant_session
    from buyeros_api.services import policy_activation_bootstrap as service
    from buyeros_api.services.release_binding import database_target_sha256

    class TargetContract(ActivationStrict):
        target_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
        source_sha: str = Field(pattern=r"^[0-9a-f]{40}$")

    manifest_hash = None
    write_started = False
    try:
        # No fallback to application database settings, no pooled owner session.
        url = make_url(dsn)
        if (url.get_backend_name() != "postgresql" or not url.host or not url.database
            or "-pooler" in url.host or url.username in {"buyeros_api", "buyeros_worker"}):
            raise ValueError("explicit direct migration-owner binding required")
        manifest = service.AuthorityManifest.model_validate_json(args.manifest.read_text(encoding="utf-8-sig"))
        authorization = service.BootstrapAuthorization.model_validate_json(args.authorization.read_text(encoding="utf-8-sig"))
        target = TargetContract.model_validate_json(args.target_contract.read_text(encoding="utf-8-sig"))
        manifest_hash = service.manifest_digest(manifest)
        if (database_target_sha256(url) != target.target_sha256
            or manifest.target_sha256 != target.target_sha256 or manifest.source_sha != target.source_sha):
            raise ValueError("reviewed target/source receipt mismatch")

        async def execute():
            nonlocal write_started
            engine = create_async_engine(url.set(drivername="postgresql+psycopg"), poolclass=NullPool)
            try:
                async with tenant_session(engine, manifest.workspace_id) as session:
                    verified = await service.verify_bootstrap_execution(session, manifest, authorization)
                    now = datetime.now(timezone.utc)
                    if args.mode == "dry-run":
                        result = await service.inspect_authority_manifest(session, manifest, now)
                    elif args.mode == "reconcile":
                        result = await service.reconcile_authority_manifest(session, manifest_hash,
                                                                           workspace_id=manifest.workspace_id)
                    elif args.mode == "apply":
                        write_started = True
                        result = await service.apply_authority_manifest(session, manifest, verified, now)
                    else:
                        if not args.reason:
                            raise ValueError("reviewed revocation reason required")
                        write_started = True
                        result = await service.revoke_authority(
                            session, manifest.expected_authority_id, manifest.expected_authority_version,
                            args.reason, verified, now)
                return result
            finally:
                await engine.dispose()

        if sys.platform == "win32":
            with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
                result = runner.run(execute())
        else:
            result = asyncio.run(execute())
        # Only bounded IDs, hashes, state and non-secret execution metadata.
        print(json.dumps({"mode": args.mode, "manifest_sha256": manifest_hash, "result": result}, default=str))
        return 0
    except (ValueError, OSError, ApiError) as error:
        if write_started and not isinstance(error, ApiError):
            print(json.dumps({"mode": args.mode, "code": "BOOTSTRAP_OUTCOME_UNCONFIRMED",
                              "unknown_outcome": True, "manifest_sha256": manifest_hash}))
            return 3
        print(json.dumps({"mode": args.mode, "code": error.code if isinstance(error, ApiError) else "INVALID_BOOTSTRAP_INPUT",
                          "manifest_sha256": manifest_hash}))
        return 2
    except Exception:
        # A lost commit response is not a fresh authorization to replay a write.
        # Preserve the exact manifest hash and reconcile before any further call.
        print(json.dumps({"mode": args.mode, "code": "BOOTSTRAP_OUTCOME_UNCONFIRMED",
                          "unknown_outcome": args.mode in {"apply", "revoke"},
                          "manifest_sha256": manifest_hash}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

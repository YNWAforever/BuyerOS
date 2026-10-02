"""Reviewed operator compare-and-swap; previews a change unless --apply is explicit."""
import argparse
import json
import os

from buyeros_api.services.worker_recovery import set_execution_runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-epoch', required=True, type=int)
    parser.add_argument('--backend', required=True, choices=['cloudflare', 'celery'])
    parser.add_argument('--enabled', required=True, choices=['true', 'false'])
    parser.add_argument('--reason', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    dsn = os.environ.get('BUYEROS_RUNTIME_ADMIN_DATABASE_URL')
    if not dsn:
        parser.error('explicit operator database connection is required; runtime connections cannot activate')
    result = set_execution_runtime(dsn, expected_epoch=args.expected_epoch, backend=args.backend,
                                   enabled=args.enabled == 'true', reason=args.reason, apply=args.apply)
    print(json.dumps(result, sort_keys=True))  # no connection, credentials or customer identifiers


if __name__ == '__main__':
    main()

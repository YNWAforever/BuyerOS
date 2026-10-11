"""Unique local fixture reports; historical/dirty evidence is never a write target."""
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4

def fresh_report_path(historical:Path)->Path:
    parent=historical.parent/'fixture-runs'
    parent.mkdir(parents=True,exist_ok=True)
    # Atomic unique directory also protects subprocess writers that open files themselves.
    while True:
        run=parent/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid4().hex)
        try:
            run.mkdir()
        except FileExistsError:
            continue
        return run/historical.name

"""Real child-process import behavior for vendor-installed hosted dependencies."""
import hashlib
import subprocess

from buyeros_api.execution import pdf_parser
from buyeros_api.services.ingestion_service import validate_upload
from tools.probe_worker_runtime import sample_pdf


def test_pdf_child_uses_vendor_dependencies_without_inheriting_credentials(monkeypatch, tmp_path):
    # -S removes the interpreter's automatic site initialization, reproducing
    # the host's packages being present only in the API process's import path.
    original = subprocess.run
    observed = []
    malicious = tmp_path / "untrusted"
    malicious.mkdir()
    (malicious / "pypdf.py").write_text("raise RuntimeError('untrusted inherited import path')\n")
    monkeypatch.setenv("PYTHONPATH", str(malicious))
    monkeypatch.setenv("BUYEROS_PROVIDER_SECRET", "fictional-secret-must-not-reach-child")
    def isolated(command, **kwargs):
        observed.append(kwargs["env"])
        assert kwargs["timeout"] == 8
        return original([command[0], "-S", *command[1:]], **kwargs)
    monkeypatch.setattr(pdf_parser.subprocess, "run", isolated)
    body = sample_pdf()
    upload = validate_upload("fictional.pdf", "application/pdf", body, hashlib.sha256(body).hexdigest())
    rows = pdf_parser.parse_pdf_candidates(upload)
    assert [(row["field"], row["value"], row["approved"]) for row in rows] == [("product", "Sensor", False)]
    assert "BUYEROS_PROVIDER_SECRET" not in observed[0]
    assert str(malicious) not in observed[0].get("PYTHONPATH", "")
    assert set(observed[0]) <= {"PYTHONIOENCODING", "PYTHONDONTWRITEBYTECODE", "PYTHONPATH", "SystemRoot"}

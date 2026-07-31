import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.models import SourceType  # noqa: E402
from backend.mitre_stix_loader import load_mitre_stix_chunks  # noqa: E402
from backend.sigma_bulk_loader import load_sigma_bulk_chunks  # noqa: E402
from backend.nist_pdf_loader import load_nist_pdf_chunks  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def test_mitre_stix_loader_filters_revoked_and_deprecated():
    chunks = load_mitre_stix_chunks(FIXTURES / "mini_enterprise_attack.json")
    ids = [c.metadata["technique_id"] for c in chunks]
    assert "T1059.001" in ids
    assert "T1000" not in ids  # revoked technique must be filtered out


def test_mitre_stix_loader_links_mitigations():
    chunks = load_mitre_stix_chunks(FIXTURES / "mini_enterprise_attack.json")
    technique = next(c for c in chunks if c.metadata["technique_id"] == "T1059.001")
    assert "Disable or restrict PowerShell" in technique.text


def test_mitre_stix_loader_missing_file_returns_empty():
    chunks = load_mitre_stix_chunks(FIXTURES / "does_not_exist.json")
    assert chunks == []


def test_sigma_bulk_loader_recurses_nested_dirs():
    chunks = load_sigma_bulk_chunks(FIXTURES / "sigma_repo")
    names = [c.source_name for c in chunks]
    assert "Suspicious PowerShell Encoded Command (Real Repo Sample)" in names
    assert "Suspicious LSASS Access (Real Repo Sample)" in names
    assert "DNS Beaconing Pattern (Real Repo Sample)" in names


def test_sigma_bulk_loader_skips_deprecated_rules():
    chunks = load_sigma_bulk_chunks(FIXTURES / "sigma_repo")
    names = [c.source_name for c in chunks]
    assert "Deprecated Old Rule" not in names


def test_sigma_bulk_loader_extracts_mitre_technique_from_tags():
    chunks = load_sigma_bulk_chunks(FIXTURES / "sigma_repo")
    powershell_rule = next(c for c in chunks if "PowerShell" in c.source_name)
    assert powershell_rule.metadata["mitre_technique"] == "T1059.001"


def test_nist_pdf_loader_extracts_and_chunks():
    chunks = load_nist_pdf_chunks(FIXTURES / "sample_nist_800-61_v2.pdf")
    assert len(chunks) > 0
    for c in chunks:
        assert c.source_type == SourceType.NIST
        assert "section" in c.metadata


def test_nist_pdf_loader_carries_heading_across_pages():
    chunks = load_nist_pdf_chunks(FIXTURES / "sample_nist_800-61_v2.pdf")
    # Page 3 has no heading of its own; it must inherit the page-2 heading.
    page3_chunk = next(c for c in chunks if c.metadata["page"] == 3)
    assert page3_chunk.metadata["section"] == "3.2 Detection and Analysis"


def test_nist_pdf_loader_missing_file_returns_empty():
    chunks = load_nist_pdf_chunks(FIXTURES / "does_not_exist.pdf")
    assert chunks == []

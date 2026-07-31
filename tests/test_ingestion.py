import json
import sys
import tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.ingestion import (  # noqa: E402
    _find_stix_bundle,
    load_all_chunks,
    load_mitre_chunks,
    load_nist_chunks,
    load_playbook_chunks,
    load_sigma_chunks,
)
from backend.models import SourceType  # noqa: E402


def test_load_mitre_chunks_returns_valid_chunks():
    chunks = load_mitre_chunks()
    assert len(chunks) > 0
    for c in chunks:
        assert c.source_type == SourceType.MITRE
        assert "technique_id" in c.metadata
        assert c.text.strip() != ""


def test_load_sigma_chunks_returns_valid_chunks():
    chunks = load_sigma_chunks()
    assert len(chunks) > 0
    for c in chunks:
        assert c.source_type == SourceType.SIGMA
        assert c.text.strip() != ""


def test_load_nist_chunks_respects_chunking():
    chunks = load_nist_chunks()
    assert len(chunks) > 0
    for c in chunks:
        assert c.source_type == SourceType.NIST
        # chunk char size should stay within a reasonable bound of the token target
        assert len(c.text) < 4000


def test_load_playbook_chunks_returns_valid_chunks():
    chunks = load_playbook_chunks()
    assert len(chunks) > 0
    for c in chunks:
        assert c.source_type == SourceType.PLAYBOOK


def test_chunk_ids_are_unique():
    all_chunks = load_mitre_chunks() + load_sigma_chunks() + load_nist_chunks() + load_playbook_chunks()
    ids = [c.chunk_id for c in all_chunks]
    assert len(ids) == len(set(ids)), "Duplicate chunk IDs detected"


# --- Regression tests for a STIX bundle being mistaken for sample-format JSON ---
# (reported crash: "TypeError: string indices must be integers, not 'str'"
# when a downloaded MITRE STIX bundle landed in knowledge/mitre/ under a
# filename other than exactly "enterprise-attack.json")

def _write_stix_bundle(directory: Path, filename: str) -> Path:
    bundle = {
        "type": "bundle",
        "id": "bundle--test",
        "spec_version": "2.0",
        "objects": [
            {
                "type": "attack-pattern",
                "id": "attack-pattern--test",
                "name": "Test Technique",
                "description": "A test technique.",
                "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": "execution"}],
                "external_references": [{"source_name": "mitre-attack", "external_id": "T9999"}],
                "revoked": False,
            }
        ],
    }
    path = directory / filename
    path.write_text(json.dumps(bundle), encoding="utf-8")
    return path


def test_load_mitre_chunks_does_not_crash_on_stix_bundle():
    """A STIX bundle (dict-shaped) must never crash the sample loader, even
    if it ends up in the sample directory under an unexpected filename."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_stix_bundle(tmp_path, "enterprise-attack (1).json")
        # Directly exercise the sample loader's parsing logic on this directory
        import backend.ingestion as ingestion_mod

        original_dir = ingestion_mod.settings.mitre_dir
        try:
            ingestion_mod.settings.mitre_dir = tmp_path
            chunks = load_mitre_chunks()
            assert chunks == []  # must skip gracefully, not raise
        finally:
            ingestion_mod.settings.mitre_dir = original_dir


def test_find_stix_bundle_detects_renamed_file():
    """A STIX bundle saved under a non-standard filename (e.g. a browser
    download saved as 'enterprise-attack (1).json') must still be detected
    by content, not just by exact filename match."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        expected = _write_stix_bundle(tmp_path, "enterprise-attack (1).json")
        found = _find_stix_bundle(tmp_path)
        assert found == expected


def test_find_stix_bundle_returns_none_when_absent():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "unrelated.json").write_text('{"foo": "bar"}', encoding="utf-8")
        assert _find_stix_bundle(tmp_path) is None


def test_load_all_chunks_uses_stix_loader_for_renamed_bundle():
    """End-to-end: load_all_chunks() must route a renamed STIX bundle to the
    STIX loader instead of crashing in the sample loader."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mitre_dir = tmp_path / "mitre"
        sigma_dir = tmp_path / "sigma"
        nist_dir = tmp_path / "nist"
        playbooks_dir = tmp_path / "playbooks"
        for d in (mitre_dir, sigma_dir, nist_dir, playbooks_dir):
            d.mkdir()
        _write_stix_bundle(mitre_dir, "enterprise-attack (1).json")

        import backend.ingestion as ingestion_mod

        original = (
            ingestion_mod.settings.mitre_dir,
            ingestion_mod.settings.sigma_dir,
            ingestion_mod.settings.nist_dir,
            ingestion_mod.settings.playbooks_dir,
        )
        try:
            ingestion_mod.settings.mitre_dir = mitre_dir
            ingestion_mod.settings.sigma_dir = sigma_dir
            ingestion_mod.settings.nist_dir = nist_dir
            ingestion_mod.settings.playbooks_dir = playbooks_dir
            chunks = load_all_chunks()  # must not raise
            mitre_chunks = [c for c in chunks if c.source_type == SourceType.MITRE]
            assert len(mitre_chunks) == 1
            assert mitre_chunks[0].metadata["technique_id"] == "T9999"
        finally:
            (
                ingestion_mod.settings.mitre_dir,
                ingestion_mod.settings.sigma_dir,
                ingestion_mod.settings.nist_dir,
                ingestion_mod.settings.playbooks_dir,
            ) = original

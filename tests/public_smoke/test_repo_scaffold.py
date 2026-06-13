from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_public_source_roots_are_explicit() -> None:
    assert (ROOT / "config-templates" / "etc" / "abyss-machine").is_dir()
    assert (ROOT / "systemd" / "system").is_dir()
    assert (ROOT / "systemd" / "user").is_dir()
    assert not (ROOT / "templates").exists()


def test_mechanic_packages_have_route_contracts() -> None:
    expected = {
        "host-lifecycle",
        "config-projection",
        "host-facts",
        "storage-routing",
        "typing-intake",
        "nervous-local",
        "local-ai-runtime",
        "diagnostic-spine",
    }
    packages = {path.name for path in (ROOT / "mechanics").iterdir() if path.is_dir()}
    assert expected <= packages
    for package in expected:
        package_root = ROOT / "mechanics" / package
        for name in ["AGENTS.md", "README.md", "DIRECTION.md", "PROVENANCE.md", "PARTS.md", "ROADMAP.md", "LANDING_LOG.md"]:
            assert (package_root / name).is_file()
        assert (package_root / "docs" / "README.md").is_file()
        assert (package_root / "parts" / "README.md").is_file()


def test_public_boundary_moved_under_docs_publication() -> None:
    assert (ROOT / "docs" / "publication" / "PUBLICATION_BOUNDARY.md").is_file()
    assert not (ROOT / "docs" / "PUBLICATION_BOUNDARY.md").exists()

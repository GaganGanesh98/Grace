"""Sanity checks for repository-root env resolution (Phase 2.3)."""

from axiom.config import REPO_ROOT


def test_repo_root_contains_readme() -> None:
    assert (REPO_ROOT / "README.md").is_file()


def test_repo_root_contains_backend_package() -> None:
    assert (REPO_ROOT / "apps" / "backend" / "pyproject.toml").is_file()

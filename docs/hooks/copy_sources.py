"""MkDocs hook: copy the tutorial notebooks and the changelog into docs/.

The notebooks in notebooks/ and CHANGELOG.md at the repository root remain the single source;
the copies written here (docs/tutorials/notebooks/, docs/changelog.md) are gitignored and are
refreshed before every build or `mkdocs serve` reload.

The copy is an in-place sync: a file is written only when its content changed, and only
notebooks that no longer exist in notebooks/ are removed. This keeps `mkdocs serve` (which
watches docs/) from re-triggering itself, and avoids a delete/recreate race when two builds
run at once.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


def _sync(src: Path, dst: Path) -> None:
    data = src.read_bytes()
    if not dst.exists() or dst.read_bytes() != data:
        dst.write_bytes(data)


def on_pre_build(config, **kwargs):  # noqa: ARG001 (MkDocs hook signature)
    src_nb = ROOT / "notebooks"
    dst_nb = DOCS / "tutorials" / "notebooks"
    dst_nb.mkdir(parents=True, exist_ok=True)
    sources = {nb.name: nb for nb in src_nb.glob("*.ipynb")}
    for name, nb in sources.items():
        _sync(nb, dst_nb / name)
    for stale in dst_nb.glob("*.ipynb"):
        if stale.name not in sources:
            stale.unlink(missing_ok=True)
    # Figures are embedded in the executed notebooks (image/png outputs), so notebooks/figures/
    # does not need to be copied.

    changelog = ROOT / "CHANGELOG.md"
    if changelog.exists():
        _sync(changelog, DOCS / "changelog.md")

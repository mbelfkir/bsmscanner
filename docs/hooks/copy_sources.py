"""MkDocs hook: copy the tutorial notebooks and the changelog into docs/.

The notebooks in notebooks/ and CHANGELOG.md at the repository root remain the single source;
the copies written here (docs/tutorials/notebooks/, docs/changelog.md) are gitignored and are
refreshed before every build or `mkdocs serve` reload.
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


def on_pre_build(config, **kwargs):  # noqa: ARG001 (MkDocs hook signature)
    src_nb = ROOT / "notebooks"
    dst_nb = DOCS / "tutorials" / "notebooks"
    if dst_nb.exists():
        shutil.rmtree(dst_nb)
    dst_nb.mkdir(parents=True)
    for nb in sorted(src_nb.glob("*.ipynb")):
        shutil.copy2(nb, dst_nb / nb.name)
    # Figures are embedded in the executed notebooks (image/png outputs), so notebooks/figures/
    # does not need to be copied.

    changelog = ROOT / "CHANGELOG.md"
    if changelog.exists():
        (DOCS / "changelog.md").write_text(changelog.read_text(encoding="utf-8"), encoding="utf-8")

"""Access to the framework-owned reusable YAML library.

BSMScanner ships a set of model-independent building blocks (physics constants,
neutrino/PMNS observables, quark/CKM observables, modular forms, ...). When the
package is installed from a wheel these live inside the installed package at
``bsm_scanner/library/core``; when running from a source checkout they live at
the repository-root ``core/`` directory.

User models refer to them with the ``core:`` prefix, which is location
independent::

    imports:
      - core:constants/physics_constants.yaml
      - core:neutrino/observables_common.yaml
      - my_parameters.yaml

This lets a model written anywhere on disk -- outside the repository, in a user's
own project -- use the shipped blocks without guessing a relative path.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from bsm_scanner.exceptions import ModelValidationError

#: Prefix used inside model YAML to reference a shipped library block.
LIBRARY_PREFIX = "core:"

#: Environment variable allowing an explicit override of the library location.
LIBRARY_ENV_VAR = "BSM_SCANNER_CORE_LIBRARY"


@lru_cache(maxsize=1)
def core_library_path() -> Path:
    """Return the directory holding the shipped ``core/`` YAML library.

    Resolution order:

    1. the ``BSM_SCANNER_CORE_LIBRARY`` environment variable, if set;
    2. the installed package data at ``bsm_scanner/library/core``;
    3. the repository-root ``core/`` directory, when running from a checkout.
    """
    override = os.environ.get(LIBRARY_ENV_VAR)
    if override:
        candidate = Path(override).expanduser().resolve()
        if not candidate.is_dir():
            raise ModelValidationError(
                f"{LIBRARY_ENV_VAR} points to '{candidate}', which is not a directory."
            )
        return candidate

    installed = Path(__file__).resolve().parent / "library" / "core"
    if installed.is_dir():
        return installed

    # Source checkout: python/bsm_scanner/library.py -> repo root -> core/
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "core"
        if (candidate / "constants").is_dir() or (candidate / "neutrino").is_dir():
            return candidate

    raise ModelValidationError(
        "Could not locate the BSMScanner core YAML library. Reinstall the package, "
        f"or set {LIBRARY_ENV_VAR} to the directory containing the core blocks."
    )


def is_library_reference(reference: str) -> bool:
    """True if ``reference`` uses the ``core:`` library prefix."""
    return isinstance(reference, str) and reference.startswith(LIBRARY_PREFIX)


def resolve_library_reference(reference: str) -> Path:
    """Resolve ``core:<relative/path.yaml>`` to a concrete path.

    Raises ``ModelValidationError`` with the available blocks listed when the
    requested block does not exist, and refuses paths that escape the library.
    """
    if not is_library_reference(reference):
        raise ModelValidationError(
            f"'{reference}' is not a core library reference (expected a '{LIBRARY_PREFIX}' prefix)."
        )

    relative = reference[len(LIBRARY_PREFIX):].lstrip("/")
    if not relative:
        raise ModelValidationError(
            f"Empty core library reference '{reference}'. Use e.g. "
            "'core:neutrino/observables_common.yaml'."
        )

    root = core_library_path()
    resolved = (root / relative).resolve()

    try:
        resolved.relative_to(root)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ModelValidationError(
            f"Core library reference '{reference}' escapes the library directory."
        ) from exc

    if not resolved.exists():
        available = "\n  ".join(list_core_blocks())
        raise ModelValidationError(
            f"Core library block '{relative}' does not exist under '{root}'.\n"
            f"Available blocks:\n  {available}"
        )
    return resolved


def list_core_blocks() -> list[str]:
    """Return every shipped library block, as ``core:``-prefixed references."""
    root = core_library_path()
    blocks = [
        f"{LIBRARY_PREFIX}{path.relative_to(root).as_posix()}"
        for path in sorted(root.rglob("*.yaml"))
    ]
    return blocks


def describe_core_block(reference: str) -> dict[str, list[str]]:
    """Summarize what a shipped block defines, as ``{section: [names...]}``.

    Intended for discovery: it lets a user see which functions, constants and
    observables a block would contribute before importing it.
    """
    import yaml

    if not is_library_reference(reference):
        reference = f"{LIBRARY_PREFIX}{reference}"
    path = resolve_library_reference(reference)

    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    summary: dict[str, list[str]] = {}
    for section, block in raw.items():
        if section in ("imports", "includes"):
            summary[section] = list(block) if isinstance(block, list) else [str(block)]
            continue
        names: list[str] = []
        if isinstance(block, list):
            names = [str(e.get("name")) for e in block if isinstance(e, dict) and "name" in e]
        elif isinstance(block, dict):
            names = [str(k) for k in block]
        if names:
            summary[section] = names
    return summary

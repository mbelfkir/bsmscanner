from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

import yaml

from bsm_scanner.exceptions import ModelValidationError
from bsm_scanner.library import is_library_reference, resolve_library_reference


IMPORT_KEYS = ("imports", "includes")
NAMED_LIST_SECTIONS = {
    "parameters",
    "constants",
    "functions",
    "derived_scalars",
    "derived_complex",
    "matrices",
    "diagonalizations",
    "mixing_matrices",
    "observables",
    "theory_checks",
    "likelihoods",
}


class ModelFragmentLoader:
    def __init__(self) -> None:
        self._named_entry_origins: dict[tuple[str, str], Path] = {}
        self._output_entry_origins: dict[str, Path] = {}
        self._leaf_origins: dict[tuple[str, ...], Path] = {}

    def load(self, path: str | Path) -> dict[str, Any]:
        root = Path(path).resolve()
        merged: dict[str, Any] = {}
        self._merge_fragment_into(merged, root, ())
        return merged

    def _merge_fragment_into(
        self,
        target: dict[str, Any],
        path: Path,
        stack: tuple[Path, ...],
    ) -> None:
        if path in stack:
            cycle = " -> ".join(str(item) for item in (*stack, path))
            raise ModelValidationError(f"Include cycle detected while loading model fragments: {cycle}")
        if not path.exists():
            raise FileNotFoundError(f"Model fragment '{path}' does not exist.")

        with path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)

        if raw is None:
            raw = {}
        if not isinstance(raw, Mapping):
            raise ModelValidationError(
                f"Model fragment '{path}' must contain a mapping at the top level."
            )

        imports = self._extract_imports(raw, path)
        for import_name in imports:
            if is_library_reference(import_name):
                child_path = resolve_library_reference(import_name)
            else:
                child_path = (path.parent / import_name).resolve()
            self._merge_fragment_into(target, child_path, (*stack, path))

        local = {key: value for key, value in raw.items() if key not in IMPORT_KEYS}
        local = self._resolve_external_assets(local, path.parent)
        self._merge_mapping(target, local, path, ())

    def _extract_imports(self, raw: Mapping[str, Any], path: Path) -> list[str]:
        values = [raw[key] for key in IMPORT_KEYS if key in raw]
        if not values:
            return []
        if len(values) > 1:
            raise ModelValidationError(
                f"Model fragment '{path}' may specify only one of 'imports' or 'includes'."
            )
        imports = values[0]
        if isinstance(imports, str):
            return [imports]
        if isinstance(imports, list) and all(isinstance(item, str) for item in imports):
            return imports
        raise ModelValidationError(
            f"Model fragment '{path}' requires 'imports' to be a string or a list of strings."
        )

    def _merge_mapping(
        self,
        target: dict[str, Any],
        source: Mapping[str, Any],
        source_path: Path,
        key_path: tuple[str, ...],
    ) -> None:
        for key, incoming_value in source.items():
            current_path = (*key_path, key)
            if key in NAMED_LIST_SECTIONS and len(current_path) == 1:
                self._merge_named_list_section(target, key, incoming_value, source_path)
                continue

            if key not in target:
                target[key] = copy.deepcopy(incoming_value)
                self._register_new_value(current_path, incoming_value, source_path)
                continue

            existing_value = target[key]
            if isinstance(existing_value, Mapping) and isinstance(incoming_value, Mapping):
                self._merge_mapping(existing_value, incoming_value, source_path, current_path)
                continue

            if isinstance(existing_value, list) and isinstance(incoming_value, list):
                self._merge_list_value(existing_value, incoming_value, current_path, source_path)
                continue

            if existing_value == incoming_value:
                continue

            previous_path = self._leaf_origins.get(current_path)
            previous_label = str(previous_path) if previous_path is not None else "a previously imported fragment"
            raise ModelValidationError(
                f"Conflicting values for '{'.'.join(current_path)}' between '{previous_label}' "
                f"and '{source_path}'."
            )

    def _merge_named_list_section(
        self,
        target: dict[str, Any],
        section: str,
        incoming_value: Any,
        source_path: Path,
    ) -> None:
        if isinstance(incoming_value, Mapping):
            normalized = []
            for name, payload in incoming_value.items():
                if not isinstance(payload, Mapping):
                    raise ModelValidationError(
                        f"Section '{section}' entry '{name}' in '{source_path}' must be a mapping."
                    )
                normalized.append({"name": str(name), **dict(payload)})
            incoming_value = normalized

        if not isinstance(incoming_value, list):
            raise ModelValidationError(
                f"Section '{section}' in '{source_path}' must be a list or mapping of named entries."
            )

        destination = target.setdefault(section, [])
        if not isinstance(destination, list):
            raise ModelValidationError(
                f"Section '{section}' was previously defined as a non-list value."
            )

        for index, item in enumerate(incoming_value):
            if not isinstance(item, Mapping):
                raise ModelValidationError(
                    f"Section '{section}' entry {index} in '{source_path}' must be a mapping."
                )
            name = item.get("name")
            if not isinstance(name, str) or not name:
                raise ModelValidationError(
                    f"Section '{section}' entry {index} in '{source_path}' requires a non-empty 'name'."
                )
            entry_key = (section, name)
            if entry_key in self._named_entry_origins:
                previous_path = self._named_entry_origins[entry_key]
                raise ModelValidationError(
                    f"Duplicate entry '{name}' in section '{section}' from '{source_path}'. "
                    f"It was already defined in '{previous_path}'."
                )
            destination.append(copy.deepcopy(item))
            self._named_entry_origins[entry_key] = source_path

    def _merge_list_value(
        self,
        destination: list[Any],
        incoming_value: list[Any],
        key_path: tuple[str, ...],
        source_path: Path,
    ) -> None:
        if key_path == ("outputs", "save"):
            for item in incoming_value:
                if not isinstance(item, str):
                    raise ModelValidationError(
                        f"Section 'outputs.save' in '{source_path}' must contain only strings."
                    )
                if item in self._output_entry_origins:
                    previous_path = self._output_entry_origins[item]
                    raise ModelValidationError(
                        f"Duplicate output '{item}' from '{source_path}'. "
                        f"It was already defined in '{previous_path}'."
                    )
                destination.append(item)
                self._output_entry_origins[item] = source_path
            return

        destination.extend(copy.deepcopy(incoming_value))

    def _register_new_value(
        self,
        key_path: tuple[str, ...],
        value: Any,
        source_path: Path,
    ) -> None:
        if len(key_path) == 1 and key_path[0] in NAMED_LIST_SECTIONS:
            self._merge_named_list_section({}, key_path[0], value, source_path)
            return

        if key_path == ("outputs",):
            if not isinstance(value, Mapping):
                raise ModelValidationError(f"Section 'outputs' in '{source_path}' must be a mapping.")
            save = value.get("save", [])
            if save:
                if not isinstance(save, list):
                    raise ModelValidationError(
                        f"Section 'outputs.save' in '{source_path}' must be a list of strings."
                    )
                self._merge_list_value([], save, ("outputs", "save"), source_path)

        if isinstance(value, Mapping):
            for child_key, child_value in value.items():
                self._register_new_value((*key_path, str(child_key)), child_value, source_path)
            return

        if isinstance(value, list):
            return

        self._leaf_origins[key_path] = source_path

    def _resolve_external_assets(self, raw: Mapping[str, Any], base_dir: Path) -> dict[str, Any]:
        return _resolve_external_assets_in_value(dict(raw), base_dir)


def load_model_mapping(path: str | Path) -> dict[str, Any]:
    return ModelFragmentLoader().load(path)


def _load_two_column_table(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = stripped.replace(",", " ").split()
        if len(fields) < 2:
            raise ValueError(
                f"Expected at least two numeric columns in '{path}' on line {line_number}."
            )
        rows.append([float(fields[0]), float(fields[1])])
    if not rows:
        raise ValueError(f"Lookup table '{path}' is empty.")
    return rows


def _resolve_external_assets_in_value(value: Any, base_dir: Path) -> Any:
    if isinstance(value, list):
        return [_resolve_external_assets_in_value(item, base_dir) for item in value]
    if not isinstance(value, Mapping):
        return value

    resolved = {key: _resolve_external_assets_in_value(item, base_dir) for key, item in value.items()}

    table_file = resolved.get("table_file")
    if isinstance(table_file, str):
        if is_library_reference(table_file):
            table_path = resolve_library_reference(table_file)
        else:
            table_path = (base_dir / table_file).resolve()
            if not table_path.exists():
                raise FileNotFoundError(
                    f"Table file '{table_file}' was not found relative to '{base_dir}'."
                )
        resolved["table"] = _load_two_column_table(table_path)

    plugin_call = resolved.get("plugin_call")
    if isinstance(plugin_call, Mapping):
        options = plugin_call.get("options")
        if isinstance(options, Mapping):
            resolved_options = dict(options)
            for key, option_value in options.items():
                if (
                    isinstance(key, str)
                    and isinstance(option_value, str)
                    and (key.endswith("_file") or key.endswith("_path"))
                ):
                    if is_library_reference(option_value):
                        resolved_options[key] = str(resolve_library_reference(option_value))
                    else:
                        resolved_options[key] = str((base_dir / option_value).resolve())
            plugin_call = dict(plugin_call)
            plugin_call["options"] = resolved_options
            resolved["plugin_call"] = plugin_call

    return resolved

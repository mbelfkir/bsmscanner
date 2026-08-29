from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from math import exp, isfinite, sqrt
from pathlib import Path
from typing import Any

from bsm_scanner.model.schema import StatisticsSpec

_NOT_IMPLEMENTED_METHODS = {"de_mcmc", "profile_likelihood", "nested_sampling"}


@dataclass(slots=True)
class StatisticsArtifacts:
    directory: Path
    samples_path: Path | None
    summary_path: Path
    credible_intervals_path: Path
    diagnostics_path: Path


def weighted_quantile(values: list[float], weights: list[float], quantile: float) -> float:
    if not values or not weights or len(values) != len(weights):
        raise ValueError("weighted_quantile requires equally sized non-empty values and weights.")
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("weighted_quantile requires 0 <= quantile <= 1.")

    pairs = sorted((float(value), float(weight)) for value, weight in zip(values, weights, strict=True))
    total_weight = sum(weight for _, weight in pairs)
    if total_weight <= 0.0:
        raise ValueError("weighted_quantile requires a strictly positive total weight.")

    target = quantile * total_weight
    cumulative = 0.0
    for value, weight in pairs:
        cumulative += weight
        if cumulative >= target:
            return value
    return pairs[-1][0]


def normalize_shifted_weights(chi2_values: list[float]) -> tuple[list[float], float]:
    if not chi2_values:
        raise ValueError("normalize_shifted_weights requires at least one chi2 value.")
    chi2_min = min(chi2_values)
    shifted = [-0.5 * (value - chi2_min) for value in chi2_values]
    unnormalized = [exp(item) if item > -745.0 else 0.0 for item in shifted]
    total = sum(unnormalized)
    if total <= 0.0:
        raise ValueError("All shifted likelihood weights underflowed to zero.")
    return [value / total for value in unnormalized], chi2_min


class StatisticsRunner:
    def __init__(
        self,
        run_directory: str | Path,
        config: StatisticsSpec,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.run_directory = Path(run_directory)
        self.config = config
        self.metadata = metadata or self._read_json(self.run_directory / "metadata.json")
        self.points_path = self.run_directory / "points.csv"
        self.summary_path = self.run_directory / "summary.json"
        self.history_path = self.run_directory / "history.json"
        self.statistics_directory = self.run_directory / "statistics"
        self.validity_source = "valid_column"

    def run(self) -> StatisticsArtifacts:
        if not self.config.enabled:
            raise ValueError("StatisticsRunner.run() requires statistics.enabled = true.")
        if self.config.method in _NOT_IMPLEMENTED_METHODS:
            raise NotImplementedError(
                f"Statistics method '{self.config.method}' is reserved for future work and is not implemented yet."
            )
        if self.config.method != "de_weighted":
            raise NotImplementedError(
                f"Unsupported statistics method '{self.config.method}'."
            )
        return self._run_de_weighted()

    def _run_de_weighted(self) -> StatisticsArtifacts:
        rows, original_fieldnames, validity_warnings = self._read_points()
        history = self._read_history()
        warnings: list[str] = list(validity_warnings)
        objective_mode = str(self.metadata.get("objective_mode", "nll"))
        if objective_mode != "nll":
            warnings.append(
                f"Using metric_value from objective_mode '{objective_mode}' as chi2 for de_weighted statistics."
            )

        valid_rows: list[dict[str, Any]] = []
        valid_chi2: list[float] = []
        for row in rows:
            chi2 = row["chi2"]
            if row["valid"] and chi2 is not None and isfinite(chi2):
                valid_rows.append(row)
                valid_chi2.append(chi2)

        invalid_penalty = self._configured_invalid_penalty()
        if invalid_penalty is not None:
            inconsistent = sum(
                1
                for row in rows
                if row["valid"]
                and (metric := self._parse_float(row.get("metric_value"))) is not None
                and metric >= invalid_penalty
            )
            if inconsistent:
                warnings.append(
                    f"{inconsistent} rows have valid == true but metric_value >= invalid_penalty; "
                    "check evaluator validity propagation"
                )

        self.statistics_directory.mkdir(parents=True, exist_ok=True)
        samples_path = (
            self.statistics_directory / "de_weighted_samples.csv"
            if self.config.output_samples
            else None
        )
        summary_path = self.statistics_directory / "de_weighted_summary.json"
        credible_path = self.statistics_directory / "de_credible_intervals.json"
        diagnostics_path = self.statistics_directory / "diagnostics.json"

        if not valid_rows:
            warnings.append("No valid points with finite chi2 were available for de_weighted statistics.")
            sample_rows = self._decorate_rows(rows, history=history, chi2_min=None, valid_weights={})
            if samples_path is not None:
                self._write_samples_csv(samples_path, sample_rows, original_fieldnames)
            self._write_json(
                summary_path,
                {
                    "method": self.config.method,
                    "objective_mode": objective_mode,
                    "chi2_source": "metric_value",
                    "credible_levels": list(self.config.credible_levels),
                    "parameters": {},
                },
            )
            self._write_json(credible_path, {"method": self.config.method, "parameters": {}})
            self._write_json(
                diagnostics_path,
                {
                    "method": self.config.method,
                    "objective_mode": objective_mode,
                    "chi2_source": "metric_value",
                    "validity_source": self.validity_source,
                    "n_total_points": len(rows),
                    "n_valid_points": 0,
                    "n_invalid_points": len(rows),
                    "chi2_min": None,
                    "chi2_max_valid": None,
                    "effective_sample_size": 0.0,
                    "weight_max": 0.0,
                    "weight_min_nonzero": None,
                    "warnings": warnings,
                },
            )
            return StatisticsArtifacts(
                directory=self.statistics_directory,
                samples_path=samples_path,
                summary_path=summary_path,
                credible_intervals_path=credible_path,
                diagnostics_path=diagnostics_path,
            )

        valid_weights, chi2_min = normalize_shifted_weights(valid_chi2)
        valid_weight_map = {
            id(row): weight
            for row, weight in zip(valid_rows, valid_weights, strict=True)
        }
        sample_rows = self._decorate_rows(rows, history=history, chi2_min=chi2_min, valid_weights=valid_weight_map)
        if samples_path is not None:
            self._write_samples_csv(samples_path, sample_rows, original_fieldnames)

        parameter_names = [
            str(item.get("name"))
            for item in self.metadata.get("scanned_parameters", [])
            if item.get("name") is not None
        ]
        if not parameter_names:
            parameter_names = [
                field[len("param::") :]
                for field in original_fieldnames
                if field.startswith("param::")
            ]

        best_row = min(valid_rows, key=lambda item: item["chi2"])
        summaries: dict[str, Any] = {}
        interval_map: dict[str, Any] = {}
        positive_weight_rows = [row for row in valid_rows if valid_weight_map.get(id(row), 0.0) > 0.0]

        for parameter in parameter_names:
            column = f"param::{parameter}"
            all_parameter_values = [
                self._parse_float(row.get(column))
                for row in rows
                if self._parse_float(row.get(column)) is not None
            ]
            weighted_values = [
                self._parse_float(row.get(column))
                for row in positive_weight_rows
                if self._parse_float(row.get(column)) is not None
            ]
            weights = [
                valid_weight_map[id(row)]
                for row in positive_weight_rows
                if self._parse_float(row.get(column)) is not None
            ]
            if not weighted_values or not weights:
                warnings.append(
                    f"No finite weighted samples were available for parameter '{parameter}'."
                )
                continue

            mean = sum(weight * value for value, weight in zip(weighted_values, weights, strict=True))
            variance = sum(
                weight * (value - mean) ** 2
                for value, weight in zip(weighted_values, weights, strict=True)
            )
            median = weighted_quantile(weighted_values, weights, 0.5)

            summary_entry = {
                "best_fit": self._parse_float(best_row.get(column)),
                "weighted_mean": mean,
                "weighted_median": median,
                "weighted_std": sqrt(max(variance, 0.0)),
                "min_sampled": min(all_parameter_values) if all_parameter_values else None,
                "max_sampled": max(all_parameter_values) if all_parameter_values else None,
            }

            intervals_for_parameter: dict[str, Any] = {}
            for level in self.config.credible_levels:
                low_q = (1.0 - level) / 2.0
                high_q = 1.0 - low_q
                level_key = self._level_key(level)
                interval = {
                    "low": weighted_quantile(weighted_values, weights, low_q),
                    "high": weighted_quantile(weighted_values, weights, high_q),
                }
                intervals_for_parameter[level_key] = interval
                summary_entry[f"credible_interval_{level_key}"] = interval

            summaries[parameter] = summary_entry
            interval_map[parameter] = intervals_for_parameter

        self._write_json(
            summary_path,
            {
                "method": self.config.method,
                "objective_mode": objective_mode,
                "chi2_source": "metric_value",
                "credible_levels": list(self.config.credible_levels),
                "parameters": summaries,
            },
        )
        self._write_json(
            credible_path,
            {
                "method": self.config.method,
                "parameters": interval_map,
            },
        )

        nonzero_weights = [weight for weight in valid_weights if weight > 0.0]
        self._write_json(
            diagnostics_path,
            {
                "method": self.config.method,
                "objective_mode": objective_mode,
                "chi2_source": "metric_value",
                "validity_source": self.validity_source,
                "n_total_points": len(rows),
                "n_valid_points": len(valid_rows),
                "n_invalid_points": len(rows) - len(valid_rows),
                "chi2_min": chi2_min,
                "chi2_max_valid": max(valid_chi2),
                "effective_sample_size": 1.0 / sum(weight * weight for weight in valid_weights),
                "weight_max": max(valid_weights),
                "weight_min_nonzero": min(nonzero_weights) if nonzero_weights else None,
                "warnings": warnings,
            },
        )
        return StatisticsArtifacts(
            directory=self.statistics_directory,
            samples_path=samples_path,
            summary_path=summary_path,
            credible_intervals_path=credible_path,
            diagnostics_path=diagnostics_path,
        )

    def _decorate_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        history: list[dict[str, Any]],
        chi2_min: float | None,
        valid_weights: dict[int, float],
    ) -> list[dict[str, Any]]:
        decorated: list[dict[str, Any]] = []
        engine = str(self.metadata.get("engine", "unknown"))
        for index, row in enumerate(rows, start=1):
            evaluation = self._parse_int(row.get("evaluation"))
            point_id = evaluation if evaluation is not None else index
            chi2 = row["chi2"]
            delta_chi2 = None
            shifted_loglike = None
            loglike = None
            if chi2 is not None and isfinite(chi2):
                loglike = -0.5 * chi2
                if chi2_min is not None:
                    delta_chi2 = chi2 - chi2_min
                    shifted_loglike = -0.5 * delta_chi2
            weight = valid_weights.get(id(row), 0.0)
            generation = self._infer_generation(point_id, history)
            source = "scan_point"
            if engine == "de_scipy" and generation is not None:
                source = "de_population"
            elif engine != "de_scipy":
                source = "unknown"

            record: dict[str, Any] = {
                "point_id": point_id,
                "generation": generation,
                "source": source,
                "valid": "true" if row["valid"] else "false",
                "chi2": chi2,
                "delta_chi2": delta_chi2,
                "loglike": loglike,
                "shifted_loglike": shifted_loglike,
                "weight": weight,
            }
            for key, value in row.items():
                if key.startswith("output::") and not self.config.include_observables:
                    continue
                if key in {"valid", "chi2"}:
                    continue
                record[key] = value
            decorated.append(record)
        return decorated

    def _read_points(self) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        if not self.points_path.exists():
            raise FileNotFoundError(f"Scan points file '{self.points_path}' was not found.")
        with self.points_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            warnings: list[str] = []
            has_valid_column = "valid" in fieldnames
            if not has_valid_column:
                self.validity_source = "status_fallback"
                warnings.append(
                    "valid column missing; inferred validity from status == ok for backward compatibility"
                )
            else:
                self.validity_source = "valid_column"
            rows: list[dict[str, Any]] = []
            for row in reader:
                materialized = dict(row)
                if has_valid_column:
                    parsed_valid = self._parse_bool(materialized.get("valid"))
                    if parsed_valid is None:
                        parsed_valid = False
                        warnings.append(
                            f"Could not parse valid value for evaluation {materialized.get('evaluation', '?')}; treated as false."
                        )
                    materialized["valid"] = parsed_valid
                else:
                    materialized["valid"] = materialized.get("status", "") == "ok"
                chi2 = self._parse_float(materialized.get("metric_value"))
                if chi2 is None:
                    chi2 = self._parse_float(materialized.get("total_nll"))
                materialized["chi2"] = chi2
                rows.append(materialized)
        return rows, fieldnames, warnings

    def _read_history(self) -> list[dict[str, Any]]:
        if not self.history_path.exists():
            return []
        payload = self._read_json(self.history_path)
        return payload if isinstance(payload, list) else []

    def _infer_generation(self, point_id: int, history: list[dict[str, Any]]) -> int | None:
        if not history:
            return None
        thresholds = [
            self._parse_int(item.get("evaluations"))
            for item in history
            if self._parse_int(item.get("evaluations")) is not None
        ]
        for generation, threshold in enumerate(thresholds):
            assert threshold is not None
            if point_id <= threshold:
                return generation
        return len(thresholds)

    def _write_samples_csv(
        self,
        destination: Path,
        rows: list[dict[str, Any]],
        original_fieldnames: list[str],
    ) -> None:
        fieldnames = [
            "point_id",
            "generation",
            "source",
            "valid",
            "chi2",
            "delta_chi2",
            "loglike",
            "shifted_loglike",
            "weight",
        ]
        for name in original_fieldnames:
            if name.startswith("output::") and not self.config.include_observables:
                continue
            if name not in fieldnames:
                fieldnames.append(name)

        with destination.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                payload = {name: row.get(name, "") for name in fieldnames}
                writer.writerow(payload)

    @staticmethod
    def _parse_bool(value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
        return None

    def _configured_invalid_penalty(self) -> float | None:
        raw_settings = self.metadata.get("raw_settings", {})
        if not isinstance(raw_settings, dict):
            return None
        for key in ("invalid_penalty", "invalid_objective"):
            penalty = self._parse_float(raw_settings.get(key))
            if penalty is not None:
                return penalty
        return None

    @staticmethod
    def _level_key(level: float) -> str:
        percentage = level * 100.0
        rounded = round(percentage)
        if abs(percentage - rounded) < 1.0e-9:
            return str(int(rounded))
        return f"{percentage:.3f}".rstrip("0").rstrip(".")

    @staticmethod
    def _parse_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            parsed = float(value)
        except Exception:
            return None
        return parsed if isfinite(parsed) else None

    @staticmethod
    def _parse_int(value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_statistics(
    run_directory: str | Path,
    config: StatisticsSpec,
    *,
    metadata: dict[str, Any] | None = None,
) -> StatisticsArtifacts | None:
    if not config.enabled:
        return None
    return StatisticsRunner(run_directory, config, metadata=metadata).run()

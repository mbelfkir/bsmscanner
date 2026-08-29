from __future__ import annotations

import re

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from bsm_scanner.exceptions import ModelValidationError


class StrEnum(str, Enum):
    pass


class ValueType(StrEnum):
    REAL = "real"
    COMPLEX = "complex"
    BOOL = "bool"
    REAL_VECTOR = "real_vector"
    REAL_MATRIX = "real_matrix"
    COMPLEX_VECTOR = "complex_vector"
    COMPLEX_MATRIX = "complex_matrix"
    STRING = "string"


class MatrixKind(StrEnum):
    DIRAC_MASS = "dirac_mass"
    MAJORANA_MASS = "majorana_mass"
    COMPLEX_GENERAL = "complex_general"
    COMPLEX_SYMMETRIC = "complex_symmetric"
    HERMITIAN = "hermitian"
    REAL_SYMMETRIC = "real_symmetric"


class MixingMatrixKind(StrEnum):
    LEFT_MISMATCH = "left_mismatch"
    PMNS = "pmns"
    CKM = "ckm"


class MixingConvention(StrEnum):
    U_LEFT_DAGGER_U_RIGHT = "U_left_dagger_U_right"
    U_LEFT_U_RIGHT_DAGGER = "U_left_U_right_dagger"


class PriorKind(StrEnum):
    FLAT = "flat"
    LOG = "log"
    SIGNED_LOG = "signed_log"
    FIXED = "fixed"


class LikelihoodKind(StrEnum):
    GAUSSIAN = "gaussian"
    ASYMMETRIC_GAUSSIAN = "asymmetric_gaussian"
    UPPER_LIMIT = "upper_limit"
    LOWER_LIMIT = "lower_limit"
    INTERVAL = "interval"
    HARD_CUT = "hard_cut"
    TABLE_LOOKUP = "table_lookup"
    MULTIVARIATE_GAUSSIAN = "multivariate_gaussian"
    CUSTOM = "custom"


class TableInterpolationKind(StrEnum):
    LINEAR = "linear"
    CUBIC_SPLINE = "cubic_spline"


@dataclass(slots=True)
class ModelMetadata:
    name: str
    version: str = "0.1.0"
    description: str = ""
    ordering: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ParameterSpec:
    name: str
    value_type: ValueType = ValueType.REAL
    scan: bool = True
    lower: float | None = None
    upper: float | None = None
    default: float | complex | None = None
    prior: PriorKind = PriorKind.FLAT
    min_abs: float | None = None
    description: str = ""

    def validate(self) -> None:
        if self.scan and (self.lower is None or self.upper is None):
            raise ModelValidationError(
                f"Scanned parameter '{self.name}' requires lower and upper bounds."
            )
        if self.scan and self.lower is not None and self.upper is not None and self.lower >= self.upper:
            raise ModelValidationError(
                f"Scanned parameter '{self.name}' requires lower < upper."
            )
        if self.scan and self.prior == PriorKind.FIXED:
            raise ModelValidationError(
                f"Scanned parameter '{self.name}' cannot use the 'fixed' prior."
            )
        if self.scan and self.prior == PriorKind.SIGNED_LOG:
            assert self.lower is not None and self.upper is not None
            if not (self.lower < 0.0 < self.upper):
                raise ModelValidationError(
                    f"Signed-log prior for '{self.name}' requires bounds that straddle zero."
                )
            if self.min_abs is not None and self.min_abs <= 0.0:
                raise ModelValidationError(
                    f"Signed-log prior for '{self.name}' requires min_abs > 0."
                )
            max_abs = max(abs(float(self.lower)), abs(float(self.upper)))
            if self.min_abs is not None and self.min_abs >= max_abs:
                raise ModelValidationError(
                    f"Signed-log prior for '{self.name}' requires min_abs below the largest bound magnitude."
                )
        if not self.scan and self.default is None:
            raise ModelValidationError(
                f"Fixed parameter '{self.name}' requires a default value."
            )


@dataclass(slots=True)
class ConstantSpec:
    name: str
    value: float | complex | bool | str
    value_type: ValueType | None = None

    def resolved_type(self) -> ValueType:
        if self.value_type is not None:
            return self.value_type
        if isinstance(self.value, bool):
            return ValueType.BOOL
        if isinstance(self.value, complex):
            return ValueType.COMPLEX
        if isinstance(self.value, str):
            return ValueType.STRING
        return ValueType.REAL


@dataclass(slots=True)
class FunctionSpec:
    name: str
    args: list[str]
    expression: str
    value_type: ValueType = ValueType.REAL


@dataclass(slots=True)
class PluginCallSpec:
    plugin: str
    function: str
    bindings: dict[str, str] = field(default_factory=dict)
    options: dict[str, bool | float | str] = field(default_factory=dict)
    output: str | None = None

    def validate(self, owner_kind: str, owner_name: str) -> None:
        if not self.plugin:
            raise ModelValidationError(
                f"{owner_kind} '{owner_name}' requires a non-empty plugin name."
            )
        if not self.function:
            raise ModelValidationError(
                f"{owner_kind} '{owner_name}' requires a non-empty plugin function name."
            )
        for argument, source in self.bindings.items():
            if not argument:
                raise ModelValidationError(
                    f"{owner_kind} '{owner_name}' has an empty plugin binding name."
                )
            if not source:
                raise ModelValidationError(
                    f"{owner_kind} '{owner_name}' plugin binding '{argument}' must reference a source node."
                )
        for option_name, option_value in self.options.items():
            if not option_name:
                raise ModelValidationError(
                    f"{owner_kind} '{owner_name}' has an empty plugin option name."
                )
            if not isinstance(option_value, (bool, int, float, str)):
                raise ModelValidationError(
                    f"{owner_kind} '{owner_name}' plugin option '{option_name}' must be a scalar bool, number, or string."
                )
        if self.output is not None and not self.output:
            raise ModelValidationError(
                f"{owner_kind} '{owner_name}' plugin output selector must be non-empty when provided."
            )


@dataclass(slots=True)
class ExpressionNodeSpec:
    name: str
    expression: str | None
    value_type: ValueType
    plugin_call: PluginCallSpec | None = None
    description: str = ""

    def validate(self) -> None:
        if bool(self.expression) == bool(self.plugin_call):
            raise ModelValidationError(
                f"Derived node '{self.name}' must define exactly one of expression or plugin_call."
            )
        if self.plugin_call is not None:
            self.plugin_call.validate("Derived node", self.name)


@dataclass(slots=True)
class DiagonalizationOutputSpec:
    masses: str | None = None
    eigenvalues: str | None = None
    unitary: str | None = None
    left_unitary: str | None = None
    right_unitary: str | None = None

    def aliases(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "masses": self.masses,
                "eigenvalues": self.eigenvalues,
                "unitary": self.unitary,
                "left_unitary": self.left_unitary,
                "right_unitary": self.right_unitary,
            }.items()
            if value is not None
        }


@dataclass(slots=True)
class MatrixSpec:
    name: str
    rows: list[list[str]]
    value_type: ValueType = ValueType.REAL_MATRIX
    matrix_type: MatrixKind | None = None
    role: str | None = None
    diagonalize: bool = False
    diagonalization_name: str | None = None
    diagonalization_method: str | None = None
    diagonalization_output: DiagonalizationOutputSpec = field(default_factory=DiagonalizationOutputSpec)
    description: str = ""

    def shape(self) -> tuple[int, int]:
        if not self.rows or not self.rows[0]:
            raise ModelValidationError(f"Matrix '{self.name}' must have at least one cell.")
        width = len(self.rows[0])
        if any(len(row) != width for row in self.rows):
            raise ModelValidationError(f"Matrix '{self.name}' has inconsistent row widths.")
        return len(self.rows), width

    def validate(self) -> None:
        self.shape()
        if self.role is not None and not self.role:
            raise ModelValidationError(f"Matrix '{self.name}' role must be non-empty when provided.")
        if (self.diagonalization_name or self.diagonalization_method) and not self.diagonalize:
            raise ModelValidationError(
                f"Matrix '{self.name}' cannot specify diagonalization metadata unless diagonalize=true."
            )
        if self.diagonalization_name is not None and not self.diagonalization_name:
            raise ModelValidationError(
                f"Matrix '{self.name}' diagonalization_name must be non-empty when provided."
            )
        if self.diagonalization_method is not None and not self.diagonalization_method:
            raise ModelValidationError(
                f"Matrix '{self.name}' diagonalization_method must be non-empty when provided."
            )
        for alias_kind, alias_name in self.diagonalization_output.aliases().items():
            if not alias_name:
                raise ModelValidationError(
                    f"Matrix '{self.name}' diagonalization output alias '{alias_kind}' must be non-empty."
                )
        if self.diagonalize:
            self.resolved_diagonalization_method()

    def resolved_diagonalization_name(self) -> str:
        if self.diagonalization_name:
            return self.diagonalization_name
        base = self.role or self.name
        sanitized = "".join(ch if ch.isalnum() else "_" for ch in base).strip("_")
        if not sanitized:
            raise ModelValidationError(
                f"Matrix '{self.name}' could not derive a valid automatic diagonalization name."
            )
        return f"diag__{sanitized}"

    def resolved_diagonalization_method(self) -> str:
        if self.diagonalization_method:
            return self.diagonalization_method
        if self.matrix_type == MatrixKind.COMPLEX_SYMMETRIC:
            return "takagi"
        if self.matrix_type == MatrixKind.COMPLEX_GENERAL:
            return "svd"
        if self.matrix_type == MatrixKind.HERMITIAN:
            return "hermitian_eigh"
        if self.matrix_type == MatrixKind.REAL_SYMMETRIC:
            return "hermitian_eigh" if self.value_type == ValueType.COMPLEX_MATRIX else "self_adjoint_eigen"
        if self.matrix_type == MatrixKind.MAJORANA_MASS:
            return "takagi" if self.value_type == ValueType.COMPLEX_MATRIX else "svd_real"
        if self.matrix_type == MatrixKind.DIRAC_MASS:
            return "svd_complex" if self.value_type == ValueType.COMPLEX_MATRIX else "svd_real"
        return "svd_complex" if self.value_type == ValueType.COMPLEX_MATRIX else "svd_real"

    def projection_quantity_for_output(self, alias_kind: str) -> str:
        method = self.resolved_diagonalization_method()
        if alias_kind == "masses":
            return "eigenvalues" if method in {"hermitian_eigh", "self_adjoint_eigen", "self_adjoint_eigen_complex"} else "singular_values"
        if alias_kind == "eigenvalues":
            return "eigenvalues"
        if alias_kind in {"unitary", "left_unitary"}:
            if self.value_type == ValueType.COMPLEX_MATRIX:
                return "u_complex"
            return "u_real"
        if alias_kind == "right_unitary":
            if self.value_type == ValueType.COMPLEX_MATRIX:
                return "v_complex"
            return "v_real"
        raise ModelValidationError(
            f"Matrix '{self.name}' has unsupported diagonalization output alias '{alias_kind}'."
        )

    def projection_value_type_for_output(self, alias_kind: str) -> ValueType:
        if alias_kind in {"masses", "eigenvalues"}:
            return ValueType.REAL_VECTOR
        if self.value_type == ValueType.COMPLEX_MATRIX:
            return ValueType.COMPLEX_MATRIX
        return ValueType.REAL_MATRIX

    def auto_diagonalization(self) -> "DiagonalizationSpec" | None:
        if not self.diagonalize:
            return None
        return DiagonalizationSpec(
            name=self.resolved_diagonalization_name(),
            input=self.name,
            method=self.resolved_diagonalization_method(),
            description=(
                f"Automatically generated diagonalization for matrix '{self.name}'"
                + (f" with role '{self.role}'." if self.role else ".")
            ),
        )

    def auto_diagonalization_outputs(self) -> list["ObservableSpec"]:
        if not self.diagonalize:
            return []
        diagonalization_name = self.resolved_diagonalization_name()
        outputs: list[ObservableSpec] = []
        for alias_kind, alias_name in self.diagonalization_output.aliases().items():
            outputs.append(
                ObservableSpec(
                    name=alias_name,
                    value_type=self.projection_value_type_for_output(alias_kind),
                    projection=ProjectionSpec(
                        from_node=diagonalization_name,
                        quantity=self.projection_quantity_for_output(alias_kind),
                    ),
                    description=(
                        f"Automatically generated {alias_kind} output from diagonalization "
                        f"'{diagonalization_name}'."
                    ),
                )
            )
        return outputs


@dataclass(slots=True)
class DiagonalizationSpec:
    name: str
    input: str
    method: str
    description: str = ""


@dataclass(slots=True)
class MixingMatrixSpec:
    name: str
    kind: MixingMatrixKind = MixingMatrixKind.LEFT_MISMATCH
    convention: MixingConvention = MixingConvention.U_LEFT_DAGGER_U_RIGHT
    left: str | None = None
    right: str | None = None
    output: str | None = None
    neutrino: str | None = None
    charged_lepton: str | None = None
    up: str | None = None
    down: str | None = None
    charged_lepton_identity_fallback: bool = True
    description: str = ""

    def resolved_output(self) -> str:
        return self.output or self.name

    def resolved_inputs(self) -> tuple[str, str]:
        if self.kind == MixingMatrixKind.PMNS:
            right = self.neutrino or self.right
            if right is None:
                raise ModelValidationError(
                    f"Mixing matrix '{self.name}' of type 'pmns' requires a neutrino rotation."
                )
            left = self.charged_lepton or self.left
            if left is None or left == "auto_identity_if_missing":
                if not self.charged_lepton_identity_fallback:
                    raise ModelValidationError(
                        f"Mixing matrix '{self.name}' requested PMNS but no charged-lepton rotation was provided and identity fallback is disabled."
                    )
                left = "identity"
            return left, right

        if self.kind == MixingMatrixKind.CKM:
            left = self.up or self.left
            right = self.down or self.right
            if left is None or right is None:
                raise ModelValidationError(
                    f"Mixing matrix '{self.name}' of type 'ckm' requires both up and down left-handed rotations."
                )
            return left, right

        if self.left is None or self.right is None:
            raise ModelValidationError(
                f"Mixing matrix '{self.name}' requires both left and right rotations."
            )
        return self.left, self.right

    def validate(self) -> None:
        if not self.name:
            raise ModelValidationError("Mixing matrix entries require a non-empty name.")
        if not self.resolved_output():
            raise ModelValidationError(f"Mixing matrix '{self.name}' requires a non-empty output name.")
        self.resolved_inputs()


@dataclass(slots=True)
class ProjectionSpec:
    from_node: str
    quantity: str
    index: int | None = None
    row: int | None = None
    col: int | None = None


@dataclass(slots=True)
class ObservableSpec:
    name: str
    value_type: ValueType = ValueType.REAL
    expression: str | None = None
    projection: ProjectionSpec | None = None
    plugin_call: PluginCallSpec | None = None
    description: str = ""

    def validate(self) -> None:
        active_specs = sum(
            1
            for item in (self.expression, self.projection, self.plugin_call)
            if item is not None
        )
        if active_specs != 1:
            raise ModelValidationError(
                f"Observable '{self.name}' must define exactly one of expression, projection, or plugin_call."
            )
        if self.plugin_call is not None:
            self.plugin_call.validate("Observable", self.name)


@dataclass(slots=True)
class TheoryCheckSpec:
    name: str
    condition: str | None = None
    plugin_call: PluginCallSpec | None = None
    fatal: bool = True
    message: str = ""

    def validate(self) -> None:
        if bool(self.condition) == bool(self.plugin_call):
            raise ModelValidationError(
                f"Theory check '{self.name}' must define exactly one of condition or plugin_call."
            )
        if self.plugin_call is not None:
            self.plugin_call.validate("Theory check", self.name)


@dataclass(slots=True)
class LikelihoodSpec:
    name: str
    kind: LikelihoodKind
    observable: str | None = None
    observables: list[str] = field(default_factory=list)
    mean: float | None = None
    means: list[float] = field(default_factory=list)
    sigma: float | None = None
    sigma_up: float | None = None
    sigma_down: float | None = None
    lower: float | None = None
    upper: float | None = None
    covariance: list[list[float]] = field(default_factory=list)
    table: list[list[float]] = field(default_factory=list)
    plugin: str | None = None
    plugin_call: PluginCallSpec | None = None
    out_of_range_penalty_scale: float | None = None
    out_of_range_penalty_cap: float | None = None
    interpolation: TableInterpolationKind = TableInterpolationKind.LINEAR
    in_range_offset: float = 0.0
    quadratic_form_prefactor: float = 0.5

    def validate(self) -> None:
        if self.kind == LikelihoodKind.CUSTOM:
            if self.plugin_call is not None:
                self.plugin_call.validate("Likelihood", self.name)
            elif not self.plugin:
                raise ModelValidationError(
                    f"Custom likelihood '{self.name}' requires either plugin_call or legacy plugin."
                )
            return
        if self.plugin_call is not None:
            raise ModelValidationError(
                f"Likelihood '{self.name}' only supports plugin_call when kind is 'custom'."
            )
        if self.kind == LikelihoodKind.MULTIVARIATE_GAUSSIAN:
            if not self.observables or not self.covariance or not self.means:
                raise ModelValidationError(
                    f"Likelihood '{self.name}' requires observables, means, and covariance."
                )
            if not self.quadratic_form_prefactor >= 0.0:
                raise ModelValidationError(
                    f"Likelihood '{self.name}' requires a non-negative quadratic_form_prefactor."
                )
        elif self.kind == LikelihoodKind.TABLE_LOOKUP:
            if self.observable is None:
                raise ModelValidationError(
                    f"Likelihood '{self.name}' requires a single observable."
                )
            if not self.table:
                raise ModelValidationError(
                    f"Likelihood '{self.name}' requires a non-empty lookup table."
                )
        elif self.observable is None:
            raise ModelValidationError(
                f"Likelihood '{self.name}' requires a single observable."
            )


@dataclass(slots=True)
class OutputSpec:
    save: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ScanSpec:
    engine: str = "diver"
    save_every: int = 1000
    seed: int = 12345
    settings: dict[str, Any] = field(default_factory=dict)
    adaptive_diver: dict[str, Any] = field(default_factory=dict)
    basin_scan: dict[str, Any] = field(default_factory=dict)
    posterior: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StatisticsSpec:
    enabled: bool = False
    method: str = "de_weighted"
    credible_levels: list[float] = field(default_factory=lambda: [0.68, 0.95])
    output_samples: bool = True
    include_observables: bool = True

    def validate(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ModelValidationError("statistics.enabled must be true or false.")
        if not isinstance(self.method, str) or not self.method:
            raise ModelValidationError("statistics.method must be a non-empty string.")
        if not isinstance(self.output_samples, bool):
            raise ModelValidationError("statistics.output_samples must be true or false.")
        if not isinstance(self.include_observables, bool):
            raise ModelValidationError("statistics.include_observables must be true or false.")
        if not self.credible_levels:
            raise ModelValidationError("statistics.credible_levels must contain at least one level.")
        cleaned: list[float] = []
        seen: set[float] = set()
        for raw_level in self.credible_levels:
            try:
                level = float(raw_level)
            except Exception as exc:
                raise ModelValidationError(
                    "statistics.credible_levels must contain only real numbers."
                ) from exc
            if not 0.0 < level < 1.0:
                raise ModelValidationError(
                    "statistics.credible_levels entries must satisfy 0 < level < 1."
                )
            if level not in seen:
                seen.add(level)
                cleaned.append(level)
        self.credible_levels = sorted(cleaned)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "method": self.method,
            "credible_levels": list(self.credible_levels),
            "output_samples": self.output_samples,
            "include_observables": self.include_observables,
        }


@dataclass(slots=True)
class ModelDefinition:
    metadata: ModelMetadata
    parameters: list[ParameterSpec] = field(default_factory=list)
    constants: list[ConstantSpec] = field(default_factory=list)
    functions: list[FunctionSpec] = field(default_factory=list)
    derived_scalars: list[ExpressionNodeSpec] = field(default_factory=list)
    derived_complex: list[ExpressionNodeSpec] = field(default_factory=list)
    matrices: list[MatrixSpec] = field(default_factory=list)
    diagonalizations: list[DiagonalizationSpec] = field(default_factory=list)
    mixing_matrices: list[MixingMatrixSpec] = field(default_factory=list)
    observables: list[ObservableSpec] = field(default_factory=list)
    theory_checks: list[TheoryCheckSpec] = field(default_factory=list)
    likelihoods: list[LikelihoodSpec] = field(default_factory=list)
    outputs: OutputSpec = field(default_factory=OutputSpec)
    scan: ScanSpec = field(default_factory=ScanSpec)
    guided_sampling: dict[str, Any] = field(default_factory=dict)
    statistics: StatisticsSpec = field(default_factory=StatisticsSpec)

    def resolved_diagonalizations(self) -> list[DiagonalizationSpec]:
        resolved = list(self.diagonalizations)
        auto = [spec for matrix in self.matrices if (spec := matrix.auto_diagonalization()) is not None]
        seen: set[str] = {item.name for item in resolved}
        for spec in auto:
            if spec.name in seen:
                raise ModelValidationError(
                    f"Automatic diagonalization '{spec.name}' conflicts with an explicitly declared node."
                )
            seen.add(spec.name)
            resolved.append(spec)
        return resolved

    def resolved_observables(self) -> list[ObservableSpec]:
        resolved = list(self.observables)
        auto = [
            observable
            for matrix in self.matrices
            for observable in matrix.auto_diagonalization_outputs()
        ]
        seen: set[str] = {item.name for item in resolved}
        for observable in auto:
            if observable.name in seen:
                raise ModelValidationError(
                    f"Automatic diagonalization output '{observable.name}' conflicts with an explicitly declared observable."
                )
            seen.add(observable.name)
            resolved.append(observable)
        return resolved

    def validate(self) -> None:
        seen: set[str] = set()
        for collection in (
            self.parameters,
            self.constants,
            self.functions,
            self.derived_scalars,
            self.derived_complex,
            self.matrices,
            self.diagonalizations,
            self.mixing_matrices,
            self.observables,
            self.theory_checks,
            self.likelihoods,
        ):
            for item in collection:
                name = getattr(item, "name")
                if name in seen:
                    raise ModelValidationError(f"Duplicate model entry '{name}'.")
                seen.add(name)

        for parameter in self.parameters:
            parameter.validate()
        for derived in self.derived_scalars + self.derived_complex:
            derived.validate()
        for matrix in self.matrices:
            matrix.validate()
        role_to_matrix: dict[str, str] = {}
        for matrix in self.matrices:
            if matrix.diagonalize and matrix.role is not None:
                previous = role_to_matrix.get(matrix.role)
                if previous is not None:
                    raise ModelValidationError(
                        f"Matrices '{previous}' and '{matrix.name}' both declare the diagonalization role '{matrix.role}'."
                    )
                role_to_matrix[matrix.role] = matrix.name
        explicit_diagonalization_names = {item.name for item in self.diagonalizations}
        for diag in self.resolved_diagonalizations():
            if diag.name not in explicit_diagonalization_names and diag.name in seen:
                raise ModelValidationError(
                    f"Automatically generated diagonalization '{diag.name}' conflicts with an existing model entry."
                )
            seen.add(diag.name)
        generated_observable_names: set[str] = set()
        for matrix in self.matrices:
            for observable in matrix.auto_diagonalization_outputs():
                observable_name = observable.name
                if observable_name in generated_observable_names:
                    raise ModelValidationError(
                        f"Automatic diagonalization output '{observable_name}' is generated more than once."
                    )
                generated_observable_names.add(observable_name)
                if observable_name in seen:
                    raise ModelValidationError(
                        f"Automatic diagonalization output '{observable_name}' conflicts with an existing model entry."
                    )
                seen.add(observable_name)
        for mixing in self.mixing_matrices:
            mixing.validate()
            output_name = mixing.resolved_output()
            if output_name in seen and output_name != mixing.name:
                raise ModelValidationError(
                    f"Mixing matrix '{mixing.name}' output '{output_name}' conflicts with an existing model entry."
                )
            seen.add(output_name)
        known_nodes = set(seen)
        for mixing in self.mixing_matrices:
            for source in mixing.resolved_inputs():
                if source != "identity" and source not in known_nodes:
                    raise ModelValidationError(
                        f"Mixing matrix '{mixing.name}' references undefined rotation '{source}'."
                    )
        for observable in self.resolved_observables():
            observable.validate()
        for theory_check in self.theory_checks:
            theory_check.validate()
        for likelihood in self.likelihoods:
            likelihood.validate()
        self.statistics.validate()

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ModelDefinition":
        metadata = ModelMetadata(**raw.get("metadata", {}))

        parameters = [
            ParameterSpec(
                name=item["name"],
                value_type=ValueType(item.get("value_type", "real")),
                scan=item.get("scan", True),
                lower=_optional_number(item.get("lower"), "lower", f"parameter '{item.get('name', '?')}'"),
                upper=_optional_number(item.get("upper"), "upper", f"parameter '{item.get('name', '?')}'"),
                default=_optional_number(item.get("default"), "default", f"parameter '{item.get('name', '?')}'"),
                prior=PriorKind(item.get("prior", "flat")),
                min_abs=_optional_number(item.get("min_abs"), "min_abs", f"parameter '{item.get('name', '?')}'"),
                description=item.get("description", ""),
            )
            for item in raw.get("parameters", [])
        ]

        constants = [
            ConstantSpec(
                name=item["name"],
                value=_coerce_constant_value(item["value"], item["name"]),
                value_type=ValueType(item["value_type"]) if "value_type" in item else None,
            )
            for item in raw.get("constants", [])
        ]

        functions = [
            FunctionSpec(
                name=item["name"],
                args=list(item.get("args", [])),
                expression=item["expression"],
                value_type=ValueType(item.get("value_type", "real")),
            )
            for item in raw.get("functions", [])
        ]

        derived_scalars = [
            ExpressionNodeSpec(
                name=item["name"],
                expression=item.get("expression"),
                value_type=ValueType(item.get("value_type", "real")),
                plugin_call=_parse_plugin_call(item),
                description=item.get("description", ""),
            )
            for item in raw.get("derived_scalars", [])
        ]

        derived_complex = [
            ExpressionNodeSpec(
                name=item["name"],
                expression=item.get("expression"),
                value_type=ValueType(item.get("value_type", "complex")),
                plugin_call=_parse_plugin_call(item),
                description=item.get("description", ""),
            )
            for item in raw.get("derived_complex", [])
        ]

        matrices = [
            MatrixSpec(
                name=item["name"],
                rows=item["rows"],
                value_type=ValueType(item.get("value_type", "real_matrix")),
                matrix_type=(
                    MatrixKind(item.get("matrix_type", item.get("type")))
                    if item.get("matrix_type", item.get("type")) is not None
                    else None
                ),
                role=item.get("role"),
                diagonalize=_parse_diagonalize_enabled(item),
                diagonalization_name=_parse_diagonalize_name(item),
                diagonalization_method=_parse_diagonalize_method(item),
                diagonalization_output=_parse_diagonalize_output(item),
                description=item.get("description", ""),
            )
            for item in _named_entries(raw, "matrices")
        ]

        diagonalizations = [
            DiagonalizationSpec(
                name=item["name"],
                input=item["input"],
                method=item["method"],
                description=item.get("description", ""),
            )
            for item in _named_entries(raw, "diagonalizations")
        ]

        mixing_matrices = [
            MixingMatrixSpec(
                name=item["name"],
                kind=MixingMatrixKind(item.get("type", item.get("kind", "left_mismatch"))),
                convention=MixingConvention(
                    item.get("convention", MixingConvention.U_LEFT_DAGGER_U_RIGHT.value)
                ),
                left=item.get("left"),
                right=item.get("right"),
                output=item.get("output"),
                neutrino=item.get("neutrino"),
                charged_lepton=item.get("charged_lepton"),
                up=item.get("up"),
                down=item.get("down"),
                charged_lepton_identity_fallback=bool(
                    item.get("charged_lepton_identity_fallback", True)
                ),
                description=item.get("description", ""),
            )
            for item in _named_entries(raw, "mixing_matrices")
        ]

        observables = []
        for item in _named_entries(raw, "observables"):
            projection = None
            if "projection" in item:
                projection = ProjectionSpec(
                    from_node=item["projection"]["from"],
                    quantity=item["projection"]["quantity"],
                    index=item["projection"].get("index"),
                    row=item["projection"].get("row"),
                    col=item["projection"].get("col"),
                )
            observables.append(
                ObservableSpec(
                    name=item["name"],
                    value_type=ValueType(item.get("value_type", "real")),
                    expression=item.get("expression"),
                    projection=projection,
                    plugin_call=_parse_plugin_call(item),
                    description=item.get("description", ""),
                )
            )

        theory_checks = [
            TheoryCheckSpec(
                name=item["name"],
                condition=item.get("condition"),
                plugin_call=_parse_plugin_call(item),
                fatal=item.get("fatal", True),
                message=item.get("message", ""),
            )
            for item in raw.get("theory_checks", [])
        ]

        likelihoods = [
            LikelihoodSpec(
                name=item["name"],
                kind=LikelihoodKind(item["kind"]),
                observable=item.get("observable"),
                observables=list(item.get("observables", [])),
                mean=item.get("mean"),
                means=list(item.get("means", [])),
                sigma=item.get("sigma"),
                sigma_up=item.get("sigma_up"),
                sigma_down=item.get("sigma_down"),
                lower=item.get("lower"),
                upper=item.get("upper"),
                covariance=list(item.get("covariance", [])),
                table=list(item.get("table", [])),
                plugin=item.get("plugin"),
                plugin_call=_parse_plugin_call(item),
                out_of_range_penalty_scale=(
                    _require_number(item["out_of_range_penalty_scale"], "out_of_range_penalty_scale", f"likelihood '{item.get('name', '?')}'")
                    if item.get("out_of_range_penalty_scale") is not None
                    else None
                ),
                out_of_range_penalty_cap=(
                    _require_number(item["out_of_range_penalty_cap"], "out_of_range_penalty_cap", f"likelihood '{item.get('name', '?')}'")
                    if item.get("out_of_range_penalty_cap") is not None
                    else None
                ),
                interpolation=TableInterpolationKind(
                    item.get("interpolation", TableInterpolationKind.LINEAR.value)
                ),
                in_range_offset=float(item.get("in_range_offset", 0.0)),
                quadratic_form_prefactor=float(item.get("quadratic_form_prefactor", 0.5)),
            )
            for item in raw.get("likelihoods", [])
        ]

        outputs = OutputSpec(save=list(raw.get("outputs", {}).get("save", [])))
        scan = ScanSpec(**raw.get("scan", {}))
        guided_sampling = dict(raw.get("guided_sampling", {}))
        statistics_raw = dict(raw.get("statistics", {}))
        if "credible_levels" in statistics_raw and statistics_raw["credible_levels"] is not None:
            statistics_raw["credible_levels"] = list(statistics_raw["credible_levels"])
        statistics = StatisticsSpec(**statistics_raw)

        model = cls(
            metadata=metadata,
            parameters=parameters,
            constants=constants,
            functions=functions,
            derived_scalars=derived_scalars,
            derived_complex=derived_complex,
            matrices=matrices,
            diagonalizations=diagonalizations,
            mixing_matrices=mixing_matrices,
            observables=observables,
            theory_checks=theory_checks,
            likelihoods=likelihoods,
            outputs=outputs,
            scan=scan,
            guided_sampling=guided_sampling,
            statistics=statistics,
        )
        model.validate()
        return model


def _parse_plugin_call(item: Mapping[str, Any]) -> PluginCallSpec | None:
    payload = item.get("plugin_call")
    if payload is None:
        return None
    if not isinstance(payload, Mapping):
        raise ModelValidationError("plugin_call must be a mapping.")
    bindings = payload.get("bindings", {})
    if not isinstance(bindings, Mapping):
        raise ModelValidationError("plugin_call.bindings must be a mapping of argument to source node.")
    options = payload.get("options", {})
    if not isinstance(options, Mapping):
        raise ModelValidationError("plugin_call.options must be a mapping of option to scalar value.")
    return PluginCallSpec(
        plugin=str(payload.get("plugin", "")),
        function=str(payload.get("function", "")),
        bindings={str(argument): str(source) for argument, source in bindings.items()},
        options={str(name): _coerce_plugin_option(name, value) for name, value in options.items()},
        output=str(payload["output"]) if payload.get("output") is not None else None,
    )


def _named_entries(raw: Mapping[str, Any], section: str) -> list[Mapping[str, Any]]:
    entries = raw.get(section, [])
    if isinstance(entries, Mapping):
        normalized: list[Mapping[str, Any]] = []
        for name, payload in entries.items():
            if not isinstance(payload, Mapping):
                raise ModelValidationError(
                    f"Section '{section}' entry '{name}' must be a mapping."
                )
            normalized.append({"name": str(name), **dict(payload)})
        return normalized
    if not isinstance(entries, list):
        raise ModelValidationError(f"Section '{section}' must be a list or mapping.")
    return entries


def _parse_diagonalize_enabled(item: Mapping[str, Any]) -> bool:
    payload = item.get("diagonalize", False)
    if isinstance(payload, Mapping):
        return True
    return bool(payload)


def _parse_diagonalize_name(item: Mapping[str, Any]) -> str | None:
    payload = item.get("diagonalize", False)
    if isinstance(payload, Mapping):
        return payload.get("name", item.get("diagonalization_name"))
    return item.get("diagonalization_name")


def _parse_diagonalize_method(item: Mapping[str, Any]) -> str | None:
    payload = item.get("diagonalize", False)
    if isinstance(payload, Mapping):
        return payload.get("method", item.get("diagonalization_method"))
    return item.get("diagonalization_method")


def _parse_diagonalize_output(item: Mapping[str, Any]) -> DiagonalizationOutputSpec:
    payload = item.get("diagonalize", False)
    output: Mapping[str, Any] = {}
    if isinstance(payload, Mapping):
        raw_output = payload.get("output", {})
        if raw_output is None:
            output = {}
        elif isinstance(raw_output, Mapping):
            output = raw_output
        else:
            raise ModelValidationError(
                f"Matrix '{item.get('name', '<unknown>')}' diagonalize.output must be a mapping."
            )
    return DiagonalizationOutputSpec(
        masses=str(output["masses"]) if output.get("masses") is not None else None,
        eigenvalues=str(output["eigenvalues"]) if output.get("eigenvalues") is not None else None,
        unitary=str(output["unitary"]) if output.get("unitary") is not None else None,
        left_unitary=(
            str(output["left_unitary"]) if output.get("left_unitary") is not None else None
        ),
        right_unitary=(
            str(output["right_unitary"]) if output.get("right_unitary") is not None else None
        ),
    )


_NUMERIC_TEXT = re.compile(
    r"^[-+]?(?:[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?|\.?(?:inf|Inf|INF))$"
)


def _require_number(value: Any, field: str, owner: str) -> float:
    """Coerce a numeric field, refusing text that silently poisons the model.

    YAML 1.1 loads ``1.0e9`` as a string.  The shipped loader resolves floats the
    YAML 1.2 way, but models may also be built in Python or loaded by a third
    party, so numeric fields are checked here as well and fail with a message
    that names the field instead of surfacing later as a type error.
    """
    if isinstance(value, bool):
        raise ModelValidationError(
            f"{owner}: '{field}' must be a number, got the boolean {value!r}."
        )
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and _NUMERIC_TEXT.match(value.strip()):
        return float(value)
    raise ModelValidationError(
        f"{owner}: '{field}' must be a number, got {value!r}. "
        "If this came from YAML, note that an exponent without a sign "
        "(1.0e9) is parsed as a string by YAML 1.1 -- write 1.0e+9."
    )


def _optional_number(value: Any, field: str, owner: str) -> float | None:
    """Like :func:`_require_number` but tolerates an absent field."""
    if value is None:
        return None
    return _require_number(value, field, owner)


def _coerce_constant_value(value: Any, name: str) -> Any:
    """Turn numeric-looking text into a float; leave genuine strings alone."""
    if isinstance(value, str) and _NUMERIC_TEXT.match(value.strip()):
        return float(value)
    return value


def _coerce_plugin_option(name: Any, value: Any) -> bool | float | str:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return value
    raise ModelValidationError(
        f"plugin_call option '{name}' must be a scalar bool, number, or string."
    )

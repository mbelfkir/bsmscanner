#include "bsm/core/constraints.hpp"
#include "bsm/core/evaluator.hpp"
#include "bsm/core/functions.hpp"
#include "bsm/core/plugins.hpp"
#include "bsm/core/scan/adapter.hpp"
#include "bsm/core/scan/runner.hpp"

#include <pybind11/complex.h>
#include <pybind11/eigen.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <stdexcept>
#include <string>

namespace py = pybind11;
using namespace bsm::core;
using namespace bsm::core::scan;

namespace {

ValueType parse_value_type(const std::string& value) {
  if (value == "real") return ValueType::Real;
  if (value == "complex") return ValueType::Complex;
  if (value == "bool") return ValueType::Bool;
  if (value == "real_vector") return ValueType::RealVector;
  if (value == "real_matrix") return ValueType::RealMatrix;
  if (value == "complex_vector") return ValueType::ComplexVector;
  if (value == "complex_matrix") return ValueType::ComplexMatrix;
  if (value == "string") return ValueType::String;
  if (value == "diagonalization") return ValueType::Diagonalization;
  return ValueType::Unknown;
}

NodeKind parse_node_kind(const std::string& value) {
  if (value == "external_parameter") return NodeKind::ExternalParameter;
  if (value == "constant") return NodeKind::Constant;
  if (value == "function") return NodeKind::Function;
  if (value == "derived") return NodeKind::Derived;
  if (value == "matrix") return NodeKind::Matrix;
  if (value == "diagonalization") return NodeKind::Diagonalization;
  if (value == "mixing_matrix") return NodeKind::MixingMatrix;
  if (value == "observable") return NodeKind::Observable;
  if (value == "theory_check") return NodeKind::TheoryCheck;
  if (value == "constraint") return NodeKind::Constraint;
  if (value == "output") return NodeKind::Output;
  throw std::runtime_error("Unknown node kind: " + value);
}

ConstraintKind parse_constraint_kind(const std::string& value) {
  if (value == "gaussian") return ConstraintKind::Gaussian;
  if (value == "asymmetric_gaussian") return ConstraintKind::AsymmetricGaussian;
  if (value == "upper_limit") return ConstraintKind::UpperLimit;
  if (value == "lower_limit") return ConstraintKind::LowerLimit;
  if (value == "interval") return ConstraintKind::Interval;
  if (value == "hard_cut") return ConstraintKind::HardCut;
  if (value == "table_lookup") return ConstraintKind::TableLookup;
  if (value == "multivariate_gaussian") return ConstraintKind::MultivariateGaussian;
  if (value == "custom") return ConstraintKind::Custom;
  throw std::runtime_error("Unknown constraint kind: " + value);
}

TableInterpolationKind parse_table_interpolation_kind(const std::string& value) {
  if (value == "linear") return TableInterpolationKind::Linear;
  if (value == "cubic_spline") return TableInterpolationKind::CubicSpline;
  throw std::runtime_error("Unknown table interpolation kind: " + value);
}

LiteralSpec parse_literal(const py::handle& obj) {
  LiteralSpec literal;
  const auto data = py::reinterpret_borrow<py::dict>(obj);
  const auto kind = py::cast<std::string>(data["kind"]);
  literal.type = parse_value_type(kind);
  if (kind == "real") {
    literal.real_value = py::cast<double>(data["value"]);
  } else if (kind == "bool") {
    literal.bool_value = py::cast<bool>(data["value"]);
  } else if (kind == "complex") {
    literal.complex_value = std::complex<double>(py::cast<double>(data["re"]),
                                                 py::cast<double>(data["im"]));
  } else if (kind == "string") {
    literal.string_value = py::cast<std::string>(data["value"]);
  }
  return literal;
}

Program parse_program(const py::handle& obj) {
  Program program;
  const auto data = py::reinterpret_borrow<py::dict>(obj);
  program.return_type = parse_value_type(py::cast<std::string>(data["return_type"]));
  program.dependencies = py::cast<std::vector<std::string>>(data["dependencies"]);

  for (const auto& item : py::reinterpret_borrow<py::list>(data["instructions"])) {
    const auto ins = py::reinterpret_borrow<py::dict>(item);
    Instruction instruction;
    instruction.op = py::cast<std::string>(ins["op"]);
    if (ins.contains("name")) instruction.name = py::cast<std::string>(ins["name"]);
    if (ins.contains("argc")) instruction.argc = py::cast<int>(ins["argc"]);
    if (ins.contains("value")) instruction.value = py::cast<double>(ins["value"]);
    if (ins.contains("re")) instruction.re = py::cast<double>(ins["re"]);
    if (ins.contains("im")) instruction.im = py::cast<double>(ins["im"]);
    if (ins.contains("boolean")) instruction.boolean = py::cast<bool>(ins["boolean"]);
    if (instruction.op == "push_bool" && ins.contains("value")) {
      instruction.boolean = py::cast<bool>(ins["value"]);
    }
    program.instructions.push_back(std::move(instruction));
  }
  return program;
}

MatrixProgram parse_matrix(const py::handle& obj) {
  MatrixProgram matrix;
  const auto data = py::reinterpret_borrow<py::dict>(obj);
  matrix.rows = py::cast<int>(data["rows"]);
  matrix.cols = py::cast<int>(data["cols"]);
  for (const auto& item : py::reinterpret_borrow<py::list>(data["cells"])) {
    matrix.cells.push_back(parse_program(item));
  }
  return matrix;
}

ProjectionSpec parse_projection(const py::handle& obj) {
  const auto data = py::reinterpret_borrow<py::dict>(obj);
  ProjectionSpec spec;
  spec.source = py::cast<std::string>(data["from"]);
  spec.quantity = py::cast<std::string>(data["quantity"]);
  if (data.contains("index") && !data["index"].is_none()) spec.index = py::cast<int>(data["index"]);
  if (data.contains("row") && !data["row"].is_none()) spec.row = py::cast<int>(data["row"]);
  if (data.contains("col") && !data["col"].is_none()) spec.col = py::cast<int>(data["col"]);
  return spec;
}

PluginCallSpec parse_plugin_call(const py::handle& obj) {
  const auto data = py::reinterpret_borrow<py::dict>(obj);
  PluginCallSpec spec;
  spec.plugin = py::cast<std::string>(data["plugin"]);
  spec.function = py::cast<std::string>(data["function"]);
  if (data.contains("output") && !data["output"].is_none()) {
    spec.output = py::cast<std::string>(data["output"]);
  }
  for (const auto& item : py::reinterpret_borrow<py::list>(data["bindings"])) {
    const auto binding = py::reinterpret_borrow<py::dict>(item);
    spec.bindings.push_back({
        py::cast<std::string>(binding["argument"]),
        py::cast<std::string>(binding["source"]),
    });
  }
  if (data.contains("options")) {
    for (const auto& item : py::reinterpret_borrow<py::list>(data["options"])) {
      const auto option = py::reinterpret_borrow<py::dict>(item);
      spec.options.push_back({
          py::cast<std::string>(option["name"]),
          parse_literal(option["value"]),
      });
    }
  }
  return spec;
}

DiagonalizationSpec parse_diagonalization(const py::handle& obj) {
  const auto data = py::reinterpret_borrow<py::dict>(obj);
  return {
      py::cast<std::string>(data["input"]),
      py::cast<std::string>(data["method"]),
  };
}

MixingMatrixSpec parse_mixing_matrix(const py::handle& obj) {
  const auto data = py::reinterpret_borrow<py::dict>(obj);
  return {
      py::cast<std::string>(data["type"]),
      py::cast<std::string>(data["convention"]),
      py::cast<std::string>(data["left"]),
      py::cast<std::string>(data["right"]),
  };
}

ConstraintSpec parse_constraint(const py::handle& obj) {
  const auto data = py::reinterpret_borrow<py::dict>(obj);
  ConstraintSpec spec;
  spec.kind = parse_constraint_kind(py::cast<std::string>(data["kind"]));
  if (data.contains("interpolation") && !data["interpolation"].is_none()) {
    spec.interpolation =
        parse_table_interpolation_kind(py::cast<std::string>(data["interpolation"]));
  }
  if (data.contains("observable") && !data["observable"].is_none()) {
    spec.observable = py::cast<std::string>(data["observable"]);
  }
  if (data.contains("observables")) {
    spec.observables = py::cast<std::vector<std::string>>(data["observables"]);
  }
  if (data.contains("mean") && !data["mean"].is_none()) spec.mean = py::cast<double>(data["mean"]);
  if (data.contains("means")) spec.means = py::cast<std::vector<double>>(data["means"]);
  if (data.contains("sigma") && !data["sigma"].is_none()) spec.sigma = py::cast<double>(data["sigma"]);
  if (data.contains("sigma_up") && !data["sigma_up"].is_none()) spec.sigma_up = py::cast<double>(data["sigma_up"]);
  if (data.contains("sigma_down") && !data["sigma_down"].is_none()) spec.sigma_down = py::cast<double>(data["sigma_down"]);
  if (data.contains("lower") && !data["lower"].is_none()) spec.lower = py::cast<double>(data["lower"]);
  if (data.contains("upper") && !data["upper"].is_none()) spec.upper = py::cast<double>(data["upper"]);
  if (data.contains("covariance")) spec.covariance = py::cast<std::vector<std::vector<double>>>(data["covariance"]);
  if (data.contains("table")) spec.table = py::cast<std::vector<std::vector<double>>>(data["table"]);
  if (data.contains("plugin") && !data["plugin"].is_none()) spec.plugin = py::cast<std::string>(data["plugin"]);
  if (data.contains("plugin_call") && !data["plugin_call"].is_none()) {
    spec.plugin_call = parse_plugin_call(data["plugin_call"]);
  }
  if (data.contains("out_of_range_penalty_scale") && !data["out_of_range_penalty_scale"].is_none()) {
    spec.out_of_range_penalty_scale = py::cast<double>(data["out_of_range_penalty_scale"]);
  }
  if (data.contains("out_of_range_penalty_cap") && !data["out_of_range_penalty_cap"].is_none()) {
    spec.out_of_range_penalty_cap = py::cast<double>(data["out_of_range_penalty_cap"]);
  }
  if (data.contains("in_range_offset") && !data["in_range_offset"].is_none()) {
    spec.in_range_offset = py::cast<double>(data["in_range_offset"]);
  }
  if (data.contains("quadratic_form_prefactor") &&
      !data["quadratic_form_prefactor"].is_none()) {
    spec.quadratic_form_prefactor =
        py::cast<double>(data["quadratic_form_prefactor"]);
  }
  finalize_constraint(spec);
  return spec;
}

OutputSpec parse_output(const py::handle& obj) {
  const auto data = py::reinterpret_borrow<py::dict>(obj);
  return {
      py::cast<std::string>(data["source"]),
      py::cast<std::string>(data["label"]),
  };
}

Value parse_python_value(const py::handle& obj) {
  if (obj.is_none()) return std::monostate{};
  if (py::isinstance<py::bool_>(obj)) return py::cast<bool>(obj);
  if (py::isinstance<py::float_>(obj) || py::isinstance<py::int_>(obj)) {
    return py::cast<double>(obj);
  }
  if (PyComplex_Check(obj.ptr())) return py::cast<std::complex<double>>(obj);
  if (py::isinstance<py::str>(obj)) return py::cast<std::string>(obj);
  throw std::runtime_error("Unsupported Python input value type.");
}

py::object value_to_python(const Value& value) {
  if (const auto* real = std::get_if<double>(&value)) return py::float_(*real);
  if (const auto* boolean = std::get_if<bool>(&value)) return py::bool_(*boolean);
  if (const auto* complex = std::get_if<std::complex<double>>(&value)) return py::cast(*complex);
  if (const auto* string = std::get_if<std::string>(&value)) return py::cast(*string);
  if (const auto* vector = std::get_if<Eigen::VectorXd>(&value)) return py::cast(*vector);
  if (const auto* matrix = std::get_if<Eigen::MatrixXd>(&value)) return py::cast(*matrix);
  if (const auto* vector = std::get_if<Eigen::VectorXcd>(&value)) return py::cast(*vector);
  if (const auto* matrix = std::get_if<Eigen::MatrixXcd>(&value)) return py::cast(*matrix);
  if (const auto* diag = std::get_if<DiagonalizationValue>(&value)) {
    py::dict out;
    out["singular_values"] = py::cast(diag->singular_values);
    out["eigenvalues"] = py::cast(diag->eigenvalues);
    out["u_real"] = py::cast(diag->u_real);
    out["v_real"] = py::cast(diag->v_real);
    out["u_complex"] = py::cast(diag->u_complex);
    out["v_complex"] = py::cast(diag->v_complex);
    return std::move(out);
  }
  return py::none();
}

CompiledModelPlan parse_plan(const py::dict& data) {
  CompiledModelPlan plan;
  plan.name = py::cast<std::string>(data["name"]);
  plan.version = py::cast<std::string>(data["version"]);
  plan.evaluation_order = py::cast<std::vector<std::string>>(data["evaluation_order"]);
  plan.saved_outputs = py::cast<std::vector<std::string>>(data["saved_outputs"]);

  for (const auto& item : py::reinterpret_borrow<py::list>(data["nodes"])) {
    const auto node_data = py::reinterpret_borrow<py::dict>(item);
    NodePlan node;
    node.name = py::cast<std::string>(node_data["name"]);
    node.kind = parse_node_kind(py::cast<std::string>(node_data["kind"]));
    node.value_type = parse_value_type(py::cast<std::string>(node_data["value_type"]));
    node.dependencies = py::cast<std::vector<std::string>>(node_data["dependencies"]);
    if (node_data.contains("literal") && !node_data["literal"].is_none()) {
      node.literal = parse_literal(node_data["literal"]);
    }
    if (node_data.contains("program")) {
      node.program = parse_program(node_data["program"]);
    }
    if (node_data.contains("matrix")) {
      node.matrix = parse_matrix(node_data["matrix"]);
    }
    if (node_data.contains("projection")) {
      node.projection = parse_projection(node_data["projection"]);
    }
    if (node_data.contains("plugin_call")) {
      node.plugin_call = parse_plugin_call(node_data["plugin_call"]);
    }
    if (node_data.contains("diagonalization")) {
      node.diagonalization = parse_diagonalization(node_data["diagonalization"]);
    }
    if (node_data.contains("mixing_matrix")) {
      node.mixing_matrix = parse_mixing_matrix(node_data["mixing_matrix"]);
    }
    if (node_data.contains("constraint")) {
      node.constraint = parse_constraint(node_data["constraint"]);
    }
    if (node_data.contains("output")) {
      node.output = parse_output(node_data["output"]);
    }
    if (node_data.contains("metadata")) {
      const auto metadata = py::reinterpret_borrow<py::dict>(node_data["metadata"]);
      if (node.kind == NodeKind::TheoryCheck) {
        if (metadata.contains("fatal")) node.fatal = py::cast<bool>(metadata["fatal"]);
        if (metadata.contains("message") && !metadata["message"].is_none()) {
          node.failure_message = py::cast<std::string>(metadata["message"]);
        }
      }
    }
    plan.nodes.push_back(std::move(node));
  }

  return plan;
}

ScanParameter parse_scan_parameter(const py::handle& obj) {
  const auto data = py::reinterpret_borrow<py::dict>(obj);
  ScanParameter parameter;
  parameter.name = py::cast<std::string>(data["name"]);
  parameter.scanner_index = py::cast<std::size_t>(data["index"]);
  parameter.lower = py::cast<double>(data["lower"]);
  parameter.upper = py::cast<double>(data["upper"]);
  parameter.prior = py::cast<std::string>(data["prior"]);
  if (data.contains("min_abs") && !data["min_abs"].is_none()) {
    parameter.min_abs = py::cast<double>(data["min_abs"]);
  }
  if (data.contains("default") && !data["default"].is_none()) {
    parameter.default_value = py::cast<double>(data["default"]);
    parameter.has_default = true;
  }
  return parameter;
}

FixedParameter parse_fixed_parameter(const py::handle& obj) {
  const auto data = py::reinterpret_borrow<py::dict>(obj);
  FixedParameter parameter;
  parameter.name = py::cast<std::string>(data["name"]);
  parameter.value = parse_python_value(data["value"]);
  return parameter;
}

ScanConfig parse_scan_config(const py::dict& data) {
  ScanConfig config;
  config.engine = parse_runner_engine(py::cast<std::string>(data["engine"]));
  config.objective_mode =
      parse_objective_mode(py::cast<std::string>(data["objective_mode"]));
  config.run_directory = py::cast<std::string>(data["run_directory"]);
  config.model_name = py::cast<std::string>(data["model_name"]);
  config.model_version = py::cast<std::string>(data["model_version"]);
  config.framework_version = py::cast<std::string>(data["framework_version"]);
  config.run_id = py::cast<std::string>(data["run_id"]);
  config.timestamp_utc = py::cast<std::string>(data["timestamp_utc"]);
  config.maximize = py::cast<bool>(data["maximize"]);
  config.save_invalid_points = py::cast<bool>(data["save_invalid_points"]);
  config.seed = py::cast<unsigned int>(data["seed"]);
  config.save_every = py::cast<std::size_t>(data["save_every"]);
  config.invalid_objective = py::cast<double>(data["invalid_objective"]);
  config.max_evaluations = py::cast<std::size_t>(data["max_evaluations"]);
  config.max_init_attempts = py::cast<std::size_t>(data["max_init_attempts"]);
  config.population_size = py::cast<int>(data["population_size"]);
  config.max_generations = py::cast<int>(data["max_generations"]);
  config.convergence_threshold = py::cast<double>(data["convergence_threshold"]);
  config.convergence_steps = py::cast<int>(data["convergence_steps"]);
  config.verbose = py::cast<int>(data["verbose"]);
  config.selected_outputs = py::cast<std::vector<std::string>>(data["selected_outputs"]);
  config.likelihood_names = py::cast<std::vector<std::string>>(data["likelihood_names"]);
  config.parameter_order = py::cast<std::vector<std::string>>(data["parameter_order"]);
  config.raw_settings = py::cast<std::unordered_map<std::string, std::string>>(data["raw_settings"]);

  for (const auto& item : py::reinterpret_borrow<py::list>(data["scanned_parameters"])) {
    config.scanned_parameters.push_back(parse_scan_parameter(item));
  }
  for (const auto& item : py::reinterpret_borrow<py::list>(data["fixed_parameters"])) {
    config.fixed_parameters.push_back(parse_fixed_parameter(item));
  }
  return config;
}

py::dict point_result_to_python(const PointResult& result) {
  py::dict out;
  out["status"] = bsm::core::to_string(result.status);
  out["valid"] = result.valid;
  out["failure_reason"] = result.failure_reason;
  out["total_nll"] = result.total_nll;
  out["likelihood_terms"] = py::cast(result.likelihood_terms);
  py::dict outputs;
  for (const auto& [name, value] : result.outputs) {
    outputs[py::str(name)] = value_to_python(value);
  }
  out["outputs"] = std::move(outputs);
  out["flags"] = py::cast(result.flags);
  return out;
}

py::dict scan_record_to_python(const ScanPointRecord& record) {
  py::dict out;
  out["metric_value"] = record.metric_value;
  out["scanner_target"] = record.scanner_target;
  out["valid"] = record.valid;
  out["scanned_values"] = py::cast(record.scanned_values);
  out["point_result"] = point_result_to_python(record.point_result);
  return out;
}

py::dict summary_to_python(const RunSummary& summary) {
  py::dict out;
  out["evaluations"] = summary.evaluations;
  out["saved_points"] = summary.saved_points;
  out["valid_points"] = summary.valid_points;
  out["interrupted"] = summary.interrupted;
  out["has_best_point"] = summary.has_best_point;
  out["best_metric_value"] = summary.best_metric_value;
  out["best_scanner_target"] = summary.best_scanner_target;
  out["best_scanned_values"] = py::cast(summary.best_scanned_values);
  out["best_point_result"] = point_result_to_python(summary.best_point_result);

  py::dict failures;
  failures["ok"] = summary.failures.ok;
  failures["missing_input"] = summary.failures.missing_input;
  failures["invalid_point"] = summary.failures.invalid_point;
  failures["numerical_error"] = summary.failures.numerical_error;
  failures["evaluation_error"] = summary.failures.evaluation_error;
  failures["non_finite_objective"] = summary.failures.non_finite_objective;
  failures["by_reason"] = py::cast(summary.failures.by_reason);
  out["failures"] = std::move(failures);
  return out;
}

py::dict scan_run_result_to_python(const ScanRunResult& result) {
  py::dict out;
  out["run_directory"] = result.run_directory;
  out["points_path"] = result.points_path;
  out["metadata_path"] = result.metadata_path;
  out["best_fit_path"] = result.best_fit_path;
  out["summary_path"] = result.summary_path;
  out["summary"] = summary_to_python(result.summary);
  return out;
}

}  // namespace

PYBIND11_MODULE(_core, m) {
  py::class_<CompiledModel>(m, "NativeCompiledModel")
      .def("evaluate",
	           [](const CompiledModel& self, const py::dict& point) {
	             std::unordered_map<std::string, Value> inputs;
	             for (const auto& item : point) {
	               inputs.emplace(py::cast<std::string>(item.first),
	                              parse_python_value(item.second));
	             }
	             PointResult result = self.evaluate(inputs);
	             return point_result_to_python(result);
	           });

  m.def("build_model", [](const py::dict& plan) {
    return CompiledModel(parse_plan(plan));
  });

  m.def("has_diver_support", []() { return diver_support_enabled(); });
  m.def("has_plugin_support",
        [](const std::string& plugin) { return has_plugin_support(plugin); });

  m.def("evaluate_scan_point",
        [](const py::dict& plan_dict, const py::dict& request_dict,
           const std::vector<double>& point_vector) {
          const auto plan = parse_plan(plan_dict);
          const auto config = parse_scan_config(request_dict);
          const ParameterMapper mapper(config);
          const CompiledModel model(plan);
          const CompiledEvaluatorAdapter adapter(model, mapper, config);
          return scan_record_to_python(adapter.evaluate(point_vector.data(), point_vector.size()));
        });

  m.def("run_scan", [](const py::dict& plan_dict, const py::dict& request_dict) {
    const auto plan = parse_plan(plan_dict);
    const auto config = parse_scan_config(request_dict);
    py::gil_scoped_release release;
    auto result = bsm::core::scan::run_scan(plan, config);
    py::gil_scoped_acquire acquire;
    return scan_run_result_to_python(result);
  });
}

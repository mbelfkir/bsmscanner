#include "bsm/core/scan/adapter.hpp"

#include <cmath>
#include <limits>

namespace bsm::core::scan {

CompiledEvaluatorAdapter::CompiledEvaluatorAdapter(const CompiledModel& model,
                                                   const ParameterMapper& mapper,
                                                   const ScanConfig& config)
    : model_(model), mapper_(mapper), config_(config) {}

ScanPointRecord CompiledEvaluatorAdapter::evaluate(const double* values,
                                                   std::size_t n) const {
  ScanPointRecord record;
  record.scanned_values.assign(values, values + n);

  if (n != mapper_.scanned_parameters().size()) {
    record.point_result.status = PointStatus::EvaluationError;
    record.point_result.valid = false;
    record.point_result.failure_reason = "Scanner dimension does not match scanned parameter list.";
    record.metric_value = config_.invalid_objective;
    record.scanner_target = config_.invalid_objective;
    return record;
  }

  for (std::size_t i = 0; i < n; ++i) {
    const auto& parameter = mapper_.scanned_parameters()[i];
    if (!std::isfinite(values[i]) || values[i] < parameter.lower || values[i] > parameter.upper) {
      record.point_result.status = PointStatus::Ok;
      record.point_result.valid = false;
      record.point_result.failure_reason = "parameter_out_of_range: " + parameter.name;
      record.metric_value = config_.invalid_objective;
      record.scanner_target = config_.invalid_objective;
      return record;
    }
  }

  std::unordered_map<std::string, Value> inputs = mapper_.base_inputs();
  mapper_.apply_scanner_point(values, n, inputs);
  record.point_result = model_.evaluate(inputs);

  bool valid = record.point_result.valid &&
               (record.point_result.status == PointStatus::Ok) &&
               std::isfinite(record.point_result.total_nll);

  double metric_value = valid ? record.point_result.total_nll : config_.invalid_objective;
  if (valid && config_.objective_mode == ObjectiveMode::NegativeLogPosterior) {
    const double prior_term = mapper_.negative_log_prior(values, n);
    if (std::isfinite(prior_term)) {
      metric_value += prior_term;
    } else {
      valid = false;
      record.point_result.valid = false;
      if (record.point_result.failure_reason.empty()) {
        record.point_result.failure_reason = "likelihood_input_invalid: prior";
      }
      metric_value = config_.invalid_objective;
    }
  }

  if (!std::isfinite(metric_value)) {
    valid = false;
    record.point_result.valid = false;
    if (record.point_result.failure_reason.empty()) {
      record.point_result.failure_reason = "non_finite_objective";
    }
    metric_value = config_.invalid_objective;
  }

  record.valid = valid;
  record.point_result.valid = valid;
  if (!valid && record.point_result.failure_reason.empty()) {
    record.point_result.failure_reason = "invalid_penalty_assigned";
  }
  record.metric_value = metric_value;
  record.scanner_target = valid
                              ? (config_.maximize ? -metric_value : metric_value)
                              : config_.invalid_objective;
  return record;
}

}  // namespace bsm::core::scan

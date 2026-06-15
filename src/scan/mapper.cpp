#include "bsm/core/scan/mapper.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <unordered_set>

namespace bsm::core::scan {

ParameterMapper::ParameterMapper(ScanConfig config) {
  scanned_parameters_ = std::move(config.scanned_parameters);
  parameter_order_ = std::move(config.parameter_order);
  std::sort(scanned_parameters_.begin(), scanned_parameters_.end(),
            [](const ScanParameter& lhs, const ScanParameter& rhs) {
              return lhs.scanner_index < rhs.scanner_index;
            });

  lower_bounds_.reserve(scanned_parameters_.size());
  upper_bounds_.reserve(scanned_parameters_.size());

  for (std::size_t i = 0; i < scanned_parameters_.size(); ++i) {
    const auto& parameter = scanned_parameters_[i];
    if (parameter.scanner_index != i) {
      throw std::runtime_error(
          "Scanned parameters must use contiguous scanner indices starting at zero.");
    }
    if (!(parameter.lower < parameter.upper)) {
      throw std::runtime_error("Invalid bounds for scanned parameter: " + parameter.name);
    }
    if (parameter.prior == "signed_log") {
      if (!(parameter.lower < 0.0 && parameter.upper > 0.0)) {
        throw std::runtime_error(
            "Signed-log prior requires bounds that straddle zero: " + parameter.name);
      }
      const double max_abs = std::max(std::abs(parameter.lower), std::abs(parameter.upper));
      if (!(parameter.min_abs > 0.0 && parameter.min_abs < max_abs) ||
          !std::isfinite(parameter.min_abs)) {
        throw std::runtime_error(
            "Signed-log prior requires 0 < min_abs < max(abs(bounds)): " + parameter.name);
      }
    }
    lower_bounds_.push_back(parameter.lower);
    upper_bounds_.push_back(parameter.upper);
    if (parameter.has_default) {
      base_inputs_[parameter.name] = parameter.default_value;
    } else {
      base_inputs_[parameter.name] = parameter.lower;
    }
  }

  for (const auto& fixed : config.fixed_parameters) {
    base_inputs_[fixed.name] = fixed.value;
  }

  if (parameter_order_.empty()) {
    parameter_order_.reserve(scanned_parameters_.size() + config.fixed_parameters.size());
    for (const auto& parameter : scanned_parameters_) {
      parameter_order_.push_back(parameter.name);
    }
    for (const auto& fixed : config.fixed_parameters) {
      parameter_order_.push_back(fixed.name);
    }
  }

  std::unordered_set<std::string> declared_order;
  for (const auto& name : parameter_order_) {
    if (!declared_order.insert(name).second) {
      throw std::runtime_error("Duplicate parameter name in scan parameter ordering: " + name);
    }
  }
  for (const auto& parameter : scanned_parameters_) {
    if (!declared_order.contains(parameter.name)) {
      throw std::runtime_error(
          "Scanned parameter missing from declared parameter ordering: " + parameter.name);
    }
  }
  for (const auto& fixed : config.fixed_parameters) {
    if (!declared_order.contains(fixed.name)) {
      throw std::runtime_error(
          "Fixed parameter missing from declared parameter ordering: " + fixed.name);
    }
  }
}

void ParameterMapper::apply_scanner_point(
    const double* values,
    std::size_t n,
    std::unordered_map<std::string, Value>& inputs) const {
  if (n != scanned_parameters_.size()) {
    throw std::runtime_error("Scanner dimension does not match scanned parameter list.");
  }

  for (std::size_t i = 0; i < n; ++i) {
    inputs[scanned_parameters_[i].name] = values[i];
  }
}

double ParameterMapper::negative_log_prior(const double* values, std::size_t n) const {
  if (n != scanned_parameters_.size()) {
    throw std::runtime_error("Scanner dimension does not match scanned parameter list.");
  }

  double result = 0.0;
  for (std::size_t i = 0; i < n; ++i) {
    const auto& parameter = scanned_parameters_[i];
    if (parameter.prior == "flat") {
      const double width = parameter.upper - parameter.lower;
      if (!(width > 0.0) || !std::isfinite(width)) {
        return std::numeric_limits<double>::infinity();
      }
      result += std::log(width);
    } else if (parameter.prior == "log") {
      if (!(values[i] > 0.0) || !std::isfinite(values[i])) {
        return std::numeric_limits<double>::infinity();
      }
      const double norm = std::log(parameter.upper / parameter.lower);
      if (!(norm > 0.0) || !std::isfinite(norm)) {
        return std::numeric_limits<double>::infinity();
      }
      result += std::log(values[i]) + std::log(norm);
    } else if (parameter.prior == "signed_log") {
      const double abs_value = std::abs(values[i]);
      if (!(abs_value >= parameter.min_abs) || !std::isfinite(abs_value)) {
        return std::numeric_limits<double>::infinity();
      }
      const double neg_span = std::abs(parameter.lower) > parameter.min_abs
                                  ? std::log(std::abs(parameter.lower) / parameter.min_abs)
                                  : 0.0;
      const double pos_span = parameter.upper > parameter.min_abs
                                  ? std::log(parameter.upper / parameter.min_abs)
                                  : 0.0;
      const double norm = neg_span + pos_span;
      if (!(norm > 0.0) || !std::isfinite(norm)) {
        return std::numeric_limits<double>::infinity();
      }
      result += std::log(abs_value) + std::log(norm);
    } else if (parameter.prior != "fixed") {
      throw std::runtime_error("Unsupported prior kind for scanned parameter: " +
                               parameter.prior);
    }
  }
  return result;
}

}  // namespace bsm::core::scan

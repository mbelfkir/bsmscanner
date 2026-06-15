#pragma once

#include "bsm/core/scan/config.hpp"

#include <unordered_map>
#include <vector>

namespace bsm::core::scan {

class ParameterMapper {
 public:
  explicit ParameterMapper(ScanConfig config);

  std::size_t dimension() const noexcept { return scanned_parameters_.size(); }

  const std::vector<ScanParameter>& scanned_parameters() const noexcept {
    return scanned_parameters_;
  }

  const std::vector<double>& lower_bounds() const noexcept { return lower_bounds_; }
  const std::vector<double>& upper_bounds() const noexcept { return upper_bounds_; }
  const std::vector<std::string>& parameter_order() const noexcept { return parameter_order_; }
  const std::unordered_map<std::string, Value>& base_inputs() const noexcept {
    return base_inputs_;
  }

  void apply_scanner_point(const double* values,
                           std::size_t n,
                           std::unordered_map<std::string, Value>& inputs) const;

  double negative_log_prior(const double* values, std::size_t n) const;

 private:
  std::vector<ScanParameter> scanned_parameters_;
  std::vector<double> lower_bounds_;
  std::vector<double> upper_bounds_;
  std::vector<std::string> parameter_order_;
  std::unordered_map<std::string, Value> base_inputs_;
};

}  // namespace bsm::core::scan


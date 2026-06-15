#pragma once

#include "bsm/core/evaluator.hpp"
#include "bsm/core/scan/config.hpp"
#include "bsm/core/scan/mapper.hpp"

#include <cstddef>
#include <string>
#include <unordered_map>
#include <vector>

namespace bsm::core::scan {

struct ScanPointRecord {
  PointResult point_result;
  std::vector<double> scanned_values;
  double metric_value = 0.0;
  double scanner_target = 0.0;
  bool valid = false;
};

class CompiledEvaluatorAdapter {
 public:
  CompiledEvaluatorAdapter(const CompiledModel& model,
                           const ParameterMapper& mapper,
                           const ScanConfig& config);

  ScanPointRecord evaluate(const double* values, std::size_t n) const;

 private:
  const CompiledModel& model_;
  const ParameterMapper& mapper_;
  const ScanConfig& config_;
};

}  // namespace bsm::core::scan


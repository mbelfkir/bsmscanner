#pragma once

#include "bsm/core/types.hpp"

#include <string>
#include <unordered_map>
#include <vector>

namespace bsm::core {

enum class PointStatus {
  Ok,
  MissingInput,
  InvalidPoint,
  NumericalError,
  EvaluationError,
};

std::string to_string(PointStatus status);

struct PointResult {
  PointStatus status = PointStatus::Ok;
  bool valid = true;
  std::string failure_reason;
  double total_nll = 0.0;
  std::unordered_map<std::string, double> likelihood_terms;
  std::unordered_map<std::string, Value> outputs;
  std::vector<std::string> flags;
};

}  // namespace bsm::core

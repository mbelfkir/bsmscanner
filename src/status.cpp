#include "bsm/core/status.hpp"

namespace bsm::core {

std::string to_string(PointStatus status) {
  switch (status) {
    case PointStatus::Ok:
      return "ok";
    case PointStatus::MissingInput:
      return "missing_input";
    case PointStatus::InvalidPoint:
      return "invalid_point";
    case PointStatus::NumericalError:
      return "numerical_error";
    case PointStatus::EvaluationError:
      return "evaluation_error";
  }
  return "unknown";
}

}  // namespace bsm::core


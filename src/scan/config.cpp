#include "bsm/core/scan/config.hpp"

#include <stdexcept>

namespace bsm::core::scan {

RunnerEngine parse_runner_engine(const std::string& value) {
  if (value == "diver") {
    return RunnerEngine::Diver;
  }
  if (value == "serial_random") {
    return RunnerEngine::SerialRandom;
  }
  throw std::runtime_error("Unknown scan engine: " + value);
}

ObjectiveMode parse_objective_mode(const std::string& value) {
  if (value == "nll") {
    return ObjectiveMode::NegativeLogLikelihood;
  }
  if (value == "posterior_nll") {
    return ObjectiveMode::NegativeLogPosterior;
  }
  throw std::runtime_error("Unknown scan objective mode: " + value);
}

std::string to_string(RunnerEngine engine) {
  switch (engine) {
    case RunnerEngine::Diver:
      return "diver";
    case RunnerEngine::SerialRandom:
      return "serial_random";
  }
  return "unknown";
}

std::string to_string(ObjectiveMode mode) {
  switch (mode) {
    case ObjectiveMode::NegativeLogLikelihood:
      return "nll";
    case ObjectiveMode::NegativeLogPosterior:
      return "posterior_nll";
  }
  return "unknown";
}

}  // namespace bsm::core::scan


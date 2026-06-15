#pragma once

#include "bsm/core/types.hpp"

#include <cstddef>
#include <string>
#include <unordered_map>
#include <vector>

namespace bsm::core::scan {

enum class RunnerEngine {
  Diver,
  SerialRandom,
};

enum class ObjectiveMode {
  NegativeLogLikelihood,
  NegativeLogPosterior,
};

struct ScanParameter {
  std::string name;
  std::size_t scanner_index = 0;
  double lower = 0.0;
  double upper = 0.0;
  std::string prior;
  double min_abs = 1.0e-12;
  double default_value = 0.0;
  bool has_default = false;
};

struct FixedParameter {
  std::string name;
  Value value;
};

struct ScanConfig {
  RunnerEngine engine = RunnerEngine::Diver;
  ObjectiveMode objective_mode = ObjectiveMode::NegativeLogLikelihood;

  std::string model_name;
  std::string model_version;
  std::string framework_version;
  std::string run_id;
  std::string run_directory;
  std::string timestamp_utc;

  unsigned int seed = 12345U;
  std::size_t save_every = 1000U;
  std::size_t max_evaluations = 0U;
  std::size_t max_init_attempts = 30000U;
  int population_size = 0;
  int max_generations = 0;
  int convergence_steps = 20;
  int verbose = 1;

  double invalid_objective = 1.0e300;
  double convergence_threshold = 1.0e-3;

  bool maximize = false;
  bool save_invalid_points = false;

  std::vector<ScanParameter> scanned_parameters;
  std::vector<FixedParameter> fixed_parameters;
  std::vector<std::string> selected_outputs;
  std::vector<std::string> likelihood_names;
  std::vector<std::string> parameter_order;
  std::unordered_map<std::string, std::string> raw_settings;
};

RunnerEngine parse_runner_engine(const std::string& value);
ObjectiveMode parse_objective_mode(const std::string& value);
std::string to_string(RunnerEngine engine);
std::string to_string(ObjectiveMode mode);

}  // namespace bsm::core::scan

#include "bsm/core/scan/runner.hpp"

#include "bsm/core/status.hpp"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <chrono>
#include <csignal>
#include <limits>
#include <memory>
#include <random>
#include <stdexcept>

#ifdef BSM_SCANNER_ENABLE_DIVER
#include "diver.hpp"
#endif

namespace bsm::core::scan {

namespace {

std::atomic<bool> g_stop_requested{false};

void signal_handler(int) { g_stop_requested.store(true); }

class SignalGuard {
 public:
  SignalGuard() : previous_(std::signal(SIGINT, signal_handler)) { g_stop_requested.store(false); }
  ~SignalGuard() { std::signal(SIGINT, previous_); }

 private:
  using Handler = void (*)(int);
  Handler previous_;
};

#ifdef BSM_SCANNER_ENABLE_DIVER
struct DiverContext {
  RunController* controller = nullptr;
};

double diver_objective(double params[],
                       const int param_dim,
                       int& fcall,
                       bool& quit,
                       const bool validvector,
                       void*& context) {
  auto* diver_context = static_cast<DiverContext*>(context);
  bool should_quit = false;
  double value = diver_context->controller->config().invalid_objective;
  if (validvector) {
    value = diver_context->controller->evaluate_scanner_point(
        params, static_cast<std::size_t>(param_dim), &should_quit);
  }
  quit = should_quit;
  fcall += 1;
  return value;
}
#endif

std::unique_ptr<ScanEngine> make_engine(RunnerEngine engine) {
  switch (engine) {
    case RunnerEngine::Diver:
      return std::make_unique<DiverRunner>();
    case RunnerEngine::SerialRandom:
      return std::make_unique<SerialRandomRunner>();
  }
  throw std::runtime_error("Unknown scan engine.");
}

double draw_signed_log(std::mt19937_64& generator, const ScanParameter& parameter) {
  const double min_abs = parameter.min_abs;
  const double neg_span = std::abs(parameter.lower) > min_abs
                              ? std::log(std::abs(parameter.lower) / min_abs)
                              : 0.0;
  const double pos_span = parameter.upper > min_abs
                              ? std::log(parameter.upper / min_abs)
                              : 0.0;
  const double total_span = neg_span + pos_span;
  if (!(total_span > 0.0) || !std::isfinite(total_span)) {
    throw std::runtime_error("Signed-log parameter has no logarithmic support: " +
                             parameter.name);
  }
  std::uniform_real_distribution<double> unit(0.0, 1.0);
  const double u = unit(generator);
  const double cutoff = neg_span / total_span;
  if (u < cutoff) {
    const double local = cutoff > 0.0 ? u / cutoff : 0.0;
    return -std::exp(std::log(std::abs(parameter.lower)) - local * neg_span);
  }
  const double local = cutoff < 1.0 ? (u - cutoff) / (1.0 - cutoff) : 0.0;
  return std::exp(std::log(min_abs) + local * pos_span);
}

}  // namespace

RunController::RunController(ScanConfig config,
                             CompiledModel compiled_model,
                             ParameterMapper mapper)
    : config_(std::move(config)),
      compiled_model_(std::move(compiled_model)),
      mapper_(std::move(mapper)),
      writer_(config_, mapper_),
      adapter_(compiled_model_, mapper_, config_) {
  summary_.best_metric_value = config_.invalid_objective;
  summary_.best_scanner_target = config_.invalid_objective;
}

RunController::~RunController() { writer_.flush(); }

bool RunController::stop_requested() const noexcept { return g_stop_requested.load(); }

double RunController::evaluate_scanner_point(const double* values,
                                             std::size_t n,
                                             bool* should_quit) {
  ScanPointRecord record = adapter_.evaluate(values, n);
  const double scanner_target = record.scanner_target;
  consume_record(std::move(record));
  const bool stop = stop_requested();
  if (should_quit != nullptr) {
    *should_quit = stop;
  }
  return scanner_target;
}

ScanPointRecord RunController::evaluate_record(const std::vector<double>& values) const {
  return adapter_.evaluate(values.data(), values.size());
}

void RunController::consume_record(ScanPointRecord record) {
  summary_.evaluations += 1U;

  switch (record.point_result.status) {
    case PointStatus::Ok:
      summary_.failures.ok += 1U;
      break;
    case PointStatus::MissingInput:
      summary_.failures.missing_input += 1U;
      break;
    case PointStatus::InvalidPoint:
      summary_.failures.invalid_point += 1U;
      break;
    case PointStatus::NumericalError:
      summary_.failures.numerical_error += 1U;
      break;
    case PointStatus::EvaluationError:
      summary_.failures.evaluation_error += 1U;
      break;
  }
  if (!record.valid && record.point_result.status == PointStatus::Ok) {
    summary_.failures.invalid_point += 1U;
  }

  if (!record.point_result.failure_reason.empty()) {
    summary_.failures.by_reason[record.point_result.failure_reason] += 1U;
  }

  if (!std::isfinite(record.metric_value)) {
    summary_.failures.non_finite_objective += 1U;
  }

  if (record.valid) {
    summary_.valid_points += 1U;
    if (!summary_.has_best_point || record.scanner_target < summary_.best_scanner_target) {
      summary_.has_best_point = true;
      summary_.best_metric_value = record.metric_value;
      summary_.best_scanner_target = record.scanner_target;
      summary_.best_scanned_values = record.scanned_values;
      summary_.best_point_result = record.point_result;
    }
  }

  if (record.valid || config_.save_invalid_points) {
    writer_.write_point(summary_.evaluations, record);
    summary_.saved_points += 1U;
  }

  if (config_.save_every > 0U && (summary_.evaluations % config_.save_every) == 0U) {
    writer_.flush();
  }
}

ScanRunResult RunController::finalize() {
  summary_.interrupted = stop_requested();
  writer_.write_best_fit(summary_);
  writer_.write_summary(summary_);
  writer_.flush();

  return {
      config_.run_directory,
      writer_.points_path(),
      writer_.metadata_path(),
      writer_.best_fit_path(),
      writer_.summary_path(),
      summary_,
  };
}

void SerialRandomRunner::run(RunController& controller) {
  const auto& mapper = controller.mapper();
  const std::size_t dimension = mapper.dimension();
  if (dimension == 0U) {
    throw std::runtime_error("No scanned parameters were provided.");
  }

  std::mt19937_64 generator(controller.config().seed);
  std::vector<std::uniform_real_distribution<double>> distributions;
  distributions.reserve(dimension);
  const auto& parameters = mapper.scanned_parameters();
  for (std::size_t i = 0; i < dimension; ++i) {
    distributions.emplace_back(mapper.lower_bounds()[i], mapper.upper_bounds()[i]);
  }

  std::vector<double> point(dimension, 0.0);
  for (std::size_t evaluation = 0; evaluation < controller.config().max_evaluations;
       ++evaluation) {
    if (controller.stop_requested()) {
      break;
    }
    for (std::size_t i = 0; i < dimension; ++i) {
      const auto& parameter = parameters[i];
      if (parameter.prior == "log") {
        std::uniform_real_distribution<double> log_distribution(
            std::log(parameter.lower), std::log(parameter.upper));
        point[i] = std::exp(log_distribution(generator));
      } else if (parameter.prior == "signed_log") {
        point[i] = draw_signed_log(generator, parameter);
      } else {
        point[i] = distributions[i](generator);
      }
    }
    bool should_quit = false;
    controller.evaluate_scanner_point(point.data(), point.size(), &should_quit);
    if (should_quit) {
      break;
    }
  }
}

void DiverRunner::run(RunController& controller) {
#ifndef BSM_SCANNER_ENABLE_DIVER
  throw std::runtime_error(
      "This build does not include Diver support. Reconfigure with "
      "-DBSM_SCANNER_BUILD_DIVER=ON and provide the Diver headers/library.");
#else
  const auto& mapper = controller.mapper();
  const int dimension = static_cast<int>(mapper.dimension());
  if (dimension == 0) {
    throw std::runtime_error("No scanned parameters were provided.");
  }

  const int population_size =
      controller.config().population_size > 0 ? controller.config().population_size
                                              : std::max(20, 10 * dimension);
  const int max_generations =
      controller.config().max_generations > 0
          ? controller.config().max_generations
          : std::max(1,
                     static_cast<int>(std::ceil(
                         static_cast<double>(controller.config().max_evaluations) /
                         static_cast<double>(population_size))));

  std::vector<double> lower = mapper.lower_bounds();
  std::vector<double> upper = mapper.upper_bounds();
  std::vector<double> best_fit(static_cast<std::size_t>(dimension), 0.0);

  constexpr int n_derived = 0;
  double best_fit_derived[1] = {0.0};
  constexpr int n_discrete = 0;
  int discrete[1] = {0};
  constexpr bool partition_discrete = false;
  constexpr int max_civilizations = 1;
  constexpr int n_f = 2;
  const double f[n_f] = {0.5, 0.9};
  const double cr = 0.9;
  const double lambda = 0.4;
  const bool current = false;
  const bool expon = false;
  const int boundary = 3;
  const bool jde = true;
  const bool lambda_jde = true;
  const bool remove_duplicates = true;
  const bool do_bayesian = false;
  auto* prior = static_cast<double (*)(const double[], const int, void*&)>(nullptr);
  const double max_node_population = 1.9;
  const double z_tolerance = 1.0e-3;
  const bool resume = false;
  const bool disable_io = true;
  const bool output_raw = false;
  const bool output_sam = false;
  const int init_pop_strategy = 1;
  const bool discard_unfit_points = false;
  const int save_count =
      static_cast<int>(std::max<std::size_t>(controller.config().save_every, 1U));

  const std::string diver_output_prefix = controller.config().run_directory + "/diver";
  DiverContext context{&controller};
  void* raw_context = &context;

  (void)cdiver(diver_objective, dimension, lower.data(), upper.data(),
               diver_output_prefix.c_str(), n_derived, best_fit.data(),
               best_fit_derived, n_discrete, discrete, partition_discrete,
               max_civilizations, max_generations, population_size, n_f, f, cr, lambda,
               current, expon, boundary, jde, lambda_jde,
               controller.config().convergence_threshold,
               controller.config().convergence_steps, remove_duplicates, do_bayesian,
               prior, max_node_population, z_tolerance, save_count, resume,
               disable_io, output_raw, output_sam, init_pop_strategy,
               discard_unfit_points, static_cast<int>(controller.config().max_init_attempts),
               controller.config().invalid_objective,
               static_cast<int>(controller.config().seed), raw_context,
               controller.config().verbose);
#endif
}

ScanRunResult run_scan(CompiledModelPlan plan, ScanConfig config) {
  SignalGuard signal_guard;
  ParameterMapper mapper(config);
  CompiledModel compiled_model(std::move(plan));
  RunController controller(std::move(config), std::move(compiled_model), std::move(mapper));
  auto engine = make_engine(controller.config().engine);
  engine->run(controller);
  return controller.finalize();
}

bool diver_support_enabled() {
#ifdef BSM_SCANNER_ENABLE_DIVER
  return true;
#else
  return false;
#endif
}

}  // namespace bsm::core::scan

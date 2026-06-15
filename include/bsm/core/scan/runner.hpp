#pragma once

#include "bsm/core/scan/adapter.hpp"
#include "bsm/core/scan/result_writer.hpp"

#include <atomic>
#include <cstddef>
#include <memory>
#include <vector>

namespace bsm::core::scan {

class RunController {
 public:
  RunController(ScanConfig config, CompiledModel compiled_model, ParameterMapper mapper);
  ~RunController();

  double evaluate_scanner_point(const double* values, std::size_t n, bool* should_quit);
  ScanPointRecord evaluate_record(const std::vector<double>& values) const;
  ScanRunResult finalize();

  const ScanConfig& config() const noexcept { return config_; }
  const ParameterMapper& mapper() const noexcept { return mapper_; }
  bool stop_requested() const noexcept;

 private:
  void consume_record(ScanPointRecord record);

  ScanConfig config_;
  CompiledModel compiled_model_;
  ParameterMapper mapper_;
  ResultWriter writer_;
  CompiledEvaluatorAdapter adapter_;
  RunSummary summary_;
};

class ScanEngine {
 public:
  virtual ~ScanEngine() = default;
  virtual void run(RunController& controller) = 0;
};

class SerialRandomRunner final : public ScanEngine {
 public:
  void run(RunController& controller) override;
};

class DiverRunner final : public ScanEngine {
 public:
  void run(RunController& controller) override;
};

ScanRunResult run_scan(CompiledModelPlan plan, ScanConfig config);
bool diver_support_enabled();

}  // namespace bsm::core::scan

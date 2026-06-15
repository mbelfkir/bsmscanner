#pragma once

#include "bsm/core/scan/adapter.hpp"
#include "bsm/core/scan/config.hpp"
#include "bsm/core/status.hpp"

#include <cstddef>
#include <fstream>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace bsm::core::scan {

struct FailureCounters {
  std::size_t ok = 0U;
  std::size_t missing_input = 0U;
  std::size_t invalid_point = 0U;
  std::size_t numerical_error = 0U;
  std::size_t evaluation_error = 0U;
  std::size_t non_finite_objective = 0U;
  std::unordered_map<std::string, std::size_t> by_reason;
};

struct RunSummary {
  std::size_t evaluations = 0U;
  std::size_t saved_points = 0U;
  std::size_t valid_points = 0U;
  bool interrupted = false;

  double best_metric_value = 0.0;
  double best_scanner_target = 0.0;
  bool has_best_point = false;

  std::vector<double> best_scanned_values;
  PointResult best_point_result;
  FailureCounters failures;
};

struct ScanRunResult {
  std::string run_directory;
  std::string points_path;
  std::string metadata_path;
  std::string best_fit_path;
  std::string summary_path;
  RunSummary summary;
};

class ResultWriter {
 public:
  ResultWriter(const ScanConfig& config, const ParameterMapper& mapper);
  ~ResultWriter();

  void write_metadata();
  void write_point(std::size_t evaluation_id, const ScanPointRecord& record);
  void write_best_fit(const RunSummary& summary);
  void write_summary(const RunSummary& summary);
  void flush();

  const std::string& points_path() const noexcept { return points_path_; }
  const std::string& metadata_path() const noexcept { return metadata_path_; }
  const std::string& best_fit_path() const noexcept { return best_fit_path_; }
  const std::string& summary_path() const noexcept { return summary_path_; }

 private:
  std::string escape_csv(const std::string& value) const;
  std::string value_to_csv(const Value& value) const;
  std::string value_to_json(const Value& value) const;
  std::string json_escape(const std::string& value) const;
  void write_csv_header();

  ScanConfig config_;
  std::vector<ScanParameter> scanned_parameters_;
  std::ofstream points_stream_;
  std::string points_path_;
  std::string metadata_path_;
  std::string best_fit_path_;
  std::string summary_path_;
};

}  // namespace bsm::core::scan

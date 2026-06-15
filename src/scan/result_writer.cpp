#include "bsm/core/scan/result_writer.hpp"

#include "bsm/core/status.hpp"

#include <Eigen/Core>

#include <algorithm>
#include <filesystem>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace bsm::core::scan {

namespace {

std::string complex_to_string(const std::complex<double>& value) {
  std::ostringstream buffer;
  buffer << value.real();
  if (value.imag() >= 0.0) {
    buffer << "+";
  }
  buffer << value.imag() << "j";
  return buffer.str();
}

std::string complex_to_json(const std::complex<double>& value) {
  return "{\"re\": " + std::to_string(value.real()) + ", \"im\": " +
         std::to_string(value.imag()) + "}";
}

template <typename VectorType, typename Formatter>
std::string vector_to_string(const VectorType& values, Formatter formatter) {
  std::ostringstream buffer;
  buffer << "[";
  for (Eigen::Index i = 0; i < values.size(); ++i) {
    if (i) buffer << ", ";
    buffer << formatter(values[i]);
  }
  buffer << "]";
  return buffer.str();
}

template <typename MatrixType, typename Formatter>
std::string matrix_to_string(const MatrixType& values, Formatter formatter) {
  std::ostringstream buffer;
  buffer << "[";
  for (Eigen::Index row = 0; row < values.rows(); ++row) {
    if (row) buffer << ", ";
    buffer << "[";
    for (Eigen::Index col = 0; col < values.cols(); ++col) {
      if (col) buffer << ", ";
      buffer << formatter(values(row, col));
    }
    buffer << "]";
  }
  buffer << "]";
  return buffer.str();
}

template <typename VectorType>
std::string real_vector_to_string(const VectorType& values) {
  return vector_to_string(values, [](const auto& entry) { return std::to_string(entry); });
}

template <typename MatrixType>
std::string real_matrix_to_string(const MatrixType& values) {
  return matrix_to_string(values, [](const auto& entry) { return std::to_string(entry); });
}

template <typename VectorType>
std::string complex_vector_to_json(const VectorType& values) {
  return vector_to_string(values, [](const auto& entry) { return complex_to_json(entry); });
}

template <typename MatrixType>
std::string complex_matrix_to_json(const MatrixType& values) {
  return matrix_to_string(values, [](const auto& entry) { return complex_to_json(entry); });
}

template <typename VectorType>
std::string complex_vector_to_csv(const VectorType& values) {
  return vector_to_string(values, [](const auto& entry) { return complex_to_string(entry); });
}

template <typename MatrixType>
std::string complex_matrix_to_csv(const MatrixType& values) {
  return matrix_to_string(values, [](const auto& entry) { return complex_to_string(entry); });
}

}  // namespace

ResultWriter::ResultWriter(const ScanConfig& config, const ParameterMapper& mapper)
    : config_(config), scanned_parameters_(mapper.scanned_parameters()) {
  std::filesystem::create_directories(config_.run_directory);

  points_path_ = config_.run_directory + "/points.csv";
  metadata_path_ = config_.run_directory + "/metadata.json";
  best_fit_path_ = config_.run_directory + "/best_fit.json";
  summary_path_ = config_.run_directory + "/summary.json";

  points_stream_.open(points_path_, std::ios::out);
  if (!points_stream_.is_open()) {
    throw std::runtime_error("Failed to open scan output file: " + points_path_);
  }

  write_csv_header();
  write_metadata();
}

ResultWriter::~ResultWriter() { flush(); }

void ResultWriter::write_csv_header() {
  points_stream_ << "evaluation,status,valid,failure_reason,scanner_target,metric_value,total_nll";
  for (const auto& parameter : scanned_parameters_) {
    points_stream_ << ",param::" << parameter.name;
  }
  for (const auto& output : config_.selected_outputs) {
    points_stream_ << ",output::" << output;
  }
  for (const auto& likelihood : config_.likelihood_names) {
    points_stream_ << ",likelihood::" << likelihood;
  }
  points_stream_ << "\n";
}

void ResultWriter::write_metadata() {
  std::ofstream stream(metadata_path_, std::ios::out);
  if (!stream.is_open()) {
    throw std::runtime_error("Failed to open metadata file: " + metadata_path_);
  }

  stream << "{\n";
  stream << "  \"model_name\": " << json_escape(config_.model_name) << ",\n";
  stream << "  \"model_version\": " << json_escape(config_.model_version) << ",\n";
  stream << "  \"framework_version\": " << json_escape(config_.framework_version) << ",\n";
  stream << "  \"run_id\": " << json_escape(config_.run_id) << ",\n";
  stream << "  \"timestamp_utc\": " << json_escape(config_.timestamp_utc) << ",\n";
  stream << "  \"engine\": " << json_escape(to_string(config_.engine)) << ",\n";
  stream << "  \"objective_mode\": " << json_escape(to_string(config_.objective_mode))
         << ",\n";
  stream << "  \"maximize\": " << (config_.maximize ? "true" : "false") << ",\n";
  stream << "  \"seed\": " << config_.seed << ",\n";
  stream << "  \"save_every\": " << config_.save_every << ",\n";
  stream << "  \"parameter_order\": [";
  for (std::size_t i = 0; i < config_.parameter_order.size(); ++i) {
    if (i) stream << ", ";
    stream << json_escape(config_.parameter_order[i]);
  }
  stream << "],\n";
  stream << "  \"scanned_parameters\": [\n";
  for (std::size_t i = 0; i < scanned_parameters_.size(); ++i) {
    const auto& parameter = scanned_parameters_[i];
    stream << "    {\"name\": " << json_escape(parameter.name)
           << ", \"scanner_index\": " << parameter.scanner_index
           << ", \"lower\": " << parameter.lower
           << ", \"upper\": " << parameter.upper
           << ", \"prior\": " << json_escape(parameter.prior)
           << ", \"min_abs\": " << parameter.min_abs << "}";
    if (i + 1 != scanned_parameters_.size()) stream << ",";
    stream << "\n";
  }
  stream << "  ],\n";
  stream << "  \"fixed_parameters\": [\n";
  for (std::size_t i = 0; i < config_.fixed_parameters.size(); ++i) {
    const auto& fixed = config_.fixed_parameters[i];
    stream << "    {\"name\": " << json_escape(fixed.name)
           << ", \"value\": " << value_to_json(fixed.value) << "}";
    if (i + 1 != config_.fixed_parameters.size()) stream << ",";
    stream << "\n";
  }
  stream << "  ],\n";
  stream << "  \"selected_outputs\": [";
  for (std::size_t i = 0; i < config_.selected_outputs.size(); ++i) {
    if (i) stream << ", ";
    stream << json_escape(config_.selected_outputs[i]);
  }
  stream << "],\n";
  stream << "  \"raw_settings\": {\n";
  std::vector<std::pair<std::string, std::string>> settings(config_.raw_settings.begin(),
                                                            config_.raw_settings.end());
  std::sort(settings.begin(), settings.end(),
            [](const auto& lhs, const auto& rhs) { return lhs.first < rhs.first; });
  for (std::size_t i = 0; i < settings.size(); ++i) {
    const auto& [key, value] = settings[i];
    stream << "    " << json_escape(key) << ": " << json_escape(value);
    if (i + 1U != settings.size()) stream << ",";
    stream << "\n";
  }
  stream << "  }\n";
  stream << "}\n";
}

void ResultWriter::write_point(std::size_t evaluation_id, const ScanPointRecord& record) {
  points_stream_ << evaluation_id << "," << escape_csv(to_string(record.point_result.status))
                 << "," << (record.valid ? "true" : "false") << ","
                 << escape_csv(record.point_result.failure_reason) << ","
                 << record.scanner_target << "," << record.metric_value << ","
                 << record.point_result.total_nll;

  for (double value : record.scanned_values) {
    points_stream_ << "," << value;
  }

  for (const auto& output_name : config_.selected_outputs) {
    const auto it = record.point_result.outputs.find(output_name);
    points_stream_ << ",";
    if (it != record.point_result.outputs.end()) {
      points_stream_ << escape_csv(value_to_csv(it->second));
    }
  }

  for (const auto& likelihood_name : config_.likelihood_names) {
    const auto it = record.point_result.likelihood_terms.find(likelihood_name);
    points_stream_ << ",";
    if (it != record.point_result.likelihood_terms.end()) {
      points_stream_ << it->second;
    }
  }

  points_stream_ << "\n";
}

void ResultWriter::write_best_fit(const RunSummary& summary) {
  std::ofstream stream(best_fit_path_, std::ios::out);
  if (!stream.is_open()) {
    throw std::runtime_error("Failed to open best-fit file: " + best_fit_path_);
  }

  stream << "{\n";
  stream << "  \"has_best_point\": " << (summary.has_best_point ? "true" : "false");
  if (!summary.has_best_point) {
    stream << "\n}\n";
    return;
  }
  stream << ",\n";
  stream << "  \"best_metric_value\": " << summary.best_metric_value << ",\n";
  stream << "  \"best_scanner_target\": " << summary.best_scanner_target << ",\n";
  stream << "  \"parameters\": {\n";
  for (std::size_t i = 0; i < scanned_parameters_.size(); ++i) {
    stream << "    " << json_escape(scanned_parameters_[i].name) << ": "
           << summary.best_scanned_values[i];
    if (i + 1 != scanned_parameters_.size()) stream << ",";
    stream << "\n";
  }
  stream << "  },\n";
  stream << "  \"outputs\": {\n";
  std::vector<std::pair<std::string, Value>> outputs(summary.best_point_result.outputs.begin(),
                                                     summary.best_point_result.outputs.end());
  std::sort(outputs.begin(), outputs.end(),
            [](const auto& lhs, const auto& rhs) { return lhs.first < rhs.first; });
  for (std::size_t i = 0; i < outputs.size(); ++i) {
    const auto& [name, value] = outputs[i];
    stream << "    " << json_escape(name) << ": " << value_to_json(value);
    if (i + 1U != outputs.size()) stream << ",";
    stream << "\n";
  }
  stream << "  },\n";
  stream << "  \"likelihood_terms\": {\n";
  std::vector<std::pair<std::string, double>> likelihoods(
      summary.best_point_result.likelihood_terms.begin(),
      summary.best_point_result.likelihood_terms.end());
  std::sort(likelihoods.begin(), likelihoods.end(),
            [](const auto& lhs, const auto& rhs) { return lhs.first < rhs.first; });
  for (std::size_t i = 0; i < likelihoods.size(); ++i) {
    const auto& [name, value] = likelihoods[i];
    stream << "    " << json_escape(name) << ": " << value;
    if (i + 1U != likelihoods.size()) stream << ",";
    stream << "\n";
  }
  stream << "  }\n";
  stream << "}\n";
}

void ResultWriter::write_summary(const RunSummary& summary) {
  std::ofstream stream(summary_path_, std::ios::out);
  if (!stream.is_open()) {
    throw std::runtime_error("Failed to open summary file: " + summary_path_);
  }

  stream << "{\n";
  stream << "  \"evaluations\": " << summary.evaluations << ",\n";
  stream << "  \"saved_points\": " << summary.saved_points << ",\n";
  stream << "  \"valid_points\": " << summary.valid_points << ",\n";
  stream << "  \"interrupted\": " << (summary.interrupted ? "true" : "false") << ",\n";
  stream << "  \"has_best_point\": " << (summary.has_best_point ? "true" : "false") << ",\n";
  stream << "  \"failure_counters\": {\n";
  stream << "    \"ok\": " << summary.failures.ok << ",\n";
  stream << "    \"missing_input\": " << summary.failures.missing_input << ",\n";
  stream << "    \"invalid_point\": " << summary.failures.invalid_point << ",\n";
  stream << "    \"numerical_error\": " << summary.failures.numerical_error << ",\n";
  stream << "    \"evaluation_error\": " << summary.failures.evaluation_error << ",\n";
  stream << "    \"non_finite_objective\": " << summary.failures.non_finite_objective << "\n";
  stream << "  },\n";
  stream << "  \"failure_reasons\": {\n";
  std::vector<std::pair<std::string, std::size_t>> reasons(summary.failures.by_reason.begin(),
                                                           summary.failures.by_reason.end());
  std::sort(reasons.begin(), reasons.end(),
            [](const auto& lhs, const auto& rhs) { return lhs.first < rhs.first; });
  for (std::size_t i = 0; i < reasons.size(); ++i) {
    const auto& [reason, value] = reasons[i];
    stream << "    " << json_escape(reason) << ": " << value;
    if (i + 1U != reasons.size()) stream << ",";
    stream << "\n";
  }
  stream << "  }\n";
  stream << "}\n";
}

void ResultWriter::flush() {
  if (points_stream_.is_open()) {
    points_stream_.flush();
  }
}

std::string ResultWriter::escape_csv(const std::string& value) const {
  if (value.find_first_of(",\"\n") == std::string::npos) {
    return value;
  }
  std::string escaped = "\"";
  for (char ch : value) {
    if (ch == '"') escaped += "\"";
    escaped += ch;
  }
  escaped += "\"";
  return escaped;
}

std::string ResultWriter::value_to_csv(const Value& value) const {
  if (const auto* real = std::get_if<double>(&value)) return std::to_string(*real);
  if (const auto* boolean = std::get_if<bool>(&value)) return *boolean ? "true" : "false";
  if (const auto* complex = std::get_if<std::complex<double>>(&value)) {
    return complex_to_string(*complex);
  }
  if (const auto* string = std::get_if<std::string>(&value)) return *string;
  if (const auto* vector = std::get_if<Eigen::VectorXd>(&value)) {
    return real_vector_to_string(*vector);
  }
  if (const auto* matrix = std::get_if<Eigen::MatrixXd>(&value)) {
    return real_matrix_to_string(*matrix);
  }
  if (const auto* vector = std::get_if<Eigen::VectorXcd>(&value)) {
    return complex_vector_to_csv(*vector);
  }
  if (const auto* matrix = std::get_if<Eigen::MatrixXcd>(&value)) {
    return complex_matrix_to_csv(*matrix);
  }
  if (const auto* diag = std::get_if<DiagonalizationValue>(&value)) {
    return "{singular_values=" + real_vector_to_string(diag->singular_values) + "}";
  }
  return "";
}

std::string ResultWriter::json_escape(const std::string& value) const {
  std::string escaped;
  escaped.reserve(value.size() + 2U);
  escaped.push_back('"');
  for (char ch : value) {
    switch (ch) {
      case '"':
        escaped += "\\\"";
        break;
      case '\\':
        escaped += "\\\\";
        break;
      case '\n':
        escaped += "\\n";
        break;
      default:
        escaped.push_back(ch);
        break;
    }
  }
  escaped.push_back('"');
  return escaped;
}

std::string ResultWriter::value_to_json(const Value& value) const {
  if (const auto* real = std::get_if<double>(&value)) return std::to_string(*real);
  if (const auto* boolean = std::get_if<bool>(&value)) return *boolean ? "true" : "false";
  if (const auto* complex = std::get_if<std::complex<double>>(&value)) {
    return complex_to_json(*complex);
  }
  if (const auto* string = std::get_if<std::string>(&value)) return json_escape(*string);
  if (const auto* vector = std::get_if<Eigen::VectorXd>(&value)) {
    return real_vector_to_string(*vector);
  }
  if (const auto* matrix = std::get_if<Eigen::MatrixXd>(&value)) {
    return real_matrix_to_string(*matrix);
  }
  if (const auto* vector = std::get_if<Eigen::VectorXcd>(&value)) {
    return complex_vector_to_json(*vector);
  }
  if (const auto* matrix = std::get_if<Eigen::MatrixXcd>(&value)) {
    return complex_matrix_to_json(*matrix);
  }
  if (const auto* diag = std::get_if<DiagonalizationValue>(&value)) {
    return "{\"singular_values\": " + real_vector_to_string(diag->singular_values) +
           ", \"eigenvalues\": " + real_vector_to_string(diag->eigenvalues) + "}";
  }
  return "null";
}

}  // namespace bsm::core::scan

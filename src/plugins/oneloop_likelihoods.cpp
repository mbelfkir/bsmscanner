#include "bsm/core/plugins.hpp"
#include "bsm/core/table_interpolation.hpp"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <sstream>
#include <limits>
#include <mutex>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace bsm::plugins::oneloop_likelihoods {

namespace {

enum class InterpolationKind {
  Linear,
  CubicSpline,
};

struct TableData {
  std::vector<std::vector<double>> rows;
  std::vector<double> second_derivatives;
  InterpolationKind interpolation = InterpolationKind::Linear;
};

struct PluginInputs {
  double log10_dm21 = std::numeric_limits<double>::quiet_NaN();
  double dm3l_mev = std::numeric_limits<double>::quiet_NaN();
  double out_of_range_penalty_scale = 0.0;
  double out_of_range_penalty_cap = std::numeric_limits<double>::infinity();
  double in_range_offset = 0.0;
  std::string dm21_table_file;
  std::string dm3l_table_file;
  InterpolationKind interpolation = InterpolationKind::Linear;
};

std::mutex& table_cache_mutex() {
  static std::mutex instance;
  return instance;
}

std::unordered_map<std::string, TableData>& table_cache() {
  static std::unordered_map<std::string, TableData> instance;
  return instance;
}

double require_real(const bsm::core::Value& value, const std::string& name) {
  if (const auto* real = std::get_if<double>(&value)) {
    return *real;
  }
  if (const auto* boolean = std::get_if<bool>(&value)) {
    return *boolean ? 1.0 : 0.0;
  }
  throw std::runtime_error(
      "oneloop_likelihoods binding '" + name + "' must be a real scalar.");
}

std::string require_string_option(const bsm::core::PluginOptionMap& options,
                                  const std::string& name) {
  const auto it = options.find(name);
  if (it == options.end()) {
    throw std::runtime_error(
        "oneloop_likelihoods requires the string option '" + name + "'.");
  }
  if (const auto* string = std::get_if<std::string>(&it->second)) {
    return *string;
  }
  throw std::runtime_error(
      "oneloop_likelihoods option '" + name + "' must be a string.");
}

double option_as_real(const bsm::core::PluginOptionMap& options,
                      const std::string& name,
                      double default_value) {
  const auto it = options.find(name);
  if (it == options.end()) {
    return default_value;
  }
  if (const auto* string = std::get_if<std::string>(&it->second)) {
    std::size_t processed = 0;
    const double parsed = std::stod(*string, &processed);
    if (processed != string->size()) {
      throw std::runtime_error(
          "oneloop_likelihoods option '" + name +
          "' must be a real scalar or a numeric string.");
    }
    return parsed;
  }
  return require_real(it->second, name);
}

InterpolationKind option_as_interpolation(
    const bsm::core::PluginOptionMap& options) {
  const auto it = options.find("interpolation");
  if (it == options.end()) {
    return InterpolationKind::Linear;
  }
  if (const auto* string = std::get_if<std::string>(&it->second)) {
    if (*string == "linear") {
      return InterpolationKind::Linear;
    }
    if (*string == "cubic_spline") {
      return InterpolationKind::CubicSpline;
    }
  }
  throw std::runtime_error(
      "oneloop_likelihoods option 'interpolation' must be 'linear' or 'cubic_spline'.");
}

void validate_table(const std::vector<std::vector<double>>& table,
                    const std::string& path) {
  bsm::core::table::validate_ascending(
      table,
      "Lookup table '" + path + "' is empty.",
      "Lookup table '" + path + "' must have strictly increasing x-values.");
}

std::vector<std::vector<double>> load_two_column_table(const std::string& path) {
  std::ifstream handle(path);
  if (!handle) {
    throw std::runtime_error("Could not open oneloop likelihood table '" + path + "'.");
  }

  std::vector<std::vector<double>> rows;
  std::string line;
  while (std::getline(handle, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    for (char& c : line) {
      if (c == ',') {
        c = ' ';
      }
    }
    std::istringstream stream(line);
    double x = 0.0;
    double y = 0.0;
    if (!(stream >> x >> y)) {
      throw std::runtime_error(
          "Failed to parse two-column likelihood table '" + path + "'.");
    }
    rows.push_back({x, y});
  }

  validate_table(rows, path);
  return rows;
}

const TableData& get_table(const std::string& path, InterpolationKind interpolation) {
  const std::string cache_key =
      path + "::" + (interpolation == InterpolationKind::CubicSpline ? "cubic" : "linear");
  std::lock_guard<std::mutex> lock(table_cache_mutex());
  auto& cache = table_cache();
  const auto it = cache.find(cache_key);
  if (it != cache.end()) {
    return it->second;
  }

  TableData data;
  data.rows = load_two_column_table(path);
  data.interpolation = interpolation;
  if (interpolation == InterpolationKind::CubicSpline) {
    data.second_derivatives =
        bsm::core::table::build_natural_cubic_spline_second_derivatives(data.rows);
  }
  return cache.emplace(cache_key, std::move(data)).first->second;
}

double interpolate(const TableData& table, double x) {
  switch (table.interpolation) {
    case InterpolationKind::Linear:
      return bsm::core::table::interpolate_linear(table.rows, x);
    case InterpolationKind::CubicSpline:
      return bsm::core::table::interpolate_cubic_spline(
          table.rows, table.second_derivatives, x);
  }
  throw std::runtime_error("Unhandled oneloop likelihood interpolation.");
}

double source_style_table_term(const TableData& table,
                               double x,
                               double penalty_scale,
                               double penalty_cap,
                               double in_range_offset) {
  const double lower = table.rows.front().at(0);
  const double upper = table.rows.back().at(0);
  if (x >= lower && x <= upper) {
    return interpolate(table, x) + in_range_offset;
  }
  const double distance = (x < lower) ? (lower - x) : (x - upper);
  double penalty = penalty_scale * distance * distance;
  if (std::isfinite(penalty_cap)) {
    penalty = std::min(penalty, penalty_cap);
  }
  return penalty;
}

PluginInputs parse_inputs(const bsm::core::PluginInvocation& invocation) {
  PluginInputs inputs;
  auto dm21_it = invocation.arguments.find("log10_dm21");
  auto dm3l_it = invocation.arguments.find("dm3l_meV");
  if (dm21_it == invocation.arguments.end() || dm3l_it == invocation.arguments.end()) {
    throw std::runtime_error(
        "oneloop_likelihoods.neutrino_mass_term requires log10_dm21 and dm3l_meV bindings.");
  }
  inputs.log10_dm21 = require_real(dm21_it->second, "log10_dm21");
  inputs.dm3l_mev = require_real(dm3l_it->second, "dm3l_meV");
  inputs.dm21_table_file = require_string_option(invocation.options, "dm21_table_file");
  inputs.dm3l_table_file = require_string_option(invocation.options, "dm3l_table_file");
  inputs.interpolation = option_as_interpolation(invocation.options);
  inputs.out_of_range_penalty_scale =
      option_as_real(invocation.options, "out_of_range_penalty_scale", 4.0e4);
  inputs.out_of_range_penalty_cap =
      option_as_real(invocation.options, "out_of_range_penalty_cap", 1.0e6);
  inputs.in_range_offset =
      option_as_real(invocation.options, "in_range_offset", 0.0);
  return inputs;
}

bsm::core::Value neutrino_mass_term(const bsm::core::PluginInvocation& invocation) {
  const PluginInputs inputs = parse_inputs(invocation);
  const TableData& dm21_table = get_table(inputs.dm21_table_file, inputs.interpolation);
  const TableData& dm3l_table = get_table(inputs.dm3l_table_file, inputs.interpolation);

  const double lower_dm21 = dm21_table.rows.front().at(0);
  const double upper_dm21 = dm21_table.rows.back().at(0);
  if (inputs.log10_dm21 < lower_dm21 || inputs.log10_dm21 > upper_dm21) {
    return source_style_table_term(
        dm21_table,
        inputs.log10_dm21,
        inputs.out_of_range_penalty_scale,
        inputs.out_of_range_penalty_cap,
        0.0);
  }

  const double lower_dm3l = dm3l_table.rows.front().at(0);
  const double upper_dm3l = dm3l_table.rows.back().at(0);
  if (inputs.dm3l_mev < lower_dm3l || inputs.dm3l_mev > upper_dm3l) {
    return source_style_table_term(
        dm3l_table,
        inputs.dm3l_mev,
        inputs.out_of_range_penalty_scale,
        inputs.out_of_range_penalty_cap,
        0.0);
  }

  return interpolate(dm21_table, inputs.log10_dm21) + inputs.in_range_offset +
         interpolate(dm3l_table, inputs.dm3l_mev) + inputs.in_range_offset;
}

struct Registrar {
  Registrar() {
    bsm::core::register_plugin_function(
        "oneloop_likelihoods",
        "neutrino_mass_term",
        neutrino_mass_term);
  }
} registrar;

}  // namespace

}  // namespace bsm::plugins::oneloop_likelihoods

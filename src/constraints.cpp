#include "bsm/core/constraints.hpp"
#include "bsm/core/functions.hpp"
#include "bsm/core/plugins.hpp"

#include <Eigen/Dense>

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <unordered_map>
#include <vector>

namespace bsm::core {

namespace {

std::unordered_map<std::string, CustomConstraintCallback>& registry() {
  static std::unordered_map<std::string, CustomConstraintCallback> instance;
  return instance;
}

double value_as_real(const Value& value) {
  if (const auto* real = std::get_if<double>(&value)) {
    return *real;
  }
  if (const auto* boolean = std::get_if<bool>(&value)) {
    return *boolean ? 1.0 : 0.0;
  }
  if (const auto* complex = std::get_if<std::complex<double>>(&value)) {
    if (std::abs(complex->imag()) > 1e-14) {
      throw std::runtime_error("Constraint expected a real observable.");
    }
    return complex->real();
  }
  throw std::runtime_error("Unsupported observable type in constraint.");
}

bool value_as_bool(const Value& value) {
  if (const auto* boolean = std::get_if<bool>(&value)) {
    return *boolean;
  }
  return value_as_real(value) != 0.0;
}

void validate_table(const std::vector<std::vector<double>>& table) {
  if (table.empty()) {
    throw std::runtime_error("Empty lookup table.");
  }
  if (table.size() <= 1) {
    return;
  }
  for (std::size_t i = 1; i < table.size(); ++i) {
    if (!(table[i - 1].at(0) < table[i].at(0))) {
      throw std::runtime_error(
          "Lookup table x-values must be strictly increasing.");
    }
  }
}

double interpolate_linear(const std::vector<std::vector<double>>& table,
                          double x) {
  if (x <= table.front().at(0)) {
    return table.front().at(1);
  }
  if (x >= table.back().at(0)) {
    return table.back().at(1);
  }
  for (std::size_t i = 1; i < table.size(); ++i) {
    const auto& left = table[i - 1];
    const auto& right = table[i];
    if (x <= right.at(0)) {
      const double span = right.at(0) - left.at(0);
      const double weight = (x - left.at(0)) / span;
      return (1.0 - weight) * left.at(1) + weight * right.at(1);
    }
  }
  return table.back().at(1);
}

std::vector<double> build_natural_cubic_spline_second_derivatives(
    const std::vector<std::vector<double>>& table) {
  const std::size_t n = table.size();
  std::vector<double> second(n, 0.0);
  if (n <= 2) {
    return second;
  }

  std::vector<double> u(n - 1, 0.0);
  for (std::size_t i = 1; i + 1 < n; ++i) {
    const double x_im1 = table[i - 1].at(0);
    const double x_i = table[i].at(0);
    const double x_ip1 = table[i + 1].at(0);
    const double y_im1 = table[i - 1].at(1);
    const double y_i = table[i].at(1);
    const double y_ip1 = table[i + 1].at(1);

    const double sig = (x_i - x_im1) / (x_ip1 - x_im1);
    const double p = sig * second[i - 1] + 2.0;
    second[i] = (sig - 1.0) / p;
    u[i] = (6.0 *
                (((y_ip1 - y_i) / (x_ip1 - x_i)) -
                 ((y_i - y_im1) / (x_i - x_im1))) /
                (x_ip1 - x_im1) -
            sig * u[i - 1]) /
           p;
  }

  second[n - 1] = 0.0;
  for (std::size_t k = n - 1; k-- > 0;) {
    second[k] = second[k] * second[k + 1] + u[k];
  }
  return second;
}

double interpolate_cubic_spline(const std::vector<std::vector<double>>& table,
                                const std::vector<double>& second,
                                double x) {
  if (table.size() <= 1) {
    return table.front().at(1);
  }
  if (x <= table.front().at(0)) {
    x = table.front().at(0);
  } else if (x >= table.back().at(0)) {
    x = table.back().at(0);
  }

  auto upper = std::lower_bound(
      table.begin(),
      table.end(),
      x,
      [](const std::vector<double>& row, double value) { return row.at(0) < value; });
  std::size_t hi = static_cast<std::size_t>(upper - table.begin());
  if (hi == 0) {
    hi = 1;
  } else if (hi >= table.size()) {
    hi = table.size() - 1;
  }
  const std::size_t lo = hi - 1;

  const double x_lo = table[lo].at(0);
  const double x_hi = table[hi].at(0);
  const double y_lo = table[lo].at(1);
  const double y_hi = table[hi].at(1);
  const double h = x_hi - x_lo;
  if (!(h > 0.0)) {
    throw std::runtime_error("Lookup table contains a non-positive spline interval.");
  }
  const double a = (x_hi - x) / h;
  const double b = (x - x_lo) / h;
  return a * y_lo + b * y_hi +
         ((a * a * a - a) * second[lo] + (b * b * b - b) * second[hi]) *
             (h * h) / 6.0;
}

double interpolate_table(const ConstraintSpec& spec, double x) {
  switch (spec.interpolation) {
    case TableInterpolationKind::Linear:
      return interpolate_linear(spec.table, x);
    case TableInterpolationKind::CubicSpline:
      return interpolate_cubic_spline(spec.table, spec.spline_second_derivatives, x);
  }
  throw std::runtime_error("Unhandled table interpolation kind.");
}

double evaluate_table_lookup(const ConstraintSpec& spec, double x) {
  const double lower = spec.table.front().at(0);
  const double upper = spec.table.back().at(0);
  if (x >= lower && x <= upper) {
    return interpolate_table(spec, x) + spec.in_range_offset;
  }
  if (!(spec.out_of_range_penalty_scale > 0.0) ||
      !std::isfinite(spec.out_of_range_penalty_scale)) {
    return interpolate_table(spec, x);
  }
  const double distance = (x < lower) ? (lower - x) : (x - upper);
  double penalty = spec.out_of_range_penalty_scale * distance * distance;
  if (std::isfinite(spec.out_of_range_penalty_cap)) {
    penalty = std::min(penalty, spec.out_of_range_penalty_cap);
  }
  return penalty;
}

}  // namespace

void finalize_constraint(ConstraintSpec& spec) {
  if (spec.kind != ConstraintKind::TableLookup) {
    return;
  }
  validate_table(spec.table);
  if (spec.interpolation == TableInterpolationKind::CubicSpline) {
    spec.spline_second_derivatives =
        build_natural_cubic_spline_second_derivatives(spec.table);
  } else {
    spec.spline_second_derivatives.clear();
  }
}

void register_custom_constraint(const std::string& name,
                                CustomConstraintCallback callback) {
  registry()[name] = std::move(callback);
}

std::optional<CustomConstraintCallback> find_custom_constraint(
    const std::string& name) {
  const auto it = registry().find(name);
  if (it == registry().end()) {
    return std::nullopt;
  }
  return it->second;
}

double evaluate_constraint(const ConstraintSpec& spec,
                           const ValueResolver& resolver) {
  switch (spec.kind) {
    case ConstraintKind::Gaussian: {
      const double x = value_as_real(resolver(spec.observable));
      const double z = (x - spec.mean) / spec.sigma;
      return 0.5 * z * z;
    }

    case ConstraintKind::AsymmetricGaussian: {
      const double x = value_as_real(resolver(spec.observable));
      const double sigma = (x >= spec.mean) ? spec.sigma_up : spec.sigma_down;
      const double z = (x - spec.mean) / sigma;
      return 0.5 * z * z;
    }

    case ConstraintKind::UpperLimit: {
      const double x = value_as_real(resolver(spec.observable));
      if (x <= spec.upper) {
        return 0.0;
      }
      if (spec.sigma > 0.0) {
        const double z = (x - spec.upper) / spec.sigma;
        return 0.5 * z * z;
      }
      return std::numeric_limits<double>::infinity();
    }

    case ConstraintKind::LowerLimit: {
      const double x = value_as_real(resolver(spec.observable));
      if (x >= spec.lower) {
        return 0.0;
      }
      if (spec.sigma > 0.0) {
        const double z = (spec.lower - x) / spec.sigma;
        return 0.5 * z * z;
      }
      return std::numeric_limits<double>::infinity();
    }

    case ConstraintKind::Interval: {
      const double x = value_as_real(resolver(spec.observable));
      if (x >= spec.lower && x <= spec.upper) {
        return 0.0;
      }
      if (spec.sigma > 0.0) {
        const double d = (x < spec.lower) ? (spec.lower - x) : (x - spec.upper);
        return 0.5 * (d / spec.sigma) * (d / spec.sigma);
      }
      return std::numeric_limits<double>::infinity();
    }

    case ConstraintKind::HardCut: {
      const Value& value = resolver(spec.observable);
      if (std::holds_alternative<bool>(value)) {
        return value_as_bool(value) ? 0.0 : std::numeric_limits<double>::infinity();
      }
      const double x = value_as_real(value);
      const bool pass = x >= spec.lower && x <= spec.upper;
      return pass ? 0.0 : std::numeric_limits<double>::infinity();
    }

    case ConstraintKind::TableLookup: {
      const double x = value_as_real(resolver(spec.observable));
      return evaluate_table_lookup(spec, x);
    }

    case ConstraintKind::MultivariateGaussian: {
      const auto n = spec.observables.size();
      Eigen::VectorXd delta(static_cast<Eigen::Index>(n));
      Eigen::MatrixXd covariance(static_cast<Eigen::Index>(n),
                                 static_cast<Eigen::Index>(n));

      for (std::size_t i = 0; i < n; ++i) {
        delta[static_cast<Eigen::Index>(i)] =
            value_as_real(resolver(spec.observables[i])) - spec.means[i];
        for (std::size_t j = 0; j < n; ++j) {
          covariance(static_cast<Eigen::Index>(i),
                     static_cast<Eigen::Index>(j)) = spec.covariance[i][j];
        }
      }

      const Eigen::MatrixXd inverse = covariance.inverse();
      return spec.quadratic_form_prefactor *
             (delta.transpose() * inverse * delta)(0, 0);
    }

    case ConstraintKind::Custom: {
      if (spec.plugin_call.has_value()) {
        return value_as_real(execute_plugin_call(*spec.plugin_call, resolver));
      }
      const auto callback = find_custom_constraint(spec.plugin);
      if (!callback.has_value()) {
        throw std::runtime_error("Unknown custom constraint plugin: " + spec.plugin);
      }
      return (*callback)(spec, resolver);
    }
  }

  throw std::runtime_error("Unhandled constraint type.");
}

}  // namespace bsm::core

#include "bsm/core/constraints.hpp"
#include "bsm/core/functions.hpp"
#include "bsm/core/plugins.hpp"
#include "bsm/core/table_interpolation.hpp"

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

double interpolate_table(const ConstraintSpec& spec, double x) {
  switch (spec.interpolation) {
    case TableInterpolationKind::Linear:
      return table::interpolate_linear(spec.table, x);
    case TableInterpolationKind::CubicSpline:
      return table::interpolate_cubic_spline(spec.table, spec.spline_second_derivatives, x);
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
  table::validate_ascending(spec.table);
  if (spec.interpolation == TableInterpolationKind::CubicSpline) {
    spec.spline_second_derivatives =
        table::build_natural_cubic_spline_second_derivatives(spec.table);
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
